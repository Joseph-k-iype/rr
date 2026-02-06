"""
LangGraph Workflow for Rule Generation
======================================
Multi-agent orchestration using LangGraph with:
- Supervisor Agent
- Rule Analyzer Agent (Chain of Thought)
- Cypher Generator Agent (Mixture of Experts)
- Validator Agent
- Conditional loops with max 3 iterations
"""

import json
import logging
import re
from typing import Dict, Any, Optional, List, TypedDict, Annotated, Literal
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, field_validator, ValidationError

# LangGraph imports
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages

from agents.ai_service import get_ai_service, AIRequestError
from agents.prompts import (
    SUPERVISOR_SYSTEM_PROMPT,
    RULE_ANALYZER_SYSTEM_PROMPT,
    CYPHER_GENERATOR_SYSTEM_PROMPT,
    VALIDATOR_SYSTEM_PROMPT,
    RULE_ANALYZER_USER_TEMPLATE,
    CYPHER_GENERATOR_USER_TEMPLATE,
    VALIDATOR_USER_TEMPLATE,
    SUPERVISOR_USER_TEMPLATE,
)
from rules.dictionaries.country_groups import COUNTRY_GROUPS, get_all_countries

logger = logging.getLogger(__name__)


# =============================================================================
# PYDANTIC VALIDATION MODELS
# =============================================================================

class RuleDefinitionModel(BaseModel):
    """Pydantic model for validating rule definitions"""
    rule_type: Literal["transfer", "attribute"]
    rule_id: str = Field(..., pattern=r"^RULE_.*$")
    name: str = Field(..., min_length=3, max_length=200)
    description: str = Field(..., min_length=10)
    priority: int = Field(..., ge=1, le=100)
    origin_countries: Optional[List[str]] = None
    origin_group: Optional[str] = None
    receiving_countries: Optional[List[str]] = None
    receiving_group: Optional[str] = None
    outcome: Literal["permission", "prohibition"]
    requires_pii: bool = False
    attribute_name: Optional[str] = None
    attribute_keywords: Optional[List[str]] = None
    required_actions: List[str] = Field(default_factory=list)
    odrl_type: Literal["Permission", "Prohibition"]
    odrl_action: str = "transfer"
    odrl_target: str = "Data"

    @field_validator('origin_group', 'receiving_group')
    @classmethod
    def validate_country_group(cls, v):
        if v is not None and v not in COUNTRY_GROUPS and v != "ANY":
            raise ValueError(f"Unknown country group: {v}")
        return v

    @field_validator('odrl_type')
    @classmethod
    def validate_odrl_matches_outcome(cls, v, info):
        outcome = info.data.get('outcome')
        if outcome == 'prohibition' and v != 'Prohibition':
            raise ValueError("odrl_type must be 'Prohibition' for prohibition outcome")
        if outcome == 'permission' and v != 'Permission':
            raise ValueError("odrl_type must be 'Permission' for permission outcome")
        return v


class CypherQueriesModel(BaseModel):
    """Pydantic model for validating Cypher queries"""
    rule_check: str = Field(..., min_length=10)
    rule_insert: str = Field(..., min_length=10)
    validation: str = Field(..., min_length=10)

    @field_validator('rule_check', 'rule_insert', 'validation')
    @classmethod
    def validate_cypher_syntax(cls, v):
        # Basic Cypher syntax validation
        if not any(keyword in v.upper() for keyword in ['MATCH', 'CREATE', 'MERGE', 'RETURN']):
            raise ValueError(f"Invalid Cypher query - missing required keywords")
        return v


class ValidationResultModel(BaseModel):
    """Pydantic model for validation results"""
    overall_valid: bool
    confidence_score: float = Field(..., ge=0.0, le=1.0)
    rule_definition_valid: bool = True
    cypher_valid: bool = True
    logical_valid: bool = True
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    suggested_fixes: List[str] = Field(default_factory=list)


# =============================================================================
# WORKFLOW STATE
# =============================================================================

