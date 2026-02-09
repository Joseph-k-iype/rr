"""
Base Executor & LangGraph Bridge
==================================
Core bridge between Google A2A SDK AgentExecutor and LangGraph node functions.

Architecture:
    LangGraph calls:  node_fn(state) -> state
                           |
                      wrap_executor_as_node()
                           |
                      InProcessRequestContext(state)
                      EventQueue()
                           |
                      executor.execute(ctx, queue)
                           |
                      _drain_event_queue_to_sse()
                           |
                      return state
"""

import asyncio
import logging
import time
import uuid
from typing import Optional

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.types import (
    TaskState,
    TaskStatus,
    TaskStatusUpdateEvent,
)

from agents.ai_service import get_ai_service, AIRequestError, AIAuthenticationError
from agents.audit.event_store import get_event_store
from agents.state.wizard_state import WizardAgentState
from models.agent_models import AgentEvent, AgentEventType
from services.sse_manager import get_sse_manager

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Mapping from A2A TaskState to SSE AgentEventType
# ---------------------------------------------------------------------------
_TASK_STATE_TO_EVENT_TYPE = {
    TaskState.working: AgentEventType.AGENT_STARTED,
    TaskState.completed: AgentEventType.AGENT_COMPLETED,
    TaskState.input_required: AgentEventType.HUMAN_REVIEW_REQUIRED,
    TaskState.failed: AgentEventType.AGENT_FAILED,
}


# ---------------------------------------------------------------------------
# InProcessRequestContext - wraps WizardAgentState for A2A executor contract
# ---------------------------------------------------------------------------
class InProcessRequestContext(RequestContext):
    """Wraps a mutable WizardAgentState dict so executors access it via A2A's
    RequestContext interface while still mutating the LangGraph state directly."""

    def __init__(self, state: WizardAgentState):
        task_id = f"task_{uuid.uuid4().hex[:12]}"
        context_id = f"ctx_{uuid.uuid4().hex[:12]}"
        super().__init__(task_id=task_id, context_id=context_id)
        self._state = state

    @property
    def state(self) -> WizardAgentState:
        """Direct access to the mutable LangGraph state dict."""
        return self._state

    def get_user_input(self, delimiter: str = "\n") -> str:
        """Return the rule text as the primary user input."""
        return self._state.get("rule_text", "")


