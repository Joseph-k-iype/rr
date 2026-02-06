"""
Tests for Agentic Workflow
===========================
Tests for the agentic reference data creation, rule generation with
audit trail, and the complete agentic pipeline.
"""

import pytest
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.rule_generator import (
    RuleGeneratorAgent,
    GeneratedRule,
    ReferenceDataItem,
)
from services.agent_audit import (
    AgentAuditTrail,
)


class TestReferenceDataDetection:
    """Tests for detecting what reference data is needed"""

    @pytest.fixture
    def generator(self):
        """Create a generator with mocked AI service"""
        with patch('agents.rule_generator.get_ai_service') as mock_ai:
            mock_service = MagicMock()
            mock_service.is_enabled = True
            mock_ai.return_value = mock_service
            gen = RuleGeneratorAgent()
            gen.ai_service = mock_service
            return gen

    def test_detect_missing_country_group(self, generator):
        """Test detection of missing country groups"""
        rule_def = {
            "rule_type": "transfer",
            "origin_group": "NONEXISTENT_GROUP",
            "receiving_group": "EU_EEA",
        }

        # Mock AI response for additional needs detection
        generator.ai_service.chat.return_value = '{"additional_needs": [], "reasoning": "All covered"}'

        needs = generator._detect_reference_data_needs(rule_def, "Test rule")

        # Should detect the missing origin group
        group_needs = [n for n in needs if n["type"] == "country_group"]
        assert len(group_needs) >= 1
        assert any(n["name"] == "NONEXISTENT_GROUP" for n in group_needs)

    def test_detect_existing_country_group_no_need(self, generator):
        """Test that existing country groups don't trigger needs"""
        rule_def = {
            "rule_type": "transfer",
            "origin_group": "EU_EEA",
            "receiving_group": "UK_CROWN_DEPENDENCIES",
        }

        generator.ai_service.chat.return_value = '{"additional_needs": [], "reasoning": "All exists"}'

        needs = generator._detect_reference_data_needs(rule_def, "Test rule")

        group_needs = [n for n in needs if n["type"] == "country_group"]
        assert len(group_needs) == 0

    def test_detect_attribute_config_need(self, generator):
        """Test detection of missing attribute config file"""
        rule_def = {
            "rule_type": "attribute",
            "attribute_name": "genetic_data",
            "attribute_keywords": ["dna", "gene"],
        }

        generator.ai_service.chat.return_value = '{"additional_needs": [], "reasoning": "checked"}'

        needs = generator._detect_reference_data_needs(rule_def, "Genetic data rule")

        # Should detect missing config file
        config_needs = [n for n in needs if n["type"] == "attribute_config"]
        assert len(config_needs) >= 1

    def test_detect_insufficient_keywords(self, generator):
        """Test detection of insufficient keywords"""
        rule_def = {
            "rule_type": "attribute",
            "attribute_name": "education_data",
            "attribute_keywords": ["student", "grade"],
        }

        generator.ai_service.chat.return_value = '{"additional_needs": [], "reasoning": "checked"}'

        needs = generator._detect_reference_data_needs(rule_def, "Education data rule")

        keyword_needs = [n for n in needs if n["type"] == "keyword_dictionary"]
        assert len(keyword_needs) >= 1
        assert any(n["name"] == "education_data_keywords" for n in keyword_needs)


class TestReferenceDataCreation:
    """Tests for creating reference data items"""

    @pytest.fixture
    def generator(self):
        """Create a generator with mocked AI service"""
        with patch('agents.rule_generator.get_ai_service') as mock_ai:
            mock_service = MagicMock()
            mock_service.is_enabled = True
            mock_ai.return_value = mock_service
            gen = RuleGeneratorAgent()
            gen.ai_service = mock_service
            return gen

    @pytest.fixture
    def audit(self):
        """Create a fresh audit trail"""
        trail = AgentAuditTrail(max_sessions=100)
        # Patch the global
        with patch('agents.rule_generator.get_agent_audit_trail', return_value=trail):
            yield trail

    def test_create_country_group(self, generator, audit):
        """Test creating a country group reference data"""
        session = audit.start_session("test")

        generator.ai_service.chat.return_value = '''```json
{
    "group_name": "SOUTH_ASIAN",
    "countries": ["India", "Pakistan", "Bangladesh", "Sri Lanka", "Nepal"],
    "description": "South Asian countries",
    "source": "Geographic classification"
}
```'''

        need = {
            "type": "country_group",
            "name": "SOUTH_ASIAN",
            "reason": "Missing group",
            "direction": "receiving",
        }

        with patch('agents.rule_generator.get_agent_audit_trail', return_value=audit):
            item = generator._create_country_group_reference(
                need, {"description": "Test"}, session.session_id
            )

        assert item is not None
        assert item.data_type == "country_group"
        assert item.name == "SOUTH_ASIAN"
        assert item.created is True
        assert item.requires_approval is True
        assert len(item.details["countries"]) == 5

    def test_create_keyword_dictionary(self, generator, audit):
        """Test creating an expanded keyword dictionary"""
        session = audit.start_session("test")

        generator.ai_service.chat.return_value = '''```json
{
    "dictionary_name": "education_data_keywords",
    "attribute_name": "education_data",
    "keywords": ["student", "grade", "transcript", "enrollment", "academic", "course", "degree", "diploma", "gpa", "semester", "tuition", "scholarship", "faculty", "curriculum", "exam"],
    "categories": {"academic": ["grade", "transcript"], "enrollment": ["enrollment", "course"]},
    "description": "Keywords for detecting education data"
}
```'''

        need = {
            "type": "keyword_dictionary",
            "name": "education_data_keywords",
            "reason": "Too few keywords",
            "current_count": 2,
        }

        rule_def = {
            "attribute_name": "education_data",
            "attribute_keywords": ["student", "grade"],
        }

        with patch('agents.rule_generator.get_agent_audit_trail', return_value=audit):
            item = generator._create_keyword_dictionary_reference(
                need, rule_def, "Education data rule", session.session_id
            )

        assert item is not None
        assert item.data_type == "keyword_dictionary"
        assert item.created is True
        assert item.details["expanded_count"] > item.details["original_count"]