class WorkflowState(TypedDict):
    """State maintained throughout the workflow"""
    # Input
    rule_text: str
    rule_country: str
    rule_type_hint: Optional[str]

    # Processing state
    current_stage: str
    iteration: int
    max_iterations: int

    # Agent outputs
    rule_definition: Optional[Dict[str, Any]]
    cypher_queries: Optional[Dict[str, Any]]
    validation_result: Optional[Dict[str, Any]]

    # Chain of thought reasoning
    analyzer_reasoning: Optional[Dict[str, Any]]
    generator_reasoning: Optional[Dict[str, Any]]

    # Feedback for retry
    feedback: str
    previous_errors: List[str]

    # Final output
    success: bool
    final_output: Optional[Dict[str, Any]]
    error_message: Optional[str]


# =============================================================================
# AGENT NODES
# =============================================================================

def build_country_groups_prompt() -> str:
    """Build prompt section listing available country groups"""
    lines = []
    for name, countries in COUNTRY_GROUPS.items():
        sample = list(countries)[:5]
        lines.append(f"- {name}: {', '.join(sample)}{'...' if len(countries) > 5 else ''}")
    return "\n".join(lines)


def parse_json_response(response: str) -> Optional[Dict[str, Any]]:
    """Parse JSON from LLM response, handling markdown code blocks"""
    # Try to extract JSON from markdown code blocks
    json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', response)
    if json_match:
        json_str = json_match.group(1)
    else:
        json_str = response

    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        # Try to find JSON object in text
        start = json_str.find('{')
        end = json_str.rfind('}') + 1
        if start != -1 and end > start:
            try:
                return json.loads(json_str[start:end])
            except json.JSONDecodeError:
                pass
    return None


def supervisor_node(state: WorkflowState) -> WorkflowState:
    """Supervisor agent - coordinates workflow"""
    ai_service = get_ai_service()

    # Build context for supervisor
    agent_outputs = {
        "rule_definition": state.get("rule_definition"),
        "cypher_queries": state.get("cypher_queries"),
        "validation_result": state.get("validation_result"),
    }

    validation_status = "Not yet validated"
    if state.get("validation_result"):
        v = state["validation_result"]
        validation_status = f"Valid: {v.get('overall_valid', False)}, Confidence: {v.get('confidence_score', 0)}"

    user_prompt = SUPERVISOR_USER_TEMPLATE.format(
        rule_text=state["rule_text"],
        current_stage=state["current_stage"],
        iteration=state["iteration"],
        max_iterations=state["max_iterations"],
        agent_outputs=json.dumps(agent_outputs, indent=2, default=str),
        validation_status=validation_status,
    )

    try:
        response = ai_service.chat(user_prompt, SUPERVISOR_SYSTEM_PROMPT)
        parsed = parse_json_response(response)

        if parsed:
            next_agent = parsed.get("next_agent", "fail")
            feedback = parsed.get("feedback", "")
            state["feedback"] = feedback

            logger.info(f"Supervisor decision: {next_agent}, reasoning: {parsed.get('reasoning', '')}")
        else:
            next_agent = "fail"
            state["error_message"] = "Supervisor failed to produce valid response"

    except AIRequestError as e:
        logger.error(f"Supervisor error: {e}")
        next_agent = "fail"
        state["error_message"] = str(e)

    state["current_stage"] = next_agent
    return state


def rule_analyzer_node(state: WorkflowState) -> WorkflowState:
    """Rule Analyzer agent - Chain of Thought analysis"""
    ai_service = get_ai_service()

    system_prompt = RULE_ANALYZER_SYSTEM_PROMPT.format(
        country_groups=build_country_groups_prompt()
    )

    user_prompt = RULE_ANALYZER_USER_TEMPLATE.format(
        rule_text=state["rule_text"],
        rule_country=state["rule_country"],
        rule_type_hint=state.get("rule_type_hint", "Not specified"),
        feedback=state.get("feedback", "None"),
    )

    try:
        response = ai_service.chat(user_prompt, system_prompt)
        parsed = parse_json_response(response)

        if parsed:
            # Store chain of thought reasoning
            state["analyzer_reasoning"] = parsed.get("chain_of_thought", {})

            # Validate rule definition with Pydantic
            rule_def = parsed.get("rule_definition", {})
            try:
                validated = RuleDefinitionModel(**rule_def)
                state["rule_definition"] = validated.model_dump()
                state["current_stage"] = "cypher_generator"
                logger.info(f"Rule analyzed successfully: {rule_def.get('rule_id')}")
            except ValidationError as ve:
                errors = [str(e) for e in ve.errors()]
                state["previous_errors"].extend(errors)
                state["feedback"] = f"Validation errors: {errors}"
                state["current_stage"] = "supervisor"
                logger.warning(f"Rule validation failed: {errors}")
        else:
            state["previous_errors"].append("Failed to parse analyzer response")
            state["current_stage"] = "supervisor"

    except AIRequestError as e:
        logger.error(f"Rule analyzer error: {e}")
        state["previous_errors"].append(str(e))
        state["current_stage"] = "supervisor"

    return state


