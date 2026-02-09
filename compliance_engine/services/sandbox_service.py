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
        self._sandbox_dictionaries: Dict[str, Dict[str, Any]] = {}  # graph_name -> dictionary_result
        self._registered_configs: Dict[str, str] = {}  # graph_name -> attribute_name (for cleanup)
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

    def add_rule_to_sandbox(
        self,
        graph_name: str,
        rule_def: Dict[str, Any],
        dictionary_result: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Add a rule to the sandbox graph.

        Args:
            graph_name: Sandbox graph name
            rule_def: Rule definition dictionary
            dictionary_result: AI-generated dictionary with keywords for attribute detection

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

            # Store rule definition and dictionary for sandbox evaluation
            if success:
                self._sandbox_rules[graph_name] = rule_def
                if dictionary_result:
                    self._sandbox_dictionaries[graph_name] = dictionary_result

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
        is tested alongside existing rules. For attribute rules, also
        registers the rule's keywords with the attribute detector so
        custom attributes can be detected from metadata.
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

                    # Register custom attribute keywords with the detector
                    # so metadata matching works for user-created rules
                    dictionary = self._sandbox_dictionaries.get(graph_name)
                    self._register_attribute_detection(rule_def, dictionary, graph_name)
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

    def _register_attribute_detection(
        self,
        rule_def: Dict[str, Any],
        dictionary_result: Optional[Dict[str, Any]],
        graph_name: str,
    ):
        """
        Register custom attribute keywords with the AttributeDetector so
        user-created attribute rules can match against metadata.

        Merges keywords from:
        1. rule_def.attribute_keywords (from the AI rule analyzer)
        2. dictionary_result.dictionaries.*.keywords (from the AI dictionary agent)
        """
        from services.attribute_detector import get_attribute_detector, AttributeDetectionConfig

        attr_name = rule_def.get('attribute_name', '')
        if not attr_name:
            return

        # Collect all keywords from the rule definition
        all_keywords = list(rule_def.get('attribute_keywords', []))

        # Merge keywords from the AI-generated dictionary
        if dictionary_result:
            dictionaries = dictionary_result.get('dictionaries', {})
            for cat_name, cat_data in dictionaries.items():
                if isinstance(cat_data, dict):
                    all_keywords.extend(cat_data.get('keywords', []))
                    # Also include sub-category terms
                    for sub_terms in cat_data.get('sub_categories', {}).values():
                        if isinstance(sub_terms, list):
                            all_keywords.extend(sub_terms)
                    # Include synonym values
                    for synonyms in cat_data.get('synonyms', {}).values():
                        if isinstance(synonyms, list):
                            all_keywords.extend(synonyms)
                    # Include expanded acronyms
                    for full_form in cat_data.get('acronyms', {}).values():
                        if isinstance(full_form, str):
                            all_keywords.append(full_form)

            # Also include PII dictionary terms if present
            pii_dict = dictionary_result.get('pii_dictionary', {})
            if isinstance(pii_dict, dict):
                all_keywords.extend(pii_dict.get('keywords', []))

        # Collect patterns
        all_patterns = list(rule_def.get('attribute_patterns', []))
        if dictionary_result:
            all_patterns.extend(dictionary_result.get('internal_patterns', []))

        # De-duplicate while preserving order
        seen = set()
        unique_keywords = []
        for kw in all_keywords:
            kw_lower = str(kw).lower().strip()
            if kw_lower and kw_lower not in seen:
                seen.add(kw_lower)
                unique_keywords.append(kw_lower)

        if not unique_keywords:
            logger.warning(f"No keywords found for attribute '{attr_name}' — detection may fail")
            return

        detector = get_attribute_detector()
        config = AttributeDetectionConfig(
            name=attr_name,
            keywords=unique_keywords,
            patterns=all_patterns,
            case_sensitive=False,
            word_boundaries=False,
            enabled=True,
        )
        detector.add_config(config)
        self._registered_configs[graph_name] = attr_name
        logger.info(
            f"Registered attribute detection for '{attr_name}' with "
            f"{len(unique_keywords)} keywords and {len(all_patterns)} patterns"
        )

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
        For attribute rules, also permanently registers the detection config.

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

                    # Permanently register attribute detection keywords
                    # so the main evaluator can detect this attribute type
                    dictionary = self._sandbox_dictionaries.get(graph_name)
                    self._register_attribute_detection(rule_def, dictionary, graph_name)
                    # Remove from cleanup tracking — this config should persist
                    self._registered_configs.pop(graph_name, None)
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
        """Delete a sandbox graph and associated rule/dictionary data."""
        try:
            self.db.delete_temp_graph(graph_name)

            # Remove from active sandboxes
            sessions_to_remove = [
                sid for sid, gn in self._active_sandboxes.items()
                if gn == graph_name
            ]
            for sid in sessions_to_remove:
                del self._active_sandboxes[sid]

            # Remove stored rule definition and dictionary
            self._sandbox_rules.pop(graph_name, None)
            self._sandbox_dictionaries.pop(graph_name, None)

            # Remove registered attribute config from detector
            attr_name = self._registered_configs.pop(graph_name, None)
            if attr_name:
                from services.attribute_detector import get_attribute_detector
                detector = get_attribute_detector()
                detector._configs.pop(attr_name, None)
                logger.info(f"Unregistered attribute detection config '{attr_name}'")

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
