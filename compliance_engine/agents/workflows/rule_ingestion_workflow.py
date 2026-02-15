"""
Rule Ingestion Workflow
========================
LangGraph StateGraph for wizard steps 4-5.
Entry -> Supervisor -> {agents} -> Supervisor -> ... -> complete/fail

Uses SqliteSaver checkpointer (persistent) with MemorySaver fallback.
"""

import logging
import os
from typing import Dict, Any, Optional, List
from datetime import datetime
from pathlib import Path

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

# Try to use SqliteSaver for persistent checkpointing; fall back to MemorySaver
try:
    import sqlite3
    from langgraph.checkpoint.sqlite import SqliteSaver
    _HAS_SQLITE_SAVER = True
except ImportError:
    _HAS_SQLITE_SAVER = False

# Persistent checkpoint directory (project-level, not temp)
_CHECKPOINT_DIR = Path(__file__).parent.parent.parent / "data" / "checkpoints"

# Module-level persistent connection (kept open for app lifetime)
_sqlite_conn: "sqlite3.Connection | None" = None

from agents.state.wizard_state import WizardAgentState, create_initial_state
from agents.nodes.supervisor import supervisor_node
from agents.nodes.rule_analyzer import rule_analyzer_node
from agents.nodes.cypher_generator import cypher_generator_node
from agents.nodes.validator import validator_node
from agents.nodes.data_dictionary import data_dictionary_node
from agents.nodes.reference_data import reference_data_node
from agents.nodes.rule_tester import rule_tester_node
from agents.audit.event_store import get_event_store
from agents.audit.event_types import AuditEventType

logger = logging.getLogger(__name__)


def human_review_node(state: WizardAgentState) -> WizardAgentState:
    """Human review node - workflow pauses here for human input."""
    state["requires_human_input"] = True
    state["events"].append({
        "event_type": "human_review_required",
        "agent_name": "human_review",
        "message": "Awaiting human review and input",
    })
    return state


def complete_node(state: WizardAgentState) -> WizardAgentState:
    """Finalize successful workflow."""
    state["success"] = True
    state["events"].append({
        "event_type": "workflow_complete",
        "agent_name": "system",
        "message": "Workflow completed successfully",
    })

    event_store = get_event_store()
    session_id = state.get("origin_country", "unknown")
    event_store.append(
        session_id=session_id,
        event_type=AuditEventType.WORKFLOW_COMPLETED,
        data={
            "rule_id": state.get("rule_definition", {}).get("rule_id"),
            "iterations": state.get("iteration", 0),
        },
    )
    logger.info("Rule ingestion workflow completed successfully")
    return state


def fail_node(state: WizardAgentState) -> WizardAgentState:
    """Handle workflow failure."""
    state["success"] = False
    if not state.get("error_message"):
        state["error_message"] = "Workflow failed after max iterations"
    state["events"].append({
        "event_type": "workflow_failed",
        "agent_name": "system",
        "message": state.get("error_message", "Unknown error"),
    })

    event_store = get_event_store()
    session_id = state.get("origin_country", "unknown")
    event_store.append(
        session_id=session_id,
        event_type=AuditEventType.WORKFLOW_FAILED,
        error=state.get("error_message"),
    )
    logger.error(f"Workflow failed: {state.get('error_message')}")
    return state


def route_from_supervisor(state: WizardAgentState) -> str:
    """Route based on supervisor decision.

    If validation has been retried enough times, route directly to
    validator so its skip-fallback triggers (instead of letting the
    supervisor re-analyze endlessly).
    """
    phase = state.get("current_phase", "fail")

    # If validation retries exhausted, go straight to validator (triggers skip fallback)
    retry_count = state.get("validation_retry_count", 0)
    if retry_count >= 3 and phase not in ("complete", "fail"):
        return "validator"

    # Check max iterations
    iteration = state.get("iteration", 0)
    max_iterations = state.get("max_iterations", 10)
    if iteration >= max_iterations and phase not in ("complete", "fail"):
        return "fail"

    valid_routes = {
        "rule_analyzer", "data_dictionary", "cypher_generator",
        "validator", "reference_data", "rule_tester", "human_review", "complete", "fail"
    }

    if phase in valid_routes:
        return phase
    return "fail"


def route_after_validation(state: WizardAgentState) -> str:
    """Route after validation."""
    phase = state.get("current_phase", "supervisor")
    if phase == "rule_tester":
        return "rule_tester"
    elif phase == "complete":
        return "complete"
    elif phase == "fail":
        return "fail"
    return "supervisor"


def route_after_rule_tester(state: WizardAgentState) -> str:
    """Route after rule tester."""
    phase = state.get("current_phase", "supervisor")
    if phase == "complete":
        return "complete"
    elif phase == "fail":
        return "fail"
    return "supervisor"


