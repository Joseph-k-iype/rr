"""Agents module - AI-powered rule generation with LangGraph"""
from .ai_service import get_ai_service, AIService, AIAuthenticationError, AIRequestError
from .rule_generator import get_rule_generator, RuleGeneratorAgent, GeneratedRule
from .graph_workflow import (
    generate_rule_with_langgraph,
    RuleGenerationResult,
    build_rule_generation_graph,
    RuleDefinitionModel,
    CypherQueriesModel,
    ValidationResultModel,
)
from .prompts import (
    SUPERVISOR_SYSTEM_PROMPT,
    RULE_ANALYZER_SYSTEM_PROMPT,
    CYPHER_GENERATOR_SYSTEM_PROMPT,
    VALIDATOR_SYSTEM_PROMPT,
)

__all__ = [
    # AI Service
    "get_ai_service",
    "AIService",
    "AIAuthenticationError",
    "AIRequestError",
    # Rule Generator
    "get_rule_generator",
    "RuleGeneratorAgent",
    "GeneratedRule",
    # LangGraph Workflow
    "generate_rule_with_langgraph",
    "RuleGenerationResult",
    "build_rule_generation_graph",
    # Pydantic Models
    "RuleDefinitionModel",
    "CypherQueriesModel",
    "ValidationResultModel",
    # Prompts
    "SUPERVISOR_SYSTEM_PROMPT",
    "RULE_ANALYZER_SYSTEM_PROMPT",
    "CYPHER_GENERATOR_SYSTEM_PROMPT",
    "VALIDATOR_SYSTEM_PROMPT",
]
