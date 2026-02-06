"""
Agent Audit Trail Service
=========================
Enterprise-grade audit trail for all agentic operations.
Tracks agent actions with correlation IDs, timestamps, inputs/outputs,
and approval status for full traceability.
"""

import uuid
import time
import logging
import json
import threading
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from enum import Enum
from collections import OrderedDict

logger = logging.getLogger(__name__)


class AgentActionType(str, Enum):
    """Types of agent actions"""
    RULE_ANALYSIS = "rule_analysis"
    CYPHER_GENERATION = "cypher_generation"
    VALIDATION = "validation"
    REFERENCE_DATA_DETECTION = "reference_data_detection"
    COUNTRY_GROUP_CREATION = "country_group_creation"
    ATTRIBUTE_CONFIG_CREATION = "attribute_config_creation"
    KEYWORD_DICTIONARY_CREATION = "keyword_dictionary_creation"
    RULE_TESTING = "rule_testing"
    RULE_EXPORT = "rule_export"
    PRECEDENT_SEARCH = "precedent_search"
    EVIDENCE_COMPILATION = "evidence_compilation"
    SUPERVISOR_DECISION = "supervisor_decision"


class AgentActionStatus(str, Enum):
    """Status of an agent action"""
    STARTED = "started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    SKIPPED = "skipped"


@dataclass
class AgentAuditEntry:
    """Single audit entry for an agent action"""
    entry_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    correlation_id: str = ""
    session_id: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    action_type: str = ""
    agent_name: str = ""
    status: str = AgentActionStatus.STARTED
    input_summary: str = ""
    output_summary: str = ""
    input_data: Optional[Dict[str, Any]] = None
    output_data: Optional[Dict[str, Any]] = None
    duration_ms: float = 0.0
    error_message: Optional[str] = None
    requires_approval: bool = False
    approved_by: Optional[str] = None
    approval_timestamp: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary, excluding None values"""
        result = asdict(self)
        return {k: v for k, v in result.items() if v is not None}


@dataclass
class AgentSession:
    """Tracks a complete agentic session with multiple actions"""
    session_id: str = field(default_factory=lambda: str(uuid.uuid4())[:16])
    correlation_id: str = field(default_factory=lambda: f"COR-{uuid.uuid4().hex[:10].upper()}")
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    completed_at: Optional[str] = None
    session_type: str = ""  # e.g., "rule_generation", "evaluation"
    initiator: str = "api"  # "api", "ui", "cli", "scheduled"
    status: str = "active"
    entries: List[AgentAuditEntry] = field(default_factory=list)
    summary: Optional[str] = None
    total_actions: int = 0
    successful_actions: int = 0
    failed_actions: int = 0
    pending_approvals: int = 0
    agentic_mode: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to summary dictionary"""
        return {
            "session_id": self.session_id,
            "correlation_id": self.correlation_id,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
            "session_type": self.session_type,
            "initiator": self.initiator,
            "status": self.status,
            "summary": self.summary,
            "total_actions": self.total_actions,
            "successful_actions": self.successful_actions,
            "failed_actions": self.failed_actions,
            "pending_approvals": self.pending_approvals,
            "agentic_mode": self.agentic_mode,
            "entries": [e.to_dict() for e in self.entries],
            "metadata": self.metadata,
        }


