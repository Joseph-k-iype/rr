"""
Sandbox Service
================
Manages sandbox graph lifecycle for safe rule testing.
Creates temporary copies of RulesGraph, runs evaluations, promotes to main.
"""

import logging
import uuid
from typing import Optional, Dict, Any

from services.database import get_db_service
from utils.graph_builder import RulesGraphBuilder
from config.settings import settings

logger = logging.getLogger(__name__)


class SandboxService:
    """Manages sandbox graph lifecycle for rule testing."""

    _instance: Optional['SandboxService'] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self.db = get_db_service()
        self._active_sandboxes: Dict[str, str] = {}  # session_id -> graph_name
        self._sandbox_rules: Dict[str, Dict[str, Any]] = {}  # graph_name -> rule_def
        self._initialized = True
        logger.info("Sandbox Service initialized")

    def create_sandbox(self, session_id: str) -> str:
        """
        Create a sandbox graph by copying the main RulesGraph structure.

        Args:
            session_id: Wizard session ID

        Returns:
            Name of the created sandbox graph
        """
        graph_name = f"sandbox_{uuid.uuid4().hex[:8]}"

        try:
            # Get a temporary graph from the database (returns tuple of graph, full_name)
            temp_graph, full_graph_name = self.db.get_temp_graph(graph_name)

            # Build the rules graph structure in the sandbox
            builder = RulesGraphBuilder(graph=temp_graph)
            builder.build(clear_existing=True)

            self._active_sandboxes[session_id] = full_graph_name
            logger.info(f"Created sandbox graph '{full_graph_name}' for session {session_id}")
            return full_graph_name

        except Exception as e:
            logger.error(f"Failed to create sandbox: {e}")
            raise

    def add_rule_to_sandbox(self, graph_name: str, rule_def: Dict[str, Any]) -> bool:
        """
        Add a rule to the sandbox graph.

        Args:
            graph_name: Sandbox graph name
            rule_def: Rule definition dictionary

        Returns:
            True if rule was added successfully
        """
        try:
            graph = self.db.db.select_graph(graph_name)
            builder = RulesGraphBuilder(graph=graph)

            rule_type = rule_def.get('rule_type', 'transfer')
            if rule_type == 'attribute':
                success = builder.add_attribute_rule(rule_def)
            else:
                success = builder.add_transfer_rule(rule_def)

            # Store rule definition for sandbox evaluation
            if success:
                self._sandbox_rules[graph_name] = rule_def

            return success

        except Exception as e:
            logger.error(f"Failed to add rule to sandbox '{graph_name}': {e}")
            return False

    def evaluate_in_sandbox(
        self,
        graph_name: str,
        origin_country: str,
        receiving_country: str,
        pii: bool = False,
        purposes: Optional[list] = None,
        process_l1: Optional[list] = None,
        process_l2: Optional[list] = None,
        process_l3: Optional[list] = None,
        personal_data_names: Optional[list] = None,
        metadata: Optional[dict] = None,
    ) -> Dict[str, Any]:
        """
        Run evaluation against the sandbox graph.

        Includes the sandbox rule in the evaluator so the new rule
        is tested alongside existing rules.
        """
        from services.rules_evaluator import RulesEvaluator

        try:
            # Build extra rules from stored sandbox rule definition
            extra_transfer = {}
            extra_attribute = {}
            rule_def = self._sandbox_rules.get(graph_name)
            if rule_def:
                rule_type = rule_def.get('rule_type', 'transfer')
                if rule_type == 'attribute':
                    attr_rule = self._build_attribute_rule(rule_def)
                    extra_attribute[rule_def['rule_id']] = attr_rule
                else:
                    transfer_rule = self._build_transfer_rule(rule_def)
                    extra_transfer[rule_def['rule_id']] = transfer_rule

            evaluator = RulesEvaluator(
                extra_transfer_rules=extra_transfer,
                extra_attribute_rules=extra_attribute,
            )
            result = evaluator.evaluate(
                origin_country=origin_country,
                receiving_country=receiving_country,
                pii=pii,
                purposes=purposes,
                process_l1=process_l1,
                process_l2=process_l2,
                process_l3=process_l3,
                personal_data_names=personal_data_names,
                metadata=metadata,
            )
            return result if isinstance(result, dict) else result.model_dump() if hasattr(result, 'model_dump') else {"result": str(result)}

        except Exception as e:
            logger.error(f"Sandbox evaluation failed: {e}")
            return {
                "transfer_status": "INSUFFICIENT_DATA",
                "message": f"Sandbox evaluation error: {str(e)}",
                "error": str(e),
            }

    def _build_transfer_rule(self, rule_def: Dict[str, Any]):
        """Build a TransferRule dataclass from a rule definition dict."""
        from rules.dictionaries.rules_definitions import TransferRule, RuleOutcome

        outcome_str = rule_def.get('outcome', 'permission')
        outcome = RuleOutcome.PROHIBITION if outcome_str == 'prohibition' else RuleOutcome.PERMISSION

        receiving = rule_def.get('receiving_countries')
        return TransferRule(
            rule_id=rule_def['rule_id'],
            name=rule_def.get('name', ''),
            description=rule_def.get('description', ''),
            priority=rule_def.get('priority', 50),
            origin_group=rule_def.get('origin_group'),
            receiving_group=rule_def.get('receiving_group'),
            receiving_countries=frozenset(receiving) if receiving else None,
            outcome=outcome,
            requires_pii=rule_def.get('requires_pii', False),
            requires_any_data=rule_def.get('requires_any_data', False),
            required_actions=rule_def.get('required_actions', []),
            odrl_type=rule_def.get('odrl_type', 'Prohibition' if outcome == RuleOutcome.PROHIBITION else 'Permission'),
            enabled=True,
        )

    def _build_attribute_rule(self, rule_def: Dict[str, Any]):
        """Build an AttributeRule dataclass from a rule definition dict."""
        from rules.dictionaries.rules_definitions import AttributeRule, RuleOutcome

        outcome_str = rule_def.get('outcome', 'prohibition')
        outcome = RuleOutcome.PROHIBITION if outcome_str == 'prohibition' else RuleOutcome.PERMISSION

        origin = rule_def.get('origin_countries')
        receiving = rule_def.get('receiving_countries')
        return AttributeRule(
            rule_id=rule_def['rule_id'],
            name=rule_def.get('name', ''),
            description=rule_def.get('description', ''),
            priority=rule_def.get('priority', 50),
            attribute_name=rule_def.get('attribute_name', ''),
            attribute_keywords=rule_def.get('attribute_keywords', []),
            attribute_patterns=rule_def.get('attribute_patterns', []),
            origin_countries=frozenset(origin) if origin else None,
            origin_group=rule_def.get('origin_group'),
            receiving_countries=frozenset(receiving) if receiving else None,
            receiving_group=rule_def.get('receiving_group'),
            outcome=outcome,
            requires_pii=rule_def.get('requires_pii', False),
            odrl_type=rule_def.get('odrl_type', 'Prohibition' if outcome == RuleOutcome.PROHIBITION else 'Permission'),
            enabled=True,
        )

    def promote_to_main(self, graph_name: str, rule_def: Dict[str, Any]) -> bool:
        """
        Promote a tested rule from sandbox to the main RulesGraph.

        Adds the rule to both the FalkorDB graph and the in-memory
        rule dictionaries so it takes effect in the evaluator immediately.

        Args:
            graph_name: Sandbox graph name
            rule_def: Rule definition to add to main graph

        Returns:
            True if promotion was successful
        """
        from rules.dictionaries.rules_definitions import TRANSFER_RULES, ATTRIBUTE_RULES

        try:
            main_builder = RulesGraphBuilder()
            rule_type = rule_def.get('rule_type', 'transfer')

            if rule_type == 'attribute':
                success = main_builder.add_attribute_rule(rule_def)
                if success:
                    attr_rule = self._build_attribute_rule(rule_def)
                    ATTRIBUTE_RULES[rule_def['rule_id']] = attr_rule
            else:
                success = main_builder.add_transfer_rule(rule_def)
                if success:
                    transfer_rule = self._build_transfer_rule(rule_def)
                    TRANSFER_RULES[rule_def['rule_id']] = transfer_rule

            if success:
                logger.info(f"Rule {rule_def.get('rule_id')} promoted to main graph and registered in evaluator")
            return success

        except Exception as e:
            logger.error(f"Failed to promote rule to main graph: {e}")
            return False

    def cleanup_sandbox(self, graph_name: str):
        """Delete a sandbox graph and associated rule data."""
        try:
            self.db.delete_temp_graph(graph_name)

            # Remove from active sandboxes
            sessions_to_remove = [
                sid for sid, gn in self._active_sandboxes.items()
                if gn == graph_name
            ]
            for sid in sessions_to_remove:
                del self._active_sandboxes[sid]

            # Remove stored rule definition
            self._sandbox_rules.pop(graph_name, None)

            logger.info(f"Cleaned up sandbox graph '{graph_name}'")

        except Exception as e:
            logger.error(f"Failed to cleanup sandbox '{graph_name}': {e}")

    def cleanup_session(self, session_id: str):
        """Cleanup sandbox for a session."""
        graph_name = self._active_sandboxes.get(session_id)
        if graph_name:
            self.cleanup_sandbox(graph_name)

    def get_sandbox_for_session(self, session_id: str) -> Optional[str]:
        """Get the sandbox graph name for a session."""
        return self._active_sandboxes.get(session_id)


_sandbox_service: Optional[SandboxService] = None


def get_sandbox_service() -> SandboxService:
    """Get the sandbox service instance."""
    global _sandbox_service
    if _sandbox_service is None:
        _sandbox_service = SandboxService()
    return _sandbox_service
