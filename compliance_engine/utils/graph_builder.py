"""
Graph Builder
=============
Builds the RulesGraph from rule definitions — the single source of truth.

RulesGraph Schema:
- Country: name
- CountryGroup: name
- Rule: rule_id, rule_type, name, description, priority, priority_order,
        origin_match_type, receiving_match_type, outcome,
        odrl_type, odrl_action, odrl_target,
        has_pii_required, requires_any_data, requires_personal_data,
        attribute_name, attribute_keywords, required_actions, enabled
- Action: name
- Permission: name
- Prohibition: name
- Duty: name, module, value

Relationships:
- Country -[:BELONGS_TO]-> CountryGroup
- Rule -[:TRIGGERED_BY_ORIGIN]-> CountryGroup | Country
- Rule -[:TRIGGERED_BY_RECEIVING]-> CountryGroup | Country
- Rule -[:EXCLUDES_RECEIVING]-> CountryGroup
- Rule -[:HAS_ACTION]-> Action
- Rule -[:HAS_PERMISSION]-> Permission
- Rule -[:HAS_PROHIBITION]-> Prohibition
- Permission -[:CAN_HAVE_DUTY]-> Duty
- Prohibition -[:CAN_HAVE_DUTY]-> Duty
"""

import logging
from typing import Set, Dict, Any

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.database import get_db_service
from rules.dictionaries.country_groups import COUNTRY_GROUPS, get_all_countries
from rules.dictionaries.rules_definitions import (
    get_enabled_case_matching_rules,
    get_enabled_transfer_rules,
    get_enabled_attribute_rules,
    RuleOutcome,
    PRIORITY_ORDER,
)
from config.settings import settings

logger = logging.getLogger(__name__)

# Map priority string to integer for graph sorting
def _priority_order(priority: str) -> int:
    return PRIORITY_ORDER.get(priority, 2)


