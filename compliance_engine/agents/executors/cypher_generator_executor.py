"""
Cypher Generator Executor
===========================
Mixture of Experts Cypher query generation with FalkorDB syntax validation.
Implements Google A2A SDK AgentExecutor interface.
"""

import logging
import time

from pydantic import ValidationError

from a2a.server.agent_execution import RequestContext
from a2a.server.events import EventQueue

from agents.executors.base_executor import ComplianceAgentExecutor, InProcessRequestContext
from agents.executors.utils import parse_json_response
from agents.prompts.cypher_prompts import (
    CYPHER_GENERATOR_SYSTEM_PROMPT,
    CYPHER_GENERATOR_USER_TEMPLATE,
)
from agents.prompts.prompt_builder import build_cypher_prompt
from agents.audit.event_types import AuditEventType
from agents.nodes.validation_models import CypherQueriesModel
from agents.ai_service import AIRequestError

logger = logging.getLogger(__name__)


class CypherGeneratorExecutor(ComplianceAgentExecutor):
    """Cypher generator agent executor - MoE query generation with FalkorDB validation."""

    agent_name = "cypher_generator"

    async def execute(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        ctx: InProcessRequestContext = context
        state = ctx.state
        start_time = time.time()
        session_id = state.get("origin_country", "unknown")

        # Guard: require rule_definition before generating Cypher
        if not state.get("rule_definition"):
            state["current_phase"] = "supervisor"
            return

        await self.emit_working(event_queue, ctx)

        self.event_store.append(
            session_id=session_id,
            event_type=AuditEventType.AGENT_INVOKED,
            agent_name=self.agent_name,
        )

        user_prompt = build_cypher_prompt(
            template=CYPHER_GENERATOR_USER_TEMPLATE,
            rule_definition=state["rule_definition"],
            feedback="",
        )

        try:
            response = self.ai_service.chat(user_prompt, CYPHER_GENERATOR_SYSTEM_PROMPT)
            parsed = parse_json_response(response)

            if parsed:
                queries = parsed.get("cypher_queries", {})
                try:
                    validated = CypherQueriesModel(**queries)
                    state["cypher_queries"] = {
                        "queries": validated.model_dump(),
                        "params": parsed.get("query_params", {}),
                        "optimization_notes": parsed.get("optimization_notes", []),
                    }

                    # FalkorDB syntax validation via EXPLAIN
                    if self.db_service:
                        self._validate_cypher_syntax(validated, session_id)

                    state["current_phase"] = "validator"

                    duration = (time.time() - start_time) * 1000
                    self.event_store.append(
                        session_id=session_id,
                        event_type=AuditEventType.CYPHER_GENERATED,
                        agent_name=self.agent_name,
                        duration_ms=duration,
                    )
                    logger.info("Cypher queries generated successfully")

                except ValidationError as ve:
                    errors = [str(e) for e in ve.errors()]
                    state["current_phase"] = "supervisor"
                    self.event_store.append(
                        session_id=session_id,
                        event_type=AuditEventType.AGENT_FAILED,
                        agent_name=self.agent_name,
                        error=f"Validation errors: {errors}",
                    )
            else:
                state["current_phase"] = "supervisor"
                self.event_store.append(
                    session_id=session_id,
                    event_type=AuditEventType.AGENT_FAILED,
                    agent_name=self.agent_name,
                    error="Failed to parse response",
                )

        except AIRequestError as e:
            logger.error(f"Cypher generator error: {e}")
            state["current_phase"] = "supervisor"
            self.event_store.append(
                session_id=session_id,
                event_type=AuditEventType.AGENT_FAILED,
                agent_name=self.agent_name,
                error=str(e),
            )

        await self.emit_completed(event_queue, ctx)

    def _validate_cypher_syntax(
        self,
        queries: CypherQueriesModel,
        session_id: str,
    ):
        """Validate generated Cypher queries against FalkorDB using EXPLAIN."""
        for query_name in ("rule_check", "rule_insert", "validation"):
            cypher = getattr(queries, query_name)
            try:
                self.db_service.execute_query(f"EXPLAIN {cypher}")
                logger.debug(f"EXPLAIN passed for {query_name}")
            except Exception as e:
                logger.warning(f"EXPLAIN failed for {query_name}: {e}")
                self.event_store.append(
                    session_id=session_id,
                    event_type=AuditEventType.AGENT_FAILED,
                    agent_name=self.agent_name,
                    error=f"Cypher syntax error in {query_name}: {e}",
                )