class AgentAuditTrail:
    """
    Enterprise-grade audit trail for agent operations.

    Thread-safe, with configurable retention and export capabilities.
    Tracks all agent actions with full context for compliance and traceability.
    """

    def __init__(self, max_sessions: int = 10000, retention_days: int = 90):
        self._lock = threading.Lock()
        self._sessions: OrderedDict[str, AgentSession] = OrderedDict()
        self._max_sessions = max_sessions
        self._retention_days = retention_days
        self._active_timers: Dict[str, float] = {}
        logger.info(
            f"Agent audit trail initialized (max_sessions={max_sessions}, "
            f"retention_days={retention_days})"
        )

    def start_session(
        self,
        session_type: str,
        initiator: str = "api",
        agentic_mode: bool = False,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> AgentSession:
        """Start a new audit session"""
        session = AgentSession(
            session_type=session_type,
            initiator=initiator,
            agentic_mode=agentic_mode,
            metadata=metadata or {},
        )

        with self._lock:
            # Evict old sessions if at capacity
            while len(self._sessions) >= self._max_sessions:
                self._sessions.popitem(last=False)

            self._sessions[session.session_id] = session

        logger.info(
            f"Audit session started: {session.session_id} "
            f"(type={session_type}, correlation={session.correlation_id}, "
            f"agentic={agentic_mode})"
        )
        return session

    def log_action(
        self,
        session_id: str,
        action_type: str,
        agent_name: str,
        status: str = AgentActionStatus.STARTED,
        input_summary: str = "",
        output_summary: str = "",
        input_data: Optional[Dict[str, Any]] = None,
        output_data: Optional[Dict[str, Any]] = None,
        requires_approval: bool = False,
        error_message: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> AgentAuditEntry:
        """Log an agent action within a session"""
        with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                logger.warning(f"Session {session_id} not found, creating orphan entry")
                session = self.start_session("unknown")

            entry = AgentAuditEntry(
                correlation_id=session.correlation_id,
                session_id=session_id,
                action_type=action_type,
                agent_name=agent_name,
                status=status,
                input_summary=input_summary,
                output_summary=output_summary,
                input_data=input_data,
                output_data=output_data,
                requires_approval=requires_approval,
                error_message=error_message,
                metadata=metadata or {},
            )

            session.entries.append(entry)
            session.total_actions += 1

            if status == AgentActionStatus.COMPLETED:
                session.successful_actions += 1
            elif status == AgentActionStatus.FAILED:
                session.failed_actions += 1
            elif requires_approval:
                session.pending_approvals += 1

            # Start timer for duration tracking
            self._active_timers[entry.entry_id] = time.time()

        logger.info(
            f"[{session.correlation_id}] Agent action: {action_type} "
            f"by {agent_name} - {status} "
            f"{'(requires approval)' if requires_approval else ''}"
        )
        return entry

    def complete_action(
        self,
        entry_id: str,
        status: str = AgentActionStatus.COMPLETED,
        output_summary: str = "",
        output_data: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None,
    ):
        """Complete a previously started action"""
        with self._lock:
            start_time = self._active_timers.pop(entry_id, None)
            duration_ms = (time.time() - start_time) * 1000 if start_time else 0.0

            for session in self._sessions.values():
                for entry in session.entries:
                    if entry.entry_id == entry_id:
                        entry.status = status
                        entry.duration_ms = duration_ms
                        if output_summary:
                            entry.output_summary = output_summary
                        if output_data:
                            entry.output_data = output_data
                        if error_message:
                            entry.error_message = error_message

                        # Update session counters
                        if status == AgentActionStatus.COMPLETED:
                            session.successful_actions += 1
                        elif status == AgentActionStatus.FAILED:
                            session.failed_actions += 1

                        logger.info(
                            f"[{session.correlation_id}] Action completed: "
                            f"{entry.action_type} - {status} ({duration_ms:.1f}ms)"
                        )
                        return

    def complete_session(
        self,
        session_id: str,
        summary: Optional[str] = None,
        status: str = "completed",
    ):
        """Complete an audit session"""
        with self._lock:
            session = self._sessions.get(session_id)
            if session:
                session.completed_at = datetime.now().isoformat()
                session.status = status
                if summary:
                    session.summary = summary

                logger.info(
                    f"Audit session completed: {session_id} "
                    f"(actions={session.total_actions}, "
                    f"success={session.successful_actions}, "
                    f"failed={session.failed_actions}, "
                    f"pending_approvals={session.pending_approvals})"
                )

    def approve_action(
        self,
        entry_id: str,
        approved_by: str = "system",
    ):
        """Approve a pending action"""
        with self._lock:
            for session in self._sessions.values():
                for entry in session.entries:
                    if entry.entry_id == entry_id:
                        entry.status = AgentActionStatus.APPROVED
                        entry.approved_by = approved_by
                        entry.approval_timestamp = datetime.now().isoformat()
                        session.pending_approvals = max(
                            0, session.pending_approvals - 1
                        )
                        logger.info(
                            f"[{session.correlation_id}] Action approved: "
                            f"{entry.action_type} by {approved_by}"
                        )
                        return True
            return False

    def reject_action(
        self,
        entry_id: str,
        rejected_by: str = "system",
        reason: str = "",
    ):
        """Reject a pending action"""
        with self._lock:
            for session in self._sessions.values():
                for entry in session.entries:
                    if entry.entry_id == entry_id:
                        entry.status = AgentActionStatus.REJECTED
                        entry.approved_by = rejected_by
                        entry.approval_timestamp = datetime.now().isoformat()
                        entry.error_message = reason
                        session.pending_approvals = max(
                            0, session.pending_approvals - 1
                        )
                        logger.info(
                            f"[{session.correlation_id}] Action rejected: "
                            f"{entry.action_type} by {rejected_by} - {reason}"
                        )
                        return True
            return False

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get a session by ID"""
        with self._lock:
            session = self._sessions.get(session_id)
            return session.to_dict() if session else None

    def get_session_entries(self, session_id: str) -> List[Dict[str, Any]]:
        """Get all entries for a session"""
        with self._lock:
            session = self._sessions.get(session_id)
            if session:
                return [e.to_dict() for e in session.entries]
            return []

    def get_recent_sessions(
        self,
        limit: int = 50,
        session_type: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Get recent sessions with optional filtering"""
        with self._lock:
            sessions = list(self._sessions.values())
            sessions.reverse()  # Most recent first

            if session_type:
                sessions = [s for s in sessions if s.session_type == session_type]
            if status:
                sessions = [s for s in sessions if s.status == status]

            return [s.to_dict() for s in sessions[:limit]]

    def get_pending_approvals(self) -> List[Dict[str, Any]]:
        """Get all entries pending approval"""
        pending = []
        with self._lock:
            for session in self._sessions.values():
                for entry in session.entries:
                    if entry.status == AgentActionStatus.PENDING_APPROVAL:
                        pending.append({
                            **entry.to_dict(),
                            "session_type": session.session_type,
                            "session_correlation_id": session.correlation_id,
                        })
        return pending

    def get_stats(self) -> Dict[str, Any]:
        """Get audit trail statistics"""
        with self._lock:
            total_sessions = len(self._sessions)
            total_actions = sum(s.total_actions for s in self._sessions.values())
            total_success = sum(s.successful_actions for s in self._sessions.values())
            total_failed = sum(s.failed_actions for s in self._sessions.values())
            total_pending = sum(s.pending_approvals for s in self._sessions.values())
            agentic_sessions = sum(
                1 for s in self._sessions.values() if s.agentic_mode
            )

            return {
                "total_sessions": total_sessions,
                "total_actions": total_actions,
                "successful_actions": total_success,
                "failed_actions": total_failed,
                "pending_approvals": total_pending,
                "agentic_sessions": agentic_sessions,
                "success_rate": (
                    total_success / total_actions if total_actions > 0 else 0.0
                ),
            }

    def cleanup_expired(self):
        """Remove sessions older than retention period"""
        cutoff = datetime.now() - timedelta(days=self._retention_days)
        cutoff_str = cutoff.isoformat()

        with self._lock:
            expired = [
                sid for sid, s in self._sessions.items()
                if s.created_at < cutoff_str
            ]
            for sid in expired:
                del self._sessions[sid]

            if expired:
                logger.info(f"Cleaned up {len(expired)} expired audit sessions")

    def export_session(self, session_id: str) -> Optional[str]:
        """Export a session as JSON for compliance reporting"""
        session_data = self.get_session(session_id)
        if session_data:
            return json.dumps(session_data, indent=2, default=str)
        return None


# Singleton
_audit_trail: Optional[AgentAuditTrail] = None


def get_agent_audit_trail() -> AgentAuditTrail:
    """Get the agent audit trail instance"""
    global _audit_trail
    if _audit_trail is None:
        from config.settings import settings
        _audit_trail = AgentAuditTrail(
            retention_days=getattr(
                settings.ai, 'agent_audit_retention_days', 90
            ),
        )
    return _audit_trail