def cypher_generator_node(state: WorkflowState) -> WorkflowState:
    """Cypher Generator agent - Mixture of Experts"""
    ai_service = get_ai_service()

    user_prompt = CYPHER_GENERATOR_USER_TEMPLATE.format(
        rule_definition=json.dumps(state["rule_definition"], indent=2),
        feedback=state.get("feedback", "None"),
    )

    try:
        response = ai_service.chat(user_prompt, CYPHER_GENERATOR_SYSTEM_PROMPT)
        parsed = parse_json_response(response)

        if parsed:
            # Store expert reasoning
            state["generator_reasoning"] = parsed.get("expert_analysis", {})

            # Validate Cypher queries with Pydantic
            queries = parsed.get("cypher_queries", {})
            try:
                validated = CypherQueriesModel(**queries)
                state["cypher_queries"] = {
                    "queries": validated.model_dump(),
                    "params": parsed.get("query_params", {}),
                    "optimization_notes": parsed.get("optimization_notes", []),
                }
                state["current_stage"] = "validator"
                logger.info("Cypher queries generated successfully")
            except ValidationError as ve:
                errors = [str(e) for e in ve.errors()]
                state["previous_errors"].extend(errors)
                state["feedback"] = f"Cypher validation errors: {errors}"
                state["current_stage"] = "supervisor"
                logger.warning(f"Cypher validation failed: {errors}")
        else:
            state["previous_errors"].append("Failed to parse generator response")
            state["current_stage"] = "supervisor"

    except AIRequestError as e:
        logger.error(f"Cypher generator error: {e}")
        state["previous_errors"].append(str(e))
        state["current_stage"] = "supervisor"

    return state


def validator_node(state: WorkflowState) -> WorkflowState:
    """Validator agent - comprehensive validation"""
    ai_service = get_ai_service()

    previous_errors_str = "\n".join(state.get("previous_errors", [])) or "None"

    user_prompt = VALIDATOR_USER_TEMPLATE.format(
        rule_text=state["rule_text"],
        rule_definition=json.dumps(state["rule_definition"], indent=2),
        cypher_queries=json.dumps(state["cypher_queries"], indent=2),
        iteration=state["iteration"],
        max_iterations=state["max_iterations"],
        previous_errors=f"Previous errors:\n{previous_errors_str}",
    )

    try:
        response = ai_service.chat(user_prompt, VALIDATOR_SYSTEM_PROMPT)
        parsed = parse_json_response(response)

        if parsed:
            # Build validation result
            val_results = parsed.get("validation_results", {})

            try:
                validated = ValidationResultModel(
                    overall_valid=parsed.get("overall_valid", False),
                    confidence_score=parsed.get("confidence_score", 0.0),
                    rule_definition_valid=val_results.get("rule_definition", {}).get("valid", False),
                    cypher_valid=val_results.get("cypher_queries", {}).get("valid", False),
                    logical_valid=val_results.get("logical", {}).get("valid", False),
                    errors=sum([
                        val_results.get("rule_definition", {}).get("errors", []),
                        val_results.get("cypher_queries", {}).get("errors", []),
                        val_results.get("logical", {}).get("errors", []),
                    ], []),
                    warnings=sum([
                        val_results.get("rule_definition", {}).get("warnings", []),
                        val_results.get("cypher_queries", {}).get("warnings", []),
                        val_results.get("logical", {}).get("warnings", []),
                    ], []),
                    suggested_fixes=parsed.get("suggested_fixes", []),
                )

                state["validation_result"] = validated.model_dump()

                if validated.overall_valid and validated.confidence_score >= 0.7:
                    state["current_stage"] = "complete"
                    state["success"] = True
                    logger.info(f"Validation passed with confidence {validated.confidence_score}")
                else:
                    state["iteration"] += 1
                    if state["iteration"] >= state["max_iterations"]:
                        state["current_stage"] = "fail"
                        state["error_message"] = f"Max iterations ({state['max_iterations']}) reached without passing validation"
                    else:
                        state["feedback"] = f"Validation failed. Fixes needed: {validated.suggested_fixes}"
                        state["previous_errors"].extend(validated.errors)
                        state["current_stage"] = "supervisor"
                    logger.warning(f"Validation failed, iteration {state['iteration']}")

            except ValidationError as ve:
                state["previous_errors"].extend([str(e) for e in ve.errors()])
                state["current_stage"] = "supervisor"
        else:
            state["previous_errors"].append("Failed to parse validator response")
            state["current_stage"] = "supervisor"

    except AIRequestError as e:
        logger.error(f"Validator error: {e}")
        state["previous_errors"].append(str(e))
        state["current_stage"] = "supervisor"

    return state


