"""
Rule Ingestion Workflow
========================
LangGraph StateGraph for wizard steps 4-5.
Entry -> Supervisor -> {agents} -> Supervisor -> ... -> complete/fail

Uses MemorySaver checkpointer and interrupt_before for human-in-the-loop.
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from agents.state.wizard_state import WizardAgentState, create_initial_state
from agents.nodes.supervisor import supervisor_node
from agents.nodes.rule_analyzer import rule_analyzer_node
from agents.nodes.cypher_generator import cypher_generator_node
from agents.nodes.validator import validator_node
from agents.nodes.data_dictionary import data_dictionary_node
from agents.nodes.reference_data import reference_data_node
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
    """Route based on supervisor decision."""
    phase = state.get("current_phase", "fail")

    # Check max iterations
    if state["iteration"] >= state["max_iterations"] and phase not in ("complete", "fail"):
        return "fail"

    valid_routes = {
        "rule_analyzer", "data_dictionary", "cypher_generator",
        "validator", "reference_data", "human_review", "complete", "fail"
    }

    if phase in valid_routes:
        return phase
    return "fail"


def route_after_validation(state: WizardAgentState) -> str:
    """Route after validation."""
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
        "human_review": "human_review",
        "complete": "complete",
        "fail": "fail",
    }
    for agent in ["rule_analyzer", "data_dictionary", "cypher_generator", "reference_data"]:
        workflow.add_conditional_edges(agent, _route_agent, agent_route_map)

    # Validator has special routing
    workflow.add_conditional_edges(
        "validator",
        route_after_validation,
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

    # Compile with checkpointer
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
    max_iterations: int = 3,
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
        config = {"configurable": {"thread_id": thread_id or "default"}}
        final_state = graph.invoke(initial_state, config)
        return RuleIngestionResult(final_state)

    except Exception as e:
        logger.error(f"Workflow execution failed: {e}", exc_info=True)
        error_state = initial_state.copy()
        error_state["success"] = False
        error_state["error_message"] = f"Workflow error: {str(e)}"
        return RuleIngestionResult(error_state)
