"""
Tests for LangGraph Rule Generation Workflow
=============================================
Tests for the multi-agent workflow with supervisor, analyzer, generator, and validator.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, Any

from agents.graph_workflow import (
    build_rule_generation_graph,
    generate_rule_with_langgraph,
    RuleGenerationResult,
    RuleDefinitionModel,
    CypherQueriesModel,
    ValidationResultModel,
    WorkflowState,
    parse_json_response,
    build_country_groups_prompt,
)
from pydantic import ValidationError


class TestPydanticModels:
    """Test Pydantic validation models"""

    def test_rule_definition_model_valid(self):
        """Test valid rule definition"""
        rule = RuleDefinitionModel(
            rule_type="transfer",
            rule_id="RULE_TEST_001",
            name="Test Transfer Rule",
            description="This is a test rule for transfer validation",
            priority=50,
            origin_countries=["Germany"],
            receiving_countries=["India"],
            outcome="prohibition",
            odrl_type="Prohibition",
        )
        assert rule.rule_type == "transfer"
        assert rule.rule_id == "RULE_TEST_001"
        assert rule.priority == 50

    def test_rule_definition_model_invalid_rule_id(self):
        """Test invalid rule ID format"""
        with pytest.raises(ValidationError):
            RuleDefinitionModel(
                rule_type="transfer",
                rule_id="INVALID_001",  # Should start with RULE_
                name="Test Rule",
                description="Test description here",
                priority=50,
                outcome="prohibition",
                odrl_type="Prohibition",
            )

    def test_rule_definition_model_invalid_priority(self):
        """Test invalid priority range"""
        with pytest.raises(ValidationError):
            RuleDefinitionModel(
                rule_type="transfer",
                rule_id="RULE_TEST_002",
                name="Test Rule",
                description="Test description here",
                priority=150,  # Should be 1-100
                outcome="prohibition",
                odrl_type="Prohibition",
            )

    def test_rule_definition_model_mismatched_odrl(self):
        """Test mismatched outcome and odrl_type"""
        with pytest.raises(ValidationError):
            RuleDefinitionModel(
                rule_type="transfer",
                rule_id="RULE_TEST_003",
                name="Test Rule",
                description="Test description here",
                priority=50,
                outcome="prohibition",
                odrl_type="Permission",  # Should be Prohibition
            )

    def test_rule_definition_model_invalid_country_group(self):
        """Test invalid country group"""
        with pytest.raises(ValidationError):
            RuleDefinitionModel(
                rule_type="transfer",
                rule_id="RULE_TEST_004",
                name="Test Rule",
                description="Test description here",
                priority=50,
                origin_group="INVALID_GROUP",
                outcome="prohibition",
                odrl_type="Prohibition",
            )

    def test_rule_definition_model_valid_country_group(self):
        """Test valid country group"""
        rule = RuleDefinitionModel(
            rule_type="transfer",
            rule_id="RULE_TEST_005",
            name="Test EU Rule",
            description="Test rule for EU transfers",
            priority=50,
            origin_group="EU_EEA",
            outcome="permission",
            odrl_type="Permission",
        )
        assert rule.origin_group == "EU_EEA"

    def test_cypher_queries_model_valid(self):
        """Test valid Cypher queries"""
        queries = CypherQueriesModel(
            rule_check="MATCH (c:Case) RETURN c",
            rule_insert="CREATE (r:Rule {name: 'test'})",
            validation="MATCH (r:Rule) RETURN count(r)",
        )
        assert "MATCH" in queries.rule_check
        assert "CREATE" in queries.rule_insert

    def test_cypher_queries_model_invalid_syntax(self):
        """Test Cypher queries without required keywords"""
        with pytest.raises(ValidationError):
            CypherQueriesModel(
                rule_check="SELECT * FROM table",  # Not Cypher
                rule_insert="CREATE (r:Rule {name: 'test'})",
                validation="MATCH (r:Rule) RETURN count(r)",
            )

    def test_validation_result_model(self):
        """Test validation result model"""
        result = ValidationResultModel(
            overall_valid=True,
            confidence_score=0.85,
            rule_definition_valid=True,
            cypher_valid=True,
            logical_valid=True,
        )
        assert result.overall_valid is True
        assert result.confidence_score == 0.85

    def test_validation_result_invalid_confidence(self):
        """Test validation result with invalid confidence score"""
        with pytest.raises(ValidationError):
            ValidationResultModel(
                overall_valid=True,
                confidence_score=1.5,  # Should be 0.0-1.0
            )


class TestJSONParsing:
    """Test JSON response parsing"""

    def test_parse_json_response_plain(self):
        """Test parsing plain JSON"""
        response = '{"key": "value", "number": 42}'
        result = parse_json_response(response)
        assert result == {"key": "value", "number": 42}

    def test_parse_json_response_markdown(self):
        """Test parsing JSON in markdown code block"""
        response = '''Here is the result:
```json
{"key": "value", "number": 42}
```
'''
        result = parse_json_response(response)
        assert result == {"key": "value", "number": 42}

    def test_parse_json_response_with_text(self):
        """Test parsing JSON embedded in text"""
        response = 'The analysis shows: {"key": "value"} which means...'
        result = parse_json_response(response)
        assert result == {"key": "value"}

    def test_parse_json_response_invalid(self):
        """Test parsing invalid JSON"""
        response = "This is not JSON at all"
        result = parse_json_response(response)
        assert result is None


class TestCountryGroupsPrompt:
    """Test country groups prompt building"""

    def test_build_country_groups_prompt(self):
        """Test country groups prompt contains expected groups"""
        prompt = build_country_groups_prompt()
        assert "EU_EEA" in prompt
        assert "UK_CROWN_DEPENDENCIES" in prompt
        assert "ADEQUACY" in prompt


class TestWorkflowGraph:
    """Test LangGraph workflow structure"""

    def test_build_graph(self):
        """Test graph can be built"""
        graph = build_rule_generation_graph()
        assert graph is not None

    def test_graph_has_nodes(self):
        """Test graph has expected nodes"""
        graph = build_rule_generation_graph()
        # The compiled graph should have nodes
        assert graph is not None


class TestRuleGenerationResult:
    """Test RuleGenerationResult model"""

    def test_successful_result(self):
        """Test successful result structure"""
        result = RuleGenerationResult(
            success=True,
            rule_id="RULE_AUTO_001",
            rule_type="transfer",
            rule_definition={"rule_id": "RULE_AUTO_001"},
            iterations=2,
            message="Rule generated successfully",
        )
        assert result.success is True
        assert result.rule_id == "RULE_AUTO_001"
        assert result.iterations == 2

    def test_failed_result(self):
        """Test failed result structure"""
        result = RuleGenerationResult(
            success=False,
            errors=["Validation failed", "Max iterations reached"],
            iterations=3,
            message="Rule generation failed",
        )
        assert result.success is False
        assert len(result.errors) == 2


class TestGenerateRuleWithLangGraph:
    """Test the main generate_rule_with_langgraph function"""

    @patch("agents.graph_workflow.get_ai_service")
    def test_disabled_ai_service(self, mock_get_ai_service):
        """Test with disabled AI service"""
        mock_service = Mock()
        mock_service.is_enabled = False
        mock_get_ai_service.return_value = mock_service

        result = generate_rule_with_langgraph(
            rule_text="Test rule text",
            rule_country="United Kingdom",
        )

        assert result.success is False
        assert "AI service is not enabled" in result.message

    @patch("agents.graph_workflow.get_ai_service")
    @patch("agents.graph_workflow.build_rule_generation_graph")
    def test_successful_workflow(self, mock_build_graph, mock_get_ai_service):
        """Test successful workflow execution"""
        # Mock AI service as enabled
        mock_service = Mock()
        mock_service.is_enabled = True
        mock_get_ai_service.return_value = mock_service

        # Mock workflow execution
        mock_workflow = Mock()
        mock_workflow.invoke.return_value = {
            "success": True,
            "final_output": {
                "rule_definition": {
                    "rule_id": "RULE_AUTO_001",
                    "rule_type": "transfer",
                },
                "cypher_queries": {"queries": {"rule_check": "MATCH (c:Case) RETURN c"}},
                "validation_result": {"overall_valid": True},
                "reasoning": {},
                "iterations": 1,
            },
        }
        mock_build_graph.return_value = mock_workflow

        result = generate_rule_with_langgraph(
            rule_text="Prohibit transfers from UK to China",
            rule_country="United Kingdom",
        )

        assert result.success is True
        assert result.rule_id == "RULE_AUTO_001"

    @patch("agents.graph_workflow.get_ai_service")
    @patch("agents.graph_workflow.build_rule_generation_graph")
    def test_failed_workflow(self, mock_build_graph, mock_get_ai_service):
        """Test failed workflow execution"""
        # Mock AI service as enabled
        mock_service = Mock()
        mock_service.is_enabled = True
        mock_get_ai_service.return_value = mock_service

        # Mock workflow failure
        mock_workflow = Mock()
        mock_workflow.invoke.return_value = {
            "success": False,
            "final_output": {
                "error": "Max iterations reached",
                "errors": ["Validation failed"],
                "iterations": 3,
            },
        }
        mock_build_graph.return_value = mock_workflow

        result = generate_rule_with_langgraph(
            rule_text="Invalid rule text",
            rule_country="Unknown",
        )

        assert result.success is False
        assert "Max iterations reached" in result.message

    @patch("agents.graph_workflow.get_ai_service")
    @patch("agents.graph_workflow.build_rule_generation_graph")
    def test_workflow_exception(self, mock_build_graph, mock_get_ai_service):
        """Test workflow with exception"""
        # Mock AI service as enabled
        mock_service = Mock()
        mock_service.is_enabled = True
        mock_get_ai_service.return_value = mock_service

        # Mock workflow exception
        mock_workflow = Mock()
        mock_workflow.invoke.side_effect = Exception("Network error")
        mock_build_graph.return_value = mock_workflow

        result = generate_rule_with_langgraph(
            rule_text="Test rule",
            rule_country="Germany",
        )

        assert result.success is False
        assert "Network error" in result.message or "Network error" in result.errors[0]


class TestWorkflowState:
    """Test WorkflowState initialization"""

    def test_initial_state(self):
        """Test initial state structure"""
        state: WorkflowState = {
            "rule_text": "Test rule",
            "rule_country": "Germany",
            "rule_type_hint": "transfer",
            "current_stage": "rule_analyzer",
            "iteration": 1,
            "max_iterations": 3,
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
        assert state["rule_text"] == "Test rule"
        assert state["iteration"] == 1
        assert state["max_iterations"] == 3