def complete_node(state: WorkflowState) -> WorkflowState:
    """Finalize successful workflow"""
    state["success"] = True
    state["final_output"] = {
        "rule_definition": state["rule_definition"],
        "cypher_queries": state["cypher_queries"],
        "validation_result": state["validation_result"],
        "reasoning": {
            "analyzer": state.get("analyzer_reasoning"),
            "generator": state.get("generator_reasoning"),
        },
        "iterations": state["iteration"],
        "timestamp": datetime.now().isoformat(),
    }
    logger.info("Workflow completed successfully")
    return state


def fail_node(state: WorkflowState) -> WorkflowState:
    """Handle workflow failure"""
    state["success"] = False
    if not state.get("error_message"):
        state["error_message"] = "Workflow failed after max iterations"
    state["final_output"] = {
        "error": state["error_message"],
        "partial_rule": state.get("rule_definition"),
        "partial_cypher": state.get("cypher_queries"),
        "errors": state.get("previous_errors", []),
        "iterations": state["iteration"],
        "timestamp": datetime.now().isoformat(),
    }
    logger.error(f"Workflow failed: {state['error_message']}")
    return state


# =============================================================================
# CONDITIONAL ROUTING
# =============================================================================

def route_from_supervisor(state: WorkflowState) -> str:
    """Route based on supervisor decision"""
    stage = state.get("current_stage", "fail")

    # Check max iterations
    if state["iteration"] >= state["max_iterations"] and stage not in ["complete", "fail"]:
        return "fail"

    if stage == "rule_analyzer":
        return "rule_analyzer"
    elif stage == "cypher_generator":
        return "cypher_generator"
    elif stage == "validator":
        return "validator"
    elif stage == "complete":
        return "complete"
    else:
        return "fail"


def route_after_validation(state: WorkflowState) -> str:
    """Route after validation"""
    stage = state.get("current_stage", "supervisor")

    if stage == "complete":
        return "complete"
    elif stage == "fail":
        return "fail"
    else:
        return "supervisor"


# =============================================================================
# BUILD WORKFLOW GRAPH
# =============================================================================