class RulesGraphBuilder:
    """Builds the RulesGraph — the single source of truth for all rule evaluation."""

    def __init__(self, graph=None):
        self.db = get_db_service()
        self.graph = graph if graph is not None else self.db.get_rules_graph()
        self._created_duties: Set[str] = set()
        self._created_countries: Set[str] = set()

    def build(self, clear_existing: bool = True):
        """Build the complete RulesGraph."""
        logger.info("Building RulesGraph...")

        if clear_existing:
            self._clear_graph()

        self._create_indexes()
        self._build_country_groups()
        self._build_countries()
        self._build_actions()
        self._build_case_matching_rules()
        self._build_transfer_rules()
        self._build_attribute_rules()

        logger.info("RulesGraph build complete!")
        self._print_stats()

    def _clear_graph(self):
        logger.info("Clearing existing RulesGraph data...")
        try:
            self.graph.query("MATCH (n) DETACH DELETE n")
        except Exception as e:
            logger.warning(f"Error clearing graph: {e}")

    def _create_indexes(self):
        indexes = [
            "CREATE INDEX IF NOT EXISTS FOR (n:Country) ON (n.name)",
            "CREATE INDEX IF NOT EXISTS FOR (n:CountryGroup) ON (n.name)",
            "CREATE INDEX IF NOT EXISTS FOR (n:Rule) ON (n.rule_id)",
            "CREATE INDEX IF NOT EXISTS FOR (n:Action) ON (n.name)",
            "CREATE INDEX IF NOT EXISTS FOR (n:Permission) ON (n.name)",
            "CREATE INDEX IF NOT EXISTS FOR (n:Prohibition) ON (n.name)",
            "CREATE INDEX IF NOT EXISTS FOR (n:Duty) ON (n.name)",
        ]
        for index in indexes:
            try:
                self.graph.query(index)
            except Exception as e:
                logger.debug(f"Index creation note: {e}")

    def _build_country_groups(self):
        logger.info("Building country groups...")
        for group_name in COUNTRY_GROUPS.keys():
            self.graph.query("CREATE (g:CountryGroup {name: $name})", {"name": group_name})
        logger.info(f"Created {len(COUNTRY_GROUPS)} country groups")

    def _build_countries(self):
        logger.info("Building countries...")
        all_countries = get_all_countries()
        for country in all_countries:
            self.graph.query("CREATE (c:Country {name: $name})", {"name": country})
            self._created_countries.add(country)
            for group_name, group_countries in COUNTRY_GROUPS.items():
                if country in group_countries:
                    self.graph.query("""
                    MATCH (c:Country {name: $country})
                    MATCH (g:CountryGroup {name: $group})
                    CREATE (c)-[:BELONGS_TO]->(g)
                    """, {"country": country, "group": group_name})
        logger.info(f"Created {len(all_countries)} country nodes")

    def _ensure_country(self, country_name: str):
        """Create a Country node if it doesn't already exist in the graph."""
        if country_name not in self._created_countries:
            self.graph.query("MERGE (c:Country {name: $name})", {"name": country_name})
            self._created_countries.add(country_name)

    def _build_actions(self):
        logger.info("Building actions...")
        actions = ["Transfer Data", "Transfer PII", "Store in Cloud", "Process Data"]
        for name in actions:
            self.graph.query("CREATE (a:Action {name: $name})", {"name": name})
        logger.info(f"Created {len(actions)} action nodes")

    def _create_duty(self, name: str, module: str, value: str):
        duty_key = f"{name}:{module}:{value}"
        if duty_key not in self._created_duties:
            self.graph.query("""
            CREATE (d:Duty {name: $name, module: $module, value: $value})
            """, {"name": name, "module": module, "value": value})
            self._created_duties.add(duty_key)

    # -------------------------------------------------------------------------
    # SET 1: Case-Matching Rules
    # -------------------------------------------------------------------------

    def _build_case_matching_rules(self):
        logger.info("Building case-matching rules...")
        rules = get_enabled_case_matching_rules()

        for rule_key, rule in rules.items():
            origin_match_type = "group" if rule.origin_group else ("specific" if rule.origin_countries else "any")
            receiving_match_type = (
                "not_in" if rule.receiving_not_in else
                "group" if rule.receiving_group else
                ("specific" if rule.receiving_countries else "any")
            )

            self.graph.query("""
            CREATE (r:Rule {
                rule_id: $rule_id,
                rule_type: 'case_matching',
                name: $name,
                description: $description,
                priority: $priority,
                priority_order: $priority_order,
                origin_match_type: $origin_match_type,
                receiving_match_type: $receiving_match_type,
                outcome: 'permission',
                odrl_type: $odrl_type,
                odrl_action: $odrl_action,
                odrl_target: $odrl_target,
                has_pii_required: $has_pii_required,
                requires_any_data: false,
                requires_personal_data: $requires_personal_data,
                enabled: true
            })
            """, {
                "rule_id": rule.rule_id,
                "name": rule.name,
                "description": rule.description,
                "priority": rule.priority,
                "priority_order": _priority_order(rule.priority),
                "origin_match_type": origin_match_type,
                "receiving_match_type": receiving_match_type,
                "odrl_type": rule.odrl_type,
                "odrl_action": rule.odrl_action,
                "odrl_target": rule.odrl_target,
                "has_pii_required": rule.requires_pii,
                "requires_personal_data": rule.requires_personal_data,
            })

            # Permission + Duties (assessments)
            perm_name = f"Transfer Permission ({rule.name})"
            self.graph.query("""
            MATCH (r:Rule {rule_id: $rule_id})
            CREATE (p:Permission {name: $name})
            CREATE (r)-[:HAS_PERMISSION]->(p)
            """, {"rule_id": rule.rule_id, "name": perm_name})

            for assessment in rule.required_assessments.to_list():
                duty_name = f"Complete {assessment} Module"
                self._create_duty(duty_name, assessment, "Completed")
                self.graph.query("""
                MATCH (p:Permission {name: $perm_name})
                MATCH (d:Duty {name: $duty_name, module: $module, value: $value})
                CREATE (p)-[:CAN_HAVE_DUTY]->(d)
                """, {"perm_name": perm_name, "duty_name": duty_name, "module": assessment, "value": "Completed"})

            # Origin relationships
            if rule.origin_group:
                self.graph.query("""
                MATCH (r:Rule {rule_id: $rule_id})
                MATCH (g:CountryGroup {name: $group})
                CREATE (r)-[:TRIGGERED_BY_ORIGIN]->(g)
                """, {"rule_id": rule.rule_id, "group": rule.origin_group})

            if rule.origin_countries:
                for country in rule.origin_countries:
                    self._ensure_country(country)
                    self.graph.query("""
                    MATCH (r:Rule {rule_id: $rule_id})
                    MATCH (c:Country {name: $country})
                    CREATE (r)-[:TRIGGERED_BY_ORIGIN]->(c)
                    """, {"rule_id": rule.rule_id, "country": country})

            # Receiving relationships
            if rule.receiving_group:
                self.graph.query("""
                MATCH (r:Rule {rule_id: $rule_id})
                MATCH (g:CountryGroup {name: $group})
                CREATE (r)-[:TRIGGERED_BY_RECEIVING]->(g)
                """, {"rule_id": rule.rule_id, "group": rule.receiving_group})

            if rule.receiving_countries:
                for country in rule.receiving_countries:
                    self._ensure_country(country)
                    self.graph.query("""
                    MATCH (r:Rule {rule_id: $rule_id})
                    MATCH (c:Country {name: $country})
                    CREATE (r)-[:TRIGGERED_BY_RECEIVING]->(c)
                    """, {"rule_id": rule.rule_id, "country": country})

            # Receiving exclusion (receiving_not_in) — rule matches when country NOT in group
            if rule.receiving_not_in:
                for group_marker in rule.receiving_not_in:
                    self.graph.query("""
                    MATCH (r:Rule {rule_id: $rule_id})
                    MATCH (g:CountryGroup {name: $group})
                    CREATE (r)-[:EXCLUDES_RECEIVING]->(g)
                    """, {"rule_id": rule.rule_id, "group": group_marker})

            # Link to Action
            self.graph.query("""
            MATCH (r:Rule {rule_id: $rule_id})
            MATCH (a:Action {name: 'Transfer Data'})
            CREATE (r)-[:HAS_ACTION]->(a)
            """, {"rule_id": rule.rule_id})

        logger.info(f"Created {len(rules)} case-matching rules")

    # -------------------------------------------------------------------------
    # SET 2A: Transfer Rules
    # -------------------------------------------------------------------------

    def _build_transfer_rules(self):
        logger.info("Building transfer rules...")
        rules = get_enabled_transfer_rules()

        for rule_key, rule in rules.items():
            # Determine origin match type from transfer pairs or groups
            has_origin_group = bool(rule.origin_group)
            has_origin_countries = bool(rule.transfer_pairs)
            origin_match_type = "group" if has_origin_group else ("specific" if has_origin_countries else "any")

            has_receiving_group = bool(rule.receiving_group)
            has_receiving_countries = bool(rule.receiving_countries) or bool(rule.transfer_pairs)
            receiving_match_type = "group" if has_receiving_group else ("specific" if has_receiving_countries else "any")

            outcome_str = "prohibition" if rule.outcome == RuleOutcome.PROHIBITION else "permission"

            self.graph.query("""
            CREATE (r:Rule {
                rule_id: $rule_id,
                rule_type: 'transfer',
                name: $name,
                description: $description,
                priority: $priority,
                priority_order: $priority_order,
                origin_match_type: $origin_match_type,
                receiving_match_type: $receiving_match_type,
                outcome: $outcome,
                odrl_type: $odrl_type,
                odrl_action: $odrl_action,
                odrl_target: $odrl_target,
                has_pii_required: $has_pii_required,
                requires_any_data: $requires_any_data,
                requires_personal_data: false,
                required_actions: $required_actions,
                enabled: true
            })
            """, {
                "rule_id": rule.rule_id,
                "name": rule.name,
                "description": rule.description,
                "priority": rule.priority,
                "priority_order": _priority_order(rule.priority),
                "origin_match_type": origin_match_type,
                "receiving_match_type": receiving_match_type,
                "outcome": outcome_str,
                "odrl_type": rule.odrl_type,
                "odrl_action": rule.odrl_action,
                "odrl_target": rule.odrl_target,
                "has_pii_required": rule.requires_pii,
                "requires_any_data": rule.requires_any_data,
                "required_actions": list(rule.required_actions),
            })

            # Permission/Prohibition
            if rule.outcome == RuleOutcome.PROHIBITION:
                self.graph.query("""
                MATCH (r:Rule {rule_id: $rule_id})
                CREATE (pb:Prohibition {name: $name})
                CREATE (r)-[:HAS_PROHIBITION]->(pb)
                """, {"rule_id": rule.rule_id, "name": rule.name})
                for action in rule.required_actions:
                    self._create_duty(action, "action", "required")
                    self.graph.query("""
                    MATCH (pb:Prohibition {name: $prohib_name})
                    MATCH (d:Duty {name: $duty_name})
                    CREATE (pb)-[:CAN_HAVE_DUTY]->(d)
                    """, {"prohib_name": rule.name, "duty_name": action})
            else:
                self.graph.query("""
                MATCH (r:Rule {rule_id: $rule_id})
                CREATE (p:Permission {name: $name})
                CREATE (r)-[:HAS_PERMISSION]->(p)
                """, {"rule_id": rule.rule_id, "name": rule.name})

            # Origin group
            if rule.origin_group:
                self.graph.query("""
                MATCH (r:Rule {rule_id: $rule_id})
                MATCH (g:CountryGroup {name: $group})
                CREATE (r)-[:TRIGGERED_BY_ORIGIN]->(g)
                """, {"rule_id": rule.rule_id, "group": rule.origin_group})

            # Receiving group
            if rule.receiving_group:
                self.graph.query("""
                MATCH (r:Rule {rule_id: $rule_id})
                MATCH (g:CountryGroup {name: $group})
                CREATE (r)-[:TRIGGERED_BY_RECEIVING]->(g)
                """, {"rule_id": rule.rule_id, "group": rule.receiving_group})

            # Specific receiving countries
            if rule.receiving_countries:
                for country in rule.receiving_countries:
                    self._ensure_country(country)
                    self.graph.query("""
                    MATCH (r:Rule {rule_id: $rule_id})
                    MATCH (c:Country {name: $country})
                    CREATE (r)-[:TRIGGERED_BY_RECEIVING]->(c)
                    """, {"rule_id": rule.rule_id, "country": country})

            # Transfer pairs → Country-level relationships
            if rule.transfer_pairs:
                origins = set()
                destinations = set()
                for origin, receiving in rule.transfer_pairs:
                    origins.add(origin)
                    destinations.add(receiving)
                for country in origins:
                    self._ensure_country(country)
                    self.graph.query("""
                    MATCH (r:Rule {rule_id: $rule_id})
                    MATCH (c:Country {name: $country})
                    MERGE (r)-[:TRIGGERED_BY_ORIGIN]->(c)
                    """, {"rule_id": rule.rule_id, "country": country})
                for country in destinations:
                    self._ensure_country(country)
                    self.graph.query("""
                    MATCH (r:Rule {rule_id: $rule_id})
                    MATCH (c:Country {name: $country})
                    MERGE (r)-[:TRIGGERED_BY_RECEIVING]->(c)
                    """, {"rule_id": rule.rule_id, "country": country})

            # Link to Action
            action_name = "Transfer PII" if rule.requires_pii else "Transfer Data"
            self.graph.query("""
            MATCH (r:Rule {rule_id: $rule_id})
            MATCH (a:Action {name: $action_name})
            CREATE (r)-[:HAS_ACTION]->(a)
            """, {"rule_id": rule.rule_id, "action_name": action_name})

        logger.info(f"Created {len(rules)} transfer rules")

    # -------------------------------------------------------------------------
    # SET 2B: Attribute Rules
    # -------------------------------------------------------------------------

    def _build_attribute_rules(self):
        logger.info("Building attribute rules...")
        rules = get_enabled_attribute_rules()

        for rule_key, rule in rules.items():
            origin_match_type = "group" if rule.origin_group else ("specific" if rule.origin_countries else "any")
            receiving_match_type = "group" if rule.receiving_group else ("specific" if rule.receiving_countries else "any")
            outcome_str = "prohibition" if rule.outcome == RuleOutcome.PROHIBITION else "permission"

            self.graph.query("""
            CREATE (r:Rule {
                rule_id: $rule_id,
                rule_type: 'attribute',
                name: $name,
                description: $description,
                priority: $priority,
                priority_order: $priority_order,
                origin_match_type: $origin_match_type,
                receiving_match_type: $receiving_match_type,
                outcome: $outcome,
                odrl_type: $odrl_type,
                odrl_action: $odrl_action,
                odrl_target: $odrl_target,
                has_pii_required: $has_pii_required,
                requires_any_data: false,
                requires_personal_data: false,
                attribute_name: $attribute_name,
                attribute_keywords: $attribute_keywords,
                enabled: true
            })
            """, {
                "rule_id": rule.rule_id,
                "name": rule.name,
                "description": rule.description,
                "priority": rule.priority,
                "priority_order": _priority_order(rule.priority),
                "origin_match_type": origin_match_type,
                "receiving_match_type": receiving_match_type,
                "outcome": outcome_str,
                "odrl_type": rule.odrl_type,
                "odrl_action": rule.odrl_action,
                "odrl_target": rule.odrl_target,
                "has_pii_required": rule.requires_pii,
                "attribute_name": rule.attribute_name,
                "attribute_keywords": list(rule.attribute_keywords),
            })

            # Prohibition/Permission
            if rule.outcome == RuleOutcome.PROHIBITION:
                self.graph.query("""
                MATCH (r:Rule {rule_id: $rule_id})
                CREATE (pb:Prohibition {name: $name})
                CREATE (r)-[:HAS_PROHIBITION]->(pb)
                """, {"rule_id": rule.rule_id, "name": rule.name})

            # Origin relationships
            if rule.origin_group:
                self.graph.query("""
                MATCH (r:Rule {rule_id: $rule_id})
                MATCH (g:CountryGroup {name: $group})
                CREATE (r)-[:TRIGGERED_BY_ORIGIN]->(g)
                """, {"rule_id": rule.rule_id, "group": rule.origin_group})

            if rule.origin_countries:
                for country in rule.origin_countries:
                    self._ensure_country(country)
                    self.graph.query("""
                    MATCH (r:Rule {rule_id: $rule_id})
                    MATCH (c:Country {name: $country})
                    CREATE (r)-[:TRIGGERED_BY_ORIGIN]->(c)
                    """, {"rule_id": rule.rule_id, "country": country})

            # Receiving relationships
            if rule.receiving_group:
                self.graph.query("""
                MATCH (r:Rule {rule_id: $rule_id})
                MATCH (g:CountryGroup {name: $group})
                CREATE (r)-[:TRIGGERED_BY_RECEIVING]->(g)
                """, {"rule_id": rule.rule_id, "group": rule.receiving_group})

            if rule.receiving_countries:
                for country in rule.receiving_countries:
                    self._ensure_country(country)
                    self.graph.query("""
                    MATCH (r:Rule {rule_id: $rule_id})
                    MATCH (c:Country {name: $country})
                    CREATE (r)-[:TRIGGERED_BY_RECEIVING]->(c)
                    """, {"rule_id": rule.rule_id, "country": country})

            # Link to Action
            self.graph.query("""
            MATCH (r:Rule {rule_id: $rule_id})
            MATCH (a:Action {name: 'Transfer Data'})
            CREATE (r)-[:HAS_ACTION]->(a)
            """, {"rule_id": rule.rule_id})

        logger.info(f"Created {len(rules)} attribute rules")

    # -------------------------------------------------------------------------
    # Dynamic rule addition (wizard/sandbox)
    # -------------------------------------------------------------------------

    def add_transfer_rule(self, rule_def: dict) -> bool:
        """Add a single transfer rule to the graph from AI-generated definition."""
        try:
            origin_match_type = "group" if rule_def.get('origin_group') else (
                "specific" if rule_def.get('origin_countries') else "any"
            )
            receiving_match_type = "group" if rule_def.get('receiving_group') else (
                "specific" if rule_def.get('receiving_countries') else "any"
            )
            priority = rule_def.get('priority', 'medium')
            outcome = rule_def.get('outcome', 'prohibition')

            self.graph.query("""
            MERGE (r:Rule {rule_id: $rule_id})
            SET r.rule_type = 'transfer',
                r.name = $name,
                r.description = $description,
                r.priority = $priority,
                r.priority_order = $priority_order,
                r.origin_match_type = $origin_match_type,
                r.receiving_match_type = $receiving_match_type,
                r.outcome = $outcome,
                r.odrl_type = $odrl_type,
                r.odrl_action = $odrl_action,
                r.odrl_target = $odrl_target,
                r.has_pii_required = $has_pii_required,
                r.requires_any_data = $requires_any_data,
                r.requires_personal_data = false,
                r.required_actions = $required_actions,
                r.enabled = true
            """, {
                "rule_id": rule_def.get('rule_id'),
                "name": rule_def.get('name', ''),
                "description": rule_def.get('description', ''),
                "priority": priority,
                "priority_order": _priority_order(priority),
                "origin_match_type": origin_match_type,
                "receiving_match_type": receiving_match_type,
                "outcome": outcome,
                "odrl_type": rule_def.get('odrl_type', 'Prohibition' if outcome == 'prohibition' else 'Permission'),
                "odrl_action": rule_def.get('odrl_action', 'transfer'),
                "odrl_target": rule_def.get('odrl_target', 'Data'),
                "has_pii_required": rule_def.get('requires_pii', False),
                "requires_any_data": rule_def.get('requires_any_data', False),
                "required_actions": rule_def.get('required_actions', []),
            })

            # Permission/Prohibition
            rule_name = rule_def.get('name', rule_def.get('rule_id'))
            if outcome == 'prohibition':
                self.graph.query("""
                MATCH (r:Rule {rule_id: $rule_id})
                MERGE (pb:Prohibition {name: $name})
                MERGE (r)-[:HAS_PROHIBITION]->(pb)
                """, {"rule_id": rule_def.get('rule_id'), "name": rule_name})
                for action in rule_def.get('required_actions', []):
                    self._create_duty(action, "action", "required")
                    self.graph.query("""
                    MATCH (pb:Prohibition {name: $prohib_name})
                    MATCH (d:Duty {name: $duty_name})
                    MERGE (pb)-[:CAN_HAVE_DUTY]->(d)
                    """, {"prohib_name": rule_name, "duty_name": action})
            else:
                self.graph.query("""
                MATCH (r:Rule {rule_id: $rule_id})
                MERGE (p:Permission {name: $name})
                MERGE (r)-[:HAS_PERMISSION]->(p)
                """, {"rule_id": rule_def.get('rule_id'), "name": rule_name})

            # Origin
            if rule_def.get('origin_group'):
                self.graph.query("""
                MATCH (r:Rule {rule_id: $rule_id})
                MATCH (g:CountryGroup {name: $group})
                MERGE (r)-[:TRIGGERED_BY_ORIGIN]->(g)
                """, {"rule_id": rule_def.get('rule_id'), "group": rule_def['origin_group']})
            if rule_def.get('origin_countries'):
                for country in rule_def['origin_countries']:
                    self._ensure_country(country)
                    self.graph.query("""
                    MATCH (r:Rule {rule_id: $rule_id})
                    MATCH (c:Country {name: $country})
                    MERGE (r)-[:TRIGGERED_BY_ORIGIN]->(c)
                    """, {"rule_id": rule_def.get('rule_id'), "country": country})

            # Receiving
            if rule_def.get('receiving_group'):
                self.graph.query("""
                MATCH (r:Rule {rule_id: $rule_id})
                MATCH (g:CountryGroup {name: $group})
                MERGE (r)-[:TRIGGERED_BY_RECEIVING]->(g)
                """, {"rule_id": rule_def.get('rule_id'), "group": rule_def['receiving_group']})
            if rule_def.get('receiving_countries'):
                for country in rule_def['receiving_countries']:
                    self._ensure_country(country)
                    self.graph.query("""
                    MATCH (r:Rule {rule_id: $rule_id})
                    MATCH (c:Country {name: $country})
                    MERGE (r)-[:TRIGGERED_BY_RECEIVING]->(c)
                    """, {"rule_id": rule_def.get('rule_id'), "country": country})

            # Action
            action_name = "Transfer PII" if rule_def.get('requires_pii') else "Transfer Data"
            self.graph.query("""
            MATCH (r:Rule {rule_id: $rule_id})
            MATCH (a:Action {name: $action_name})
            MERGE (r)-[:HAS_ACTION]->(a)
            """, {"rule_id": rule_def.get('rule_id'), "action_name": action_name})

            logger.info(f"Added transfer rule: {rule_def.get('rule_id')}")
            return True
        except Exception as e:
            logger.error(f"Failed to add transfer rule: {e}")
            return False

    def add_attribute_rule(self, rule_def: dict) -> bool:
        """Add a single attribute rule to the graph from AI-generated definition."""
        try:
            origin_match_type = "group" if rule_def.get('origin_group') else (
                "specific" if rule_def.get('origin_countries') else "any"
            )
            receiving_match_type = "group" if rule_def.get('receiving_group') else (
                "specific" if rule_def.get('receiving_countries') else "any"
            )
            priority = rule_def.get('priority', 'medium')
            outcome = rule_def.get('outcome', 'prohibition')

            self.graph.query("""
            MERGE (r:Rule {rule_id: $rule_id})
            SET r.rule_type = 'attribute',
                r.name = $name,
                r.description = $description,
                r.priority = $priority,
                r.priority_order = $priority_order,
                r.origin_match_type = $origin_match_type,
                r.receiving_match_type = $receiving_match_type,
                r.outcome = $outcome,
                r.odrl_type = $odrl_type,
                r.odrl_action = $odrl_action,
                r.odrl_target = $odrl_target,
                r.has_pii_required = $has_pii_required,
                r.requires_any_data = false,
                r.requires_personal_data = false,
                r.attribute_name = $attribute_name,
                r.attribute_keywords = $attribute_keywords,
                r.enabled = true
            """, {
                "rule_id": rule_def.get('rule_id'),
                "name": rule_def.get('name', ''),
                "description": rule_def.get('description', ''),
                "priority": priority,
                "priority_order": _priority_order(priority),
                "origin_match_type": origin_match_type,
                "receiving_match_type": receiving_match_type,
                "outcome": outcome,
                "odrl_type": rule_def.get('odrl_type', 'Prohibition' if outcome == 'prohibition' else 'Permission'),
                "odrl_action": rule_def.get('odrl_action', 'transfer'),
                "odrl_target": rule_def.get('odrl_target', 'Data'),
                "has_pii_required": rule_def.get('requires_pii', False),
                "attribute_name": rule_def.get('attribute_name', ''),
                "attribute_keywords": rule_def.get('attribute_keywords', []),
            })

            # Prohibition
            rule_name = rule_def.get('name', rule_def.get('rule_id'))
            if outcome == 'prohibition':
                self.graph.query("""
                MATCH (r:Rule {rule_id: $rule_id})
                MERGE (pb:Prohibition {name: $name})
                MERGE (r)-[:HAS_PROHIBITION]->(pb)
                """, {"rule_id": rule_def.get('rule_id'), "name": rule_name})
            else:
                self.graph.query("""
                MATCH (r:Rule {rule_id: $rule_id})
                MERGE (p:Permission {name: $name})
                MERGE (r)-[:HAS_PERMISSION]->(p)
                """, {"rule_id": rule_def.get('rule_id'), "name": rule_name})

            # Origin
            if rule_def.get('origin_group'):
                self.graph.query("""
                MATCH (r:Rule {rule_id: $rule_id})
                MATCH (g:CountryGroup {name: $group})
                MERGE (r)-[:TRIGGERED_BY_ORIGIN]->(g)
                """, {"rule_id": rule_def.get('rule_id'), "group": rule_def['origin_group']})
            if rule_def.get('origin_countries'):
                for country in rule_def['origin_countries']:
                    self._ensure_country(country)
                    self.graph.query("""
                    MATCH (r:Rule {rule_id: $rule_id})
                    MATCH (c:Country {name: $country})
                    MERGE (r)-[:TRIGGERED_BY_ORIGIN]->(c)
                    """, {"rule_id": rule_def.get('rule_id'), "country": country})

            # Receiving
            if rule_def.get('receiving_group'):
                self.graph.query("""
                MATCH (r:Rule {rule_id: $rule_id})
                MATCH (g:CountryGroup {name: $group})
                MERGE (r)-[:TRIGGERED_BY_RECEIVING]->(g)
                """, {"rule_id": rule_def.get('rule_id'), "group": rule_def['receiving_group']})
            if rule_def.get('receiving_countries'):
                for country in rule_def['receiving_countries']:
                    self._ensure_country(country)
                    self.graph.query("""
                    MATCH (r:Rule {rule_id: $rule_id})
                    MATCH (c:Country {name: $country})
                    MERGE (r)-[:TRIGGERED_BY_RECEIVING]->(c)
                    """, {"rule_id": rule_def.get('rule_id'), "country": country})

            # Action
            self.graph.query("""
            MATCH (r:Rule {rule_id: $rule_id})
            MATCH (a:Action {name: 'Transfer Data'})
            MERGE (r)-[:HAS_ACTION]->(a)
            """, {"rule_id": rule_def.get('rule_id')})

            logger.info(f"Added attribute rule: {rule_def.get('rule_id')}")
            return True
        except Exception as e:
            logger.error(f"Failed to add attribute rule: {e}")
            return False

    def _print_stats(self):
        stats = self.db.get_graph_stats(settings.database.rules_graph_name)
        logger.info(f"RulesGraph stats: {stats['node_count']} nodes, {stats['edge_count']} edges")


def build_rules_graph(clear_existing: bool = True):
    """Build the rules graph (convenience function)"""
    builder = RulesGraphBuilder()
    builder.build(clear_existing)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    build_rules_graph()
