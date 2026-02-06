"""
Tests for Agent Audit Trail
============================
Comprehensive tests for the enterprise-grade agent audit trail service.
"""

import pytest
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from services.agent_audit import (
    AgentAuditTrail,
    AgentActionType,
    AgentActionStatus,
    AgentAuditEntry,
    AgentSession,
)


class TestAgentAuditTrail:
    """Tests for the AgentAuditTrail service"""

    @pytest.fixture
    def audit(self):
        """Create a fresh audit trail for each test"""
        return AgentAuditTrail(max_sessions=100, retention_days=30)

    def test_start_session(self, audit):
        """Test starting a new audit session"""
        session = audit.start_session(
            session_type="rule_generation",
            initiator="api",
            agentic_mode=True,
            metadata={"test": True},
        )
        assert session.session_id
        assert session.correlation_id.startswith("COR-")
        assert session.session_type == "rule_generation"
        assert session.agentic_mode is True
        assert session.status == "active"

    def test_log_action(self, audit):
        """Test logging an action within a session"""
        session = audit.start_session("test")
        entry = audit.log_action(
            session_id=session.session_id,
            action_type=AgentActionType.RULE_ANALYSIS,
            agent_name="TestAgent",
            status=AgentActionStatus.STARTED,
            input_summary="Testing rule analysis",
        )
        assert entry.entry_id
        assert entry.correlation_id == session.correlation_id
        assert entry.action_type == AgentActionType.RULE_ANALYSIS
        assert entry.agent_name == "TestAgent"

    def test_complete_action(self, audit):
        """Test completing a started action with duration tracking"""
        session = audit.start_session("test")
        entry = audit.log_action(
            session_id=session.session_id,
            action_type=AgentActionType.RULE_ANALYSIS,
            agent_name="TestAgent",
        )

        time.sleep(0.01)  # Small delay for duration tracking

        audit.complete_action(
            entry_id=entry.entry_id,
            status=AgentActionStatus.COMPLETED,
            output_summary="Analysis complete",
        )

        session_data = audit.get_session(session.session_id)
        completed_entry = session_data["entries"][0]
        assert completed_entry["status"] == AgentActionStatus.COMPLETED
        assert completed_entry["duration_ms"] > 0
        assert completed_entry["output_summary"] == "Analysis complete"

    def test_complete_session(self, audit):
        """Test completing a session"""
        session = audit.start_session("test")
        audit.log_action(
            session_id=session.session_id,
            action_type=AgentActionType.RULE_ANALYSIS,
            agent_name="TestAgent",
            status=AgentActionStatus.COMPLETED,
        )

        audit.complete_session(
            session.session_id,
            summary="Test completed",
            status="completed",
        )

        session_data = audit.get_session(session.session_id)
        assert session_data["status"] == "completed"
        assert session_data["summary"] == "Test completed"
        assert session_data["completed_at"] is not None

    def test_approval_workflow(self, audit):
        """Test approve/reject workflow for pending actions"""
        session = audit.start_session("test", agentic_mode=True)
        entry = audit.log_action(
            session_id=session.session_id,
            action_type=AgentActionType.COUNTRY_GROUP_CREATION,
            agent_name="CountryGroupAgent",
            status=AgentActionStatus.PENDING_APPROVAL,
            requires_approval=True,
        )

        # Verify pending approvals
        pending = audit.get_pending_approvals()
        assert len(pending) == 1
        assert pending[0]["entry_id"] == entry.entry_id

        # Approve the action
        result = audit.approve_action(entry.entry_id, approved_by="admin")
        assert result is True

        # Verify approved
        session_data = audit.get_session(session.session_id)
        approved_entry = session_data["entries"][0]
        assert approved_entry["status"] == AgentActionStatus.APPROVED
        assert approved_entry["approved_by"] == "admin"

        # Verify no more pending
        pending = audit.get_pending_approvals()
        assert len(pending) == 0

    def test_reject_action(self, audit):
        """Test rejecting an action"""
        session = audit.start_session("test")
        entry = audit.log_action(
            session_id=session.session_id,
            action_type=AgentActionType.ATTRIBUTE_CONFIG_CREATION,
            agent_name="AttributeConfigAgent",
            status=AgentActionStatus.PENDING_APPROVAL,
            requires_approval=True,
        )

        result = audit.reject_action(
            entry.entry_id,
            rejected_by="reviewer",
            reason="Incorrect keywords",
        )
        assert result is True

        session_data = audit.get_session(session.session_id)
        rejected_entry = session_data["entries"][0]
        assert rejected_entry["status"] == AgentActionStatus.REJECTED
        assert rejected_entry["error_message"] == "Incorrect keywords"

    def test_get_recent_sessions(self, audit):
        """Test retrieving recent sessions with filtering"""
        audit.start_session("rule_generation", agentic_mode=True)
        audit.start_session("evaluation")
        audit.start_session("rule_generation")

        # All sessions
        all_sessions = audit.get_recent_sessions(limit=10)
        assert len(all_sessions) == 3

        # Filter by type
        rule_sessions = audit.get_recent_sessions(
            limit=10, session_type="rule_generation"
        )
        assert len(rule_sessions) == 2

    def test_stats(self, audit):
        """Test audit trail statistics"""
        session = audit.start_session("test", agentic_mode=True)
        audit.log_action(
            session_id=session.session_id,
            action_type=AgentActionType.RULE_ANALYSIS,
            agent_name="TestAgent",
            status=AgentActionStatus.COMPLETED,
        )
        audit.log_action(
            session_id=session.session_id,
            action_type=AgentActionType.VALIDATION,
            agent_name="TestAgent",
            status=AgentActionStatus.FAILED,
        )

        stats = audit.get_stats()
        assert stats["total_sessions"] == 1
        assert stats["total_actions"] == 2
        assert stats["agentic_sessions"] == 1

    def test_session_eviction(self, audit):
        """Test that old sessions are evicted when at capacity"""
        small_audit = AgentAuditTrail(max_sessions=3)
        ids = []
        for i in range(5):
            session = small_audit.start_session(f"test_{i}")
            ids.append(session.session_id)

        # Only 3 should remain
        all_sessions = small_audit.get_recent_sessions(limit=10)
        assert len(all_sessions) == 3

        # First 2 should be evicted
        assert small_audit.get_session(ids[0]) is None
        assert small_audit.get_session(ids[1]) is None
        assert small_audit.get_session(ids[4]) is not None

    def test_export_session(self, audit):
        """Test exporting a session as JSON"""
        session = audit.start_session("test")
        audit.log_action(
            session_id=session.session_id,
            action_type=AgentActionType.RULE_ANALYSIS,
            agent_name="TestAgent",
            status=AgentActionStatus.COMPLETED,
        )

        export = audit.export_session(session.session_id)
        assert export is not None
        import json
        parsed = json.loads(export)
        assert parsed["session_id"] == session.session_id
        assert len(parsed["entries"]) == 1

    def test_nonexistent_session(self, audit):
        """Test querying a nonexistent session"""
        result = audit.get_session("nonexistent")
        assert result is None

    def test_multiple_actions_tracking(self, audit):
        """Test tracking multiple actions in a session"""
        session = audit.start_session("rule_generation", agentic_mode=True)

        # Log multiple actions
        audit.log_action(
            session_id=session.session_id,
            action_type=AgentActionType.RULE_ANALYSIS,
            agent_name="RuleAnalyzer",
            status=AgentActionStatus.COMPLETED,
        )
        audit.log_action(
            session_id=session.session_id,
            action_type=AgentActionType.REFERENCE_DATA_DETECTION,
            agent_name="ReferenceDataDetector",
            status=AgentActionStatus.COMPLETED,
        )
        audit.log_action(
            session_id=session.session_id,
            action_type=AgentActionType.COUNTRY_GROUP_CREATION,
            agent_name="CountryGroupAgent",
            status=AgentActionStatus.PENDING_APPROVAL,
            requires_approval=True,
        )
        audit.log_action(
            session_id=session.session_id,
            action_type=AgentActionType.ATTRIBUTE_CONFIG_CREATION,
            agent_name="AttributeConfigAgent",
            status=AgentActionStatus.PENDING_APPROVAL,
            requires_approval=True,
        )

        session_data = audit.get_session(session.session_id)
        assert session_data["total_actions"] == 4
        assert session_data["pending_approvals"] == 2

    def test_thread_safety(self, audit):
        """Test that the audit trail is thread-safe"""
        import threading

        session = audit.start_session("concurrent_test")
        errors = []

        def log_action(i):
            try:
                audit.log_action(
                    session_id=session.session_id,
                    action_type=AgentActionType.RULE_ANALYSIS,
                    agent_name=f"Thread_{i}",
                    status=AgentActionStatus.COMPLETED,
                )
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=log_action, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        session_data = audit.get_session(session.session_id)
        assert session_data["total_actions"] == 10


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