def build_rule_ingestion_graph(with_interrupt: bool = True) -> tuple:
    """
    Build the LangGraph workflow for rule ingestion.

    Args:
        with_interrupt: If True, adds interrupt_before on human_review

    Returns:
        Tuple of (compiled graph, checkpointer)
    """
    workflow = StateGraph(WizardAgentState)

    # Add nodes
    workflow.add_node("supervisor", supervisor_node)
    workflow.add_node("rule_analyzer", rule_analyzer_node)
    workflow.add_node("data_dictionary", data_dictionary_node)
    workflow.add_node("cypher_generator", cypher_generator_node)
    workflow.add_node("validator", validator_node)
    workflow.add_node("reference_data", reference_data_node)
    workflow.add_node("rule_tester", rule_tester_node)
    workflow.add_node("human_review", human_review_node)
    workflow.add_node("complete", complete_node)
    workflow.add_node("fail", fail_node)

    # Entry point -> supervisor
    workflow.set_entry_point("supervisor")

    # Supervisor routes to any agent
    workflow.add_conditional_edges(
        "supervisor",
        route_from_supervisor,
        {
            "rule_analyzer": "rule_analyzer",
            "data_dictionary": "data_dictionary",
            "cypher_generator": "cypher_generator",
            "validator": "validator",
            "reference_data": "reference_data",
            "rule_tester": "rule_tester",
            "human_review": "human_review",
            "complete": "complete",
            "fail": "fail",
        }
    )

    # Agent routing function
    def _route_agent(state: WizardAgentState) -> str:
        return state.get("current_phase", "supervisor")

    # All agents route back to supervisor (or forward to next agent)
    agent_route_map = {
        "supervisor": "supervisor",
        "rule_analyzer": "rule_analyzer",
        "data_dictionary": "data_dictionary",
        "cypher_generator": "cypher_generator",
        "validator": "validator",
        "reference_data": "reference_data",
        "rule_tester": "rule_tester",
        "human_review": "human_review",
        "complete": "complete",
        "fail": "fail",
    }
    for agent in ["rule_analyzer", "data_dictionary", "cypher_generator", "reference_data"]:
        workflow.add_conditional_edges(agent, _route_agent, agent_route_map)

    # Validator has special routing (can go to rule_tester)
    workflow.add_conditional_edges(
        "validator",
        route_after_validation,
        {
            "rule_tester": "rule_tester",
            "complete": "complete",
            "fail": "fail",
            "supervisor": "supervisor",
        }
    )

    # Rule tester routing
    workflow.add_conditional_edges(
        "rule_tester",
        route_after_rule_tester,
        {
            "complete": "complete",
            "fail": "fail",
            "supervisor": "supervisor",
        }
    )

    # Human review goes back to supervisor
    workflow.add_edge("human_review", "supervisor")

    # Terminal nodes
    workflow.add_edge("complete", END)
    workflow.add_edge("fail", END)

    # Compile with checkpointer — prefer SqliteSaver for persistent memory
    if _HAS_SQLITE_SAVER:
        global _sqlite_conn
        _CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
        db_path = str(_CHECKPOINT_DIR / "checkpoints.db")
        try:
            # Create a persistent connection (reused across invocations)
            if _sqlite_conn is None:
                _sqlite_conn = sqlite3.connect(db_path, check_same_thread=False)
            checkpointer = SqliteSaver(_sqlite_conn)
            logger.info(f"Using SqliteSaver checkpointer at {db_path}")
        except Exception as e:
            logger.warning(f"SqliteSaver init failed, falling back to MemorySaver: {e}")
            checkpointer = MemorySaver()
    else:
        checkpointer = MemorySaver()

    interrupt = ["human_review"] if with_interrupt else None

    compiled = workflow.compile(
        checkpointer=checkpointer,
        interrupt_before=interrupt,
    )

    return compiled, checkpointer


class RuleIngestionResult:
    """Result of running the rule ingestion workflow."""

    def __init__(self, state: WizardAgentState):
        self.success = state.get("success", False)
        self.rule_definition = state.get("rule_definition")
        self.cypher_queries = state.get("cypher_queries")
        self.dictionary_result = state.get("dictionary_result")
        self.analysis_result = state.get("analysis_result")
        self.validation_result = state.get("validation_result")
        self.test_results = state.get("test_results")
        self.error_message = state.get("error_message")
        self.iterations = state.get("iteration", 0)
        self.events = state.get("events", [])
        self.requires_human_input = state.get("requires_human_input", False)


def run_rule_ingestion(
    origin_country: str,
    scenario_type: str,
    receiving_countries: List[str],
    rule_text: str,
    data_categories: Optional[List[str]] = None,
    is_pii_related: bool = False,
    max_iterations: int = 10,
    thread_id: Optional[str] = None,
) -> RuleIngestionResult:
    """
    Run the rule ingestion workflow.

    Args:
        origin_country: Origin country
        scenario_type: transfer or attribute
        receiving_countries: List of receiving countries
        rule_text: Natural language rule description
        data_categories: Optional data categories for dictionary generation
        max_iterations: Max retry iterations
        thread_id: Thread ID for checkpointer (session tracking)

    Returns:
        RuleIngestionResult with all outputs
    """
    initial_state = create_initial_state(
        origin_country=origin_country,
        scenario_type=scenario_type,
        receiving_countries=receiving_countries,
        rule_text=rule_text,
        data_categories=data_categories,
        is_pii_related=is_pii_related,
        max_iterations=max_iterations,
    )

    event_store = get_event_store()
    event_store.append(
        session_id=origin_country,
        event_type=AuditEventType.WORKFLOW_STARTED,
        data={"rule_text": rule_text[:200]},
    )

    try:
        graph, checkpointer = build_rule_ingestion_graph()
        config = {
            "configurable": {"thread_id": thread_id or "default"},
            "recursion_limit": 50,
        }
        final_state = graph.invoke(initial_state, config)
        return RuleIngestionResult(final_state)

    except Exception as e:
        logger.error(f"Workflow execution failed: {e}", exc_info=True)
        error_state = initial_state.copy()
        error_state["success"] = False
        error_state["error_message"] = f"Workflow error: {str(e)}"
        return RuleIngestionResult(error_state)