# ---------------------------------------------------------------------------
# ComplianceAgentExecutor - base class for all 6 agent executors
# ---------------------------------------------------------------------------
class ComplianceAgentExecutor(AgentExecutor):
    """Base executor for compliance agents.

    Subclasses must set ``agent_name`` and implement ``execute()``.
    """

    agent_name: str = "base"

    def __init__(
        self,
        ai_service=None,
        event_store=None,
        db_service=None,
    ):
        self.ai_service = ai_service or get_ai_service()
        self.event_store = event_store or get_event_store()
        self.db_service = db_service

    # -- convenience emitters (async, called from async execute()) -------------

    async def emit_working(
        self,
        event_queue: EventQueue,
        context: InProcessRequestContext,
        message: str = "",
    ):
        """Emit a TaskState.working status update."""
        await event_queue.enqueue_event(
            TaskStatusUpdateEvent(
                taskId=context.task_id,
                contextId=context.context_id,
                status=TaskStatus(state=TaskState.working, message=None),
                final=False,
            )
        )

    async def emit_completed(
        self,
        event_queue: EventQueue,
        context: InProcessRequestContext,
        message: str = "",
    ):
        """Emit a TaskState.completed status update."""
        await event_queue.enqueue_event(
            TaskStatusUpdateEvent(
                taskId=context.task_id,
                contextId=context.context_id,
                status=TaskStatus(state=TaskState.completed, message=None),
                final=True,
            )
        )

    async def emit_input_required(
        self,
        event_queue: EventQueue,
        context: InProcessRequestContext,
        message: str = "",
    ):
        """Emit a TaskState.input_required status update."""
        await event_queue.enqueue_event(
            TaskStatusUpdateEvent(
                taskId=context.task_id,
                contextId=context.context_id,
                status=TaskStatus(state=TaskState.input_required, message=None),
                final=False,
            )
        )

    # -- AI call with retry (handles 401 token refresh transparently) ----------

    def call_ai_with_retry(
        self,
        user_prompt: str,
        system_prompt: str,
        max_retries: int = 2,
    ) -> str:
        """Call AI service with transparent retry on auth/request errors.

        Retries up to max_retries times on AIRequestError or
        AIAuthenticationError (e.g. token expiry, 401). Preserves the
        full prompt context across retries so no information is lost.

        Returns:
            LLM response text

        Raises:
            AIRequestError: If all retries fail
        """
        last_error = None
        for attempt in range(max_retries + 1):
            try:
                return self.ai_service.chat(user_prompt, system_prompt)
            except (AIRequestError, AIAuthenticationError) as e:
                last_error = e
                if attempt < max_retries:
                    logger.warning(
                        f"{self.agent_name}: auth/request error "
                        f"(attempt {attempt + 1}/{max_retries + 1}), retrying: {e}"
                    )
                    time.sleep(1)
                    continue
        raise AIRequestError(
            f"{self.agent_name}: failed after {max_retries + 1} attempts: {last_error}"
        )

    # -- abstract methods from AgentExecutor -----------------------------------

    async def execute(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        raise NotImplementedError("Subclasses must implement execute()")

    async def cancel(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        raise Exception(f"Cancel not supported for {self.agent_name}")


# ---------------------------------------------------------------------------
# wrap_executor_as_node  – the LangGraph <-> A2A bridge
# ---------------------------------------------------------------------------
def wrap_executor_as_node(
    executor: ComplianceAgentExecutor,
):
    """Return a ``def node_fn(state) -> state`` compatible with LangGraph.

    1. Wraps the state in an ``InProcessRequestContext``.
    2. Runs the executor's ``execute()`` (async) synchronously.
    3. Drains the ``EventQueue`` and converts A2A events to ``AgentEvent`` SSE messages.
    4. Appends to ``state["events"]`` for backward compatibility.
    """

    async def _run(state: WizardAgentState) -> None:
        ctx = InProcessRequestContext(state)
        queue = EventQueue()
        await executor.execute(ctx, queue)
        await _drain_event_queue_to_sse(queue, state, executor.agent_name)

    def node_fn(state: WizardAgentState) -> WizardAgentState:
        # Run the async execute + drain in a sync context
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            # We're inside an async context (e.g. FastAPI) – run in a thread
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                pool.submit(asyncio.run, _run(state)).result()
        else:
            asyncio.run(_run(state))

        return state

    # Preserve a useful name for LangGraph introspection
    node_fn.__name__ = f"{executor.agent_name}_node"
    node_fn.__qualname__ = f"{executor.agent_name}_node"
    return node_fn


# ---------------------------------------------------------------------------
# internal: drain A2A EventQueue into SSE AgentEvents
# ---------------------------------------------------------------------------
async def _drain_event_queue_to_sse(
    queue: EventQueue,
    state: WizardAgentState,
    agent_name: str,
):
    """Dequeue all A2A events, map to AgentEvent, publish via SSE manager."""
    sse_manager = get_sse_manager()
    session_id = state.get("origin_country", "unknown")

    while True:
        try:
            event = await queue.dequeue_event(no_wait=True)
        except Exception:
            break

        if event is None:
            break

        # Map A2A TaskStatusUpdateEvent -> SSE AgentEvent
        if isinstance(event, TaskStatusUpdateEvent):
            task_state = event.status.state
            event_type = _TASK_STATE_TO_EVENT_TYPE.get(
                task_state, AgentEventType.AGENT_COMPLETED
            )

            sse_event = AgentEvent(
                event_type=event_type,
                session_id=session_id,
                agent_name=agent_name,
                phase=state.get("current_phase", ""),
                message=f"{agent_name}: {task_state}",
            )

            # Publish to SSE
            sse_manager.publish_sync(session_id, sse_event)

            # Backward-compatible state["events"] entry
            state["events"].append({
                "event_type": event_type.value,
                "agent_name": agent_name,
                "message": sse_event.message,
            })