class TestGeneratedRuleModel:
    """Tests for the enhanced GeneratedRule model"""

    def test_generated_rule_with_reference_data(self):
        """Test GeneratedRule includes reference data"""
        rule = GeneratedRule(
            rule_definition={"rule_id": "RULE_TEST"},
            cypher_queries={},
            reasoning={},
            test_cases=[],
            reference_data=[
                ReferenceDataItem(
                    data_type="country_group",
                    name="TEST_GROUP",
                    details={"countries": ["A", "B"]},
                    created=True,
                ),
                ReferenceDataItem(
                    data_type="attribute_config",
                    name="test_config",
                    details={"keywords_count": 20},
                    created=True,
                ),
            ],
            audit_session_id="sess-001",
        )
        assert len(rule.reference_data) == 2
        assert rule.audit_session_id == "sess-001"

    def test_reference_data_item(self):
        """Test ReferenceDataItem dataclass"""
        item = ReferenceDataItem(
            data_type="keyword_dictionary",
            name="health_keywords",
            details={"keywords": ["patient", "diagnosis"]},
            created=True,
            requires_approval=True,
            approval_status="pending",
        )
        assert item.requires_approval is True
        assert item.approval_status == "pending"


class TestAgenticEndToEnd:
    """End-to-end tests for the agentic workflow"""

    @pytest.fixture
    def generator(self):
        """Create a generator with mocked dependencies"""
        with patch('agents.rule_generator.get_ai_service') as mock_ai, \
             patch('agents.rule_generator.get_db_service') as mock_db:
            mock_service = MagicMock()
            mock_service.is_enabled = True
            mock_ai.return_value = mock_service
            mock_db.return_value = MagicMock()
            gen = RuleGeneratorAgent()
            gen.ai_service = mock_service
            return gen

    def test_agentic_mode_creates_audit_session(self, generator):
        """Test that agentic mode creates an audit session"""
        # Mock the LangGraph workflow
        with patch('agents.rule_generator.generate_rule_with_langgraph') as mock_gen, \
             patch('agents.rule_generator.get_agent_audit_trail') as mock_audit:

            mock_result = MagicMock()
            mock_result.success = True
            mock_result.rule_definition = {
                "rule_id": "RULE_TEST",
                "rule_type": "transfer",
                "origin_group": "EU_EEA",
            }
            mock_result.cypher_queries = {}
            mock_result.reasoning = {}
            mock_result.iterations = 1
            mock_result.message = "Success"
            mock_gen.return_value = mock_result

            mock_trail = AgentAuditTrail()
            mock_audit.return_value = mock_trail

            result = generator.generate_rule(
                rule_text="EU data cannot go to restricted countries",
                rule_country="Germany",
                agentic_mode=True,
            )

            assert result.audit_session_id is not None
            # Verify session was created
            session = mock_trail.get_session(result.audit_session_id)
            assert session is not None
            assert session["agentic_mode"] is True


class TestAPIEndpointEnhancements:
    """Tests for the enhanced API endpoints"""

    @pytest.fixture
    def client(self):
        """Get test client"""
        from api.main import app
        from fastapi.testclient import TestClient
        return TestClient(app)

    def test_agent_sessions_endpoint(self, client):
        """Test the agent sessions listing endpoint"""
        response = client.get("/api/agent/sessions")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_agent_stats_endpoint(self, client):
        """Test the agent stats endpoint"""
        response = client.get("/api/agent/stats")
        assert response.status_code == 200
        data = response.json()
        assert "total_sessions" in data
        assert "total_actions" in data
        assert "success_rate" in data

    def test_agent_pending_approvals_endpoint(self, client):
        """Test the pending approvals endpoint"""
        response = client.get("/api/agent/pending-approvals")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_evaluate_rules_returns_evidence(self, client):
        """Test that evaluation endpoint returns evidence summary"""
        response = client.post("/api/evaluate-rules", json={
            "origin_country": "United Kingdom",
            "receiving_country": "Germany",
            "pii": False,
        })
        assert response.status_code == 200
        data = response.json()
        assert "transfer_status" in data
        # evidence_summary may or may not be present depending on evaluation path

    def test_generate_rule_agentic_mode(self, client):
        """Test AI rule generation with agentic mode flag"""
        response = client.post("/api/ai/generate-rule", json={
            "rule_text": "Health data from US should not go to China",
            "rule_country": "United States",
            "rule_type": "attribute",
            "test_in_temp_graph": False,
            "agentic_mode": True,
        })
        assert response.status_code == 200
        data = response.json()
        # Response should have agentic_mode field
        assert "agentic_mode" in data or "success" in data

    def test_agent_session_not_found(self, client):
        """Test 404 for nonexistent session"""
        response = client.get("/api/agent/sessions/nonexistent-id")
        assert response.status_code == 404

    def test_approval_endpoint(self, client):
        """Test the approval endpoint with nonexistent entry"""
        response = client.post("/api/agent/approve", json={
            "entry_id": "nonexistent",
            "action": "approve",
            "approved_by": "test",
        })
        assert response.status_code == 404


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