def build_rule_generation_graph() -> StateGraph:
    """Build the LangGraph workflow for rule generation"""

    # Create the graph
    workflow = StateGraph(WorkflowState)

    # Add nodes
    workflow.add_node("supervisor", supervisor_node)
    workflow.add_node("rule_analyzer", rule_analyzer_node)
    workflow.add_node("cypher_generator", cypher_generator_node)
    workflow.add_node("validator", validator_node)
    workflow.add_node("complete", complete_node)
    workflow.add_node("fail", fail_node)

    # Set entry point
    workflow.set_entry_point("rule_analyzer")

    # Add edges from rule_analyzer
    workflow.add_conditional_edges(
        "rule_analyzer",
        lambda s: s.get("current_stage", "supervisor"),
        {
            "cypher_generator": "cypher_generator",
            "supervisor": "supervisor",
        }
    )

    # Add edges from cypher_generator
    workflow.add_conditional_edges(
        "cypher_generator",
        lambda s: s.get("current_stage", "supervisor"),
        {
            "validator": "validator",
            "supervisor": "supervisor",
        }
    )

    # Add edges from validator
    workflow.add_conditional_edges(
        "validator",
        route_after_validation,
        {
            "complete": "complete",
            "fail": "fail",
            "supervisor": "supervisor",
        }
    )

    # Add edges from supervisor
    workflow.add_conditional_edges(
        "supervisor",
        route_from_supervisor,
        {
            "rule_analyzer": "rule_analyzer",
            "cypher_generator": "cypher_generator",
            "validator": "validator",
            "complete": "complete",
            "fail": "fail",
        }
    )

    # Terminal nodes
    workflow.add_edge("complete", END)
    workflow.add_edge("fail", END)

    return workflow.compile()


# =============================================================================
# PUBLIC API
# =============================================================================

class RuleGenerationResult(BaseModel):
    """Result of rule generation workflow"""
    success: bool
    rule_id: Optional[str] = None
    rule_type: Optional[str] = None
    rule_definition: Optional[Dict[str, Any]] = None
    cypher_queries: Optional[Dict[str, Any]] = None
    validation_result: Optional[Dict[str, Any]] = None
    reasoning: Optional[Dict[str, Any]] = None
    iterations: int = 0
    errors: List[str] = Field(default_factory=list)
    message: str = ""


def generate_rule_with_langgraph(
    rule_text: str,
    rule_country: str,
    rule_type_hint: Optional[str] = None,
    max_iterations: int = 3,
) -> RuleGenerationResult:
    """
    Generate a rule using the LangGraph workflow.

    Args:
        rule_text: Natural language rule description
        rule_country: Primary country the rule relates to
        rule_type_hint: Optional hint for rule type
        max_iterations: Maximum retry iterations (default 3)

    Returns:
        RuleGenerationResult with the generated rule or errors
    """
    ai_service = get_ai_service()

    if not ai_service.is_enabled:
        return RuleGenerationResult(
            success=False,
            message="AI service is not enabled",
            errors=["AI service disabled in configuration"],
        )

    # Initialize state
    initial_state: WorkflowState = {
        "rule_text": rule_text,
        "rule_country": rule_country,
        "rule_type_hint": rule_type_hint,
        "current_stage": "rule_analyzer",
        "iteration": 1,
        "max_iterations": max_iterations,
        "rule_definition": None,
        "cypher_queries": None,
        "validation_result": None,
        "analyzer_reasoning": None,
        "generator_reasoning": None,
        "feedback": "",
        "previous_errors": [],
        "success": False,
        "final_output": None,
        "error_message": None,
    }

    try:
        # Build and run the workflow
        workflow = build_rule_generation_graph()
        final_state = workflow.invoke(initial_state)

        # Build result
        if final_state.get("success"):
            output = final_state.get("final_output", {})
            rule_def = output.get("rule_definition", {})

            return RuleGenerationResult(
                success=True,
                rule_id=rule_def.get("rule_id"),
                rule_type=rule_def.get("rule_type"),
                rule_definition=rule_def,
                cypher_queries=output.get("cypher_queries"),
                validation_result=output.get("validation_result"),
                reasoning=output.get("reasoning"),
                iterations=output.get("iterations", 1),
                message="Rule generated successfully",
            )
        else:
            output = final_state.get("final_output", {})
            return RuleGenerationResult(
                success=False,
                rule_definition=output.get("partial_rule"),
                cypher_queries=output.get("partial_cypher"),
                iterations=output.get("iterations", 1),
                errors=output.get("errors", []),
                message=output.get("error", "Rule generation failed"),
            )

    except Exception as e:
        logger.error(f"Workflow execution failed: {e}", exc_info=True)
        return RuleGenerationResult(
            success=False,
            message=f"Workflow error: {str(e)}",
            errors=[str(e)],
        )
