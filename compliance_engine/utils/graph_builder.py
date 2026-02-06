"""
Graph Builder
=============
Builds the RulesGraph from rule definitions.

RulesGraph Schema (matching mermaid diagram):
- Country: name
- CountryGroup: name
- Rule: rule_id, priority, origin_match_type, receiving_match_type, odrl_type, has_pii_required
- Action: name
- Permission: name
- Prohibition: name
- Duty: name, module, value

Relationships:
- Country -[:BELONGS_TO]-> CountryGroup
- Rule -[:HAS_ACTION]-> Action
- Rule -[:HAS_PERMISSION]-> Permission
- Rule -[:HAS_PROHIBITION]-> Prohibition
- Rule -[:TRIGGERED_BY_ORIGIN]-> CountryGroup
- Rule -[:TRIGGERED_BY_RECEIVING]-> CountryGroup
- Permission -[:CAN_HAVE_DUTY]-> Duty
- Prohibition -[:CAN_HAVE_DUTY]-> Duty
"""

import logging
from typing import Set

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
)
from config.settings import settings

logger = logging.getLogger(__name__)


class RulesGraphBuilder:
    """
    Builds the RulesGraph from dictionaries.

    The RulesGraph contains:
    - CountryGroup nodes (name)
    - Country nodes (name, linked to groups)
    - Rule nodes (rule_id, priority, origin_match_type, receiving_match_type, odrl_type, has_pii_required)
    - Action nodes (name)
    - Permission nodes (name)
    - Prohibition nodes (name)
    - Duty nodes (name, module, value)
    """

    def __init__(self, graph=None):
        """
        Initialize the builder.

        Args:
            graph: Optional graph instance. If None, uses the default RulesGraph.
        """
        self.db = get_db_service()
        self.graph = graph if graph is not None else self.db.get_rules_graph()
        self._created_duties: Set[str] = set()

    def build(self, clear_existing: bool = True):
        """
        Build the complete RulesGraph.

        Args:
            clear_existing: Whether to clear existing graph data
        """
        logger.info("Building RulesGraph...")

        if clear_existing:
            self._clear_graph()

        # Create indexes
        self._create_indexes()

        # Build country structure
        self._build_country_groups()
        self._build_countries()

        # Build rule structure
        self._build_actions()
        self._build_case_matching_rules()
        self._build_transfer_rules()
        self._build_attribute_rules()

        logger.info("RulesGraph build complete!")
        self._print_stats()

    def _clear_graph(self):
        """Clear existing graph data"""
        logger.info("Clearing existing RulesGraph data...")
        try:
            self.graph.query("MATCH (n) DETACH DELETE n")
        except Exception as e:
            logger.warning(f"Error clearing graph: {e}")

    def _create_indexes(self):
        """Create indexes for efficient querying"""
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
        """Build CountryGroup nodes"""
        logger.info("Building country groups...")

        for group_name in COUNTRY_GROUPS.keys():
            # CountryGroup only has 'name' property per schema
            query = "CREATE (g:CountryGroup {name: $name})"
            self.graph.query(query, {"name": group_name})

        logger.info(f"Created {len(COUNTRY_GROUPS)} country groups")

    def _build_countries(self):
        """Build Country nodes and link to groups"""
        logger.info("Building countries...")

        all_countries = get_all_countries()

        for country in all_countries:
            # Country only has 'name' property per schema
            self.graph.query(
                "CREATE (c:Country {name: $name})",
                {"name": country}
            )

            # Link to groups with BELONGS_TO relationship
            for group_name, group_countries in COUNTRY_GROUPS.items():
                if country in group_countries:
                    self.graph.query("""
                    MATCH (c:Country {name: $country})
                    MATCH (g:CountryGroup {name: $group})
                    CREATE (c)-[:BELONGS_TO]->(g)
                    """, {"country": country, "group": group_name})

        logger.info(f"Created {len(all_countries)} country nodes")

    def _build_actions(self):
        """Build Action nodes"""
        logger.info("Building actions...")

        # Action only has 'name' property per schema
        actions = [
            "Transfer Data",
            "Transfer PII",
            "Store in Cloud",
            "Process Data",
        ]

        for name in actions:
            self.graph.query(
                "CREATE (a:Action {name: $name})",
                {"name": name}
            )

        logger.info(f"Created {len(actions)} action nodes")

    def _create_duty(self, name: str, module: str, value: str):
        """Create a Duty node if it doesn't exist"""
        duty_key = f"{name}:{module}:{value}"
        if duty_key not in self._created_duties:
            # Duty has name, module, value per schema
            self.graph.query("""
            CREATE (d:Duty {
                name: $name,
                module: $module,
                value: $value
            })
            """, {"name": name, "module": module, "value": value})
            self._created_duties.add(duty_key)

    def _build_case_matching_rules(self):
        """Build case-matching rules (SET 1)"""
        logger.info("Building case-matching rules...")

        rules = get_enabled_case_matching_rules()

        for rule_key, rule in rules.items():
            # Determine match types
            origin_match_type = "group" if rule.origin_group else ("specific" if rule.origin_countries else "any")
            receiving_match_type = "group" if rule.receiving_group else ("specific" if rule.receiving_countries else "any")

            # Create Rule node with schema-defined properties
            self.graph.query("""
            CREATE (r:Rule {
                rule_id: $rule_id,
                priority: $priority,
                origin_match_type: $origin_match_type,
                receiving_match_type: $receiving_match_type,
                odrl_type: $odrl_type,
                has_pii_required: $has_pii_required
            })
            """, {
                "rule_id": rule.rule_id,
                "priority": rule.priority,
                "origin_match_type": origin_match_type,
                "receiving_match_type": receiving_match_type,
                "odrl_type": rule.odrl_type,
                "has_pii_required": rule.requires_pii,
            })

            # Create Permission node (only 'name' per schema)
            perm_name = f"Transfer Permission ({rule.name})"
            self.graph.query("""
            MATCH (r:Rule {rule_id: $rule_id})
            CREATE (p:Permission {name: $name})
            CREATE (r)-[:HAS_PERMISSION]->(p)
            """, {
                "rule_id": rule.rule_id,
                "name": perm_name,
            })

            # Create Duties and link from Permission
            for assessment in rule.required_assessments.to_list():
                duty_name = f"Complete {assessment} Module"
                module = assessment  # PIA, TIA, HRPR
                value = "Completed"

                self._create_duty(duty_name, module, value)

                # Link Permission to Duty
                self.graph.query("""
                MATCH (p:Permission {name: $perm_name})
                MATCH (d:Duty {name: $duty_name, module: $module, value: $value})
                CREATE (p)-[:CAN_HAVE_DUTY]->(d)
                """, {
                    "perm_name": perm_name,
                    "duty_name": duty_name,
                    "module": module,
                    "value": value
                })

            # Link Rule to origin CountryGroup
            if rule.origin_group:
                self.graph.query("""
                MATCH (r:Rule {rule_id: $rule_id})
                MATCH (g:CountryGroup {name: $group})
                CREATE (r)-[:TRIGGERED_BY_ORIGIN]->(g)
                """, {"rule_id": rule.rule_id, "group": rule.origin_group})

            # Link Rule to receiving CountryGroup
            if rule.receiving_group:
                self.graph.query("""
                MATCH (r:Rule {rule_id: $rule_id})
                MATCH (g:CountryGroup {name: $group})
                CREATE (r)-[:TRIGGERED_BY_RECEIVING]->(g)
                """, {"rule_id": rule.rule_id, "group": rule.receiving_group})

            # Link Rule to Action
            self.graph.query("""
            MATCH (r:Rule {rule_id: $rule_id})
            MATCH (a:Action {name: 'Transfer Data'})
            CREATE (r)-[:HAS_ACTION]->(a)
            """, {"rule_id": rule.rule_id})

        logger.info(f"Created {len(rules)} case-matching rules")

    def _build_transfer_rules(self):
        """Build transfer rules (SET 2A)"""
        logger.info("Building transfer rules...")

        rules = get_enabled_transfer_rules()

        for rule_key, rule in rules.items():
            # Determine match types
            origin_match_type = "group" if rule.origin_group else "specific"
            receiving_match_type = "group" if rule.receiving_group else "specific"

            # Create Rule node with schema-defined properties
            self.graph.query("""
            CREATE (r:Rule {
                rule_id: $rule_id,
                priority: $priority,
                origin_match_type: $origin_match_type,
                receiving_match_type: $receiving_match_type,
                odrl_type: $odrl_type,
                has_pii_required: $has_pii_required
            })
            """, {
                "rule_id": rule.rule_id,
                "priority": rule.priority,
                "origin_match_type": origin_match_type,
                "receiving_match_type": receiving_match_type,
                "odrl_type": rule.odrl_type,
                "has_pii_required": rule.requires_pii,
            })

            # Create Prohibition or Permission (only 'name' per schema)
            if rule.outcome == RuleOutcome.PROHIBITION:
                prohib_name = rule.name
                self.graph.query("""
                MATCH (r:Rule {rule_id: $rule_id})
                CREATE (pb:Prohibition {name: $name})
                CREATE (r)-[:HAS_PROHIBITION]->(pb)
                """, {
                    "rule_id": rule.rule_id,
                    "name": prohib_name,
                })

                # Create Duties and link from Prohibition
                for action in rule.required_actions:
                    self._create_duty(action, "action", "required")

                    self.graph.query("""
                    MATCH (pb:Prohibition {name: $prohib_name})
                    MATCH (d:Duty {name: $duty_name})
                    CREATE (pb)-[:CAN_HAVE_DUTY]->(d)
                    """, {
                        "prohib_name": prohib_name,
                        "duty_name": action,
                    })
            else:
                perm_name = rule.name
                self.graph.query("""
                MATCH (r:Rule {rule_id: $rule_id})
                CREATE (p:Permission {name: $name})
                CREATE (r)-[:HAS_PERMISSION]->(p)
                """, {
                    "rule_id": rule.rule_id,
                    "name": perm_name,
                })

            # Link Rule to origin CountryGroup if specified
            if rule.origin_group:
                self.graph.query("""
                MATCH (r:Rule {rule_id: $rule_id})
                MATCH (g:CountryGroup {name: $group})
                CREATE (r)-[:TRIGGERED_BY_ORIGIN]->(g)
                """, {"rule_id": rule.rule_id, "group": rule.origin_group})

            # Link Rule to receiving CountryGroup if specified
            if rule.receiving_group:
                self.graph.query("""
                MATCH (r:Rule {rule_id: $rule_id})
                MATCH (g:CountryGroup {name: $group})
                CREATE (r)-[:TRIGGERED_BY_RECEIVING]->(g)
                """, {"rule_id": rule.rule_id, "group": rule.receiving_group})

            # Link Rule to Action
            action_name = "Transfer PII" if rule.requires_pii else "Transfer Data"
            self.graph.query("""
            MATCH (r:Rule {rule_id: $rule_id})
            MATCH (a:Action {name: $action_name})
            CREATE (r)-[:HAS_ACTION]->(a)
            """, {"rule_id": rule.rule_id, "action_name": action_name})

        logger.info(f"Created {len(rules)} transfer rules")

    def _build_attribute_rules(self):
        """Build attribute rules (SET 2B)"""
        logger.info("Building attribute rules...")

        rules = get_enabled_attribute_rules()

        for rule_key, rule in rules.items():
            # Determine match types
            origin_match_type = "group" if rule.origin_group else ("specific" if rule.origin_countries else "any")
            receiving_match_type = "group" if rule.receiving_group else ("specific" if rule.receiving_countries else "any")

            # Create Rule node with schema-defined properties
            self.graph.query("""
            CREATE (r:Rule {
                rule_id: $rule_id,
                priority: $priority,
                origin_match_type: $origin_match_type,
                receiving_match_type: $receiving_match_type,
                odrl_type: $odrl_type,
                has_pii_required: $has_pii_required
            })
            """, {
                "rule_id": rule.rule_id,
                "priority": rule.priority,
                "origin_match_type": origin_match_type,
                "receiving_match_type": receiving_match_type,
                "odrl_type": rule.odrl_type,
                "has_pii_required": rule.requires_pii,
            })

            # Attribute rules are typically prohibitions
            if rule.outcome == RuleOutcome.PROHIBITION:
                prohib_name = rule.name
                self.graph.query("""
                MATCH (r:Rule {rule_id: $rule_id})
                CREATE (pb:Prohibition {name: $name})
                CREATE (r)-[:HAS_PROHIBITION]->(pb)
                """, {
                    "rule_id": rule.rule_id,
                    "name": prohib_name,
                })

            # Link Rule to Action
            self.graph.query("""
            MATCH (r:Rule {rule_id: $rule_id})
            MATCH (a:Action {name: 'Transfer Data'})
            CREATE (r)-[:HAS_ACTION]->(a)
            """, {"rule_id": rule.rule_id})

        logger.info(f"Created {len(rules)} attribute rules")

    def _print_stats(self):
        """Print graph statistics"""
        stats = self.db.get_graph_stats(settings.database.rules_graph_name)
        logger.info(f"RulesGraph stats: {stats['node_count']} nodes, {stats['edge_count']} edges")

    def add_transfer_rule(self, rule_def: dict) -> bool:
        """
        Add a single transfer rule to the graph.

        Args:
            rule_def: Dictionary with rule definition from AI generation

        Returns:
            True if successful, False otherwise
        """
        try:
            # Determine match types
            origin_match_type = "group" if rule_def.get('origin_group') else (
                "specific" if rule_def.get('origin_countries') else "any"
            )
            receiving_match_type = "group" if rule_def.get('receiving_group') else (
                "specific" if rule_def.get('receiving_countries') else "any"
            )

            # Create Rule node
            self.graph.query("""
            MERGE (r:Rule {rule_id: $rule_id})
            SET r.priority = $priority,
                r.origin_match_type = $origin_match_type,
                r.receiving_match_type = $receiving_match_type,
                r.odrl_type = $odrl_type,
                r.has_pii_required = $has_pii_required
            """, {
                "rule_id": rule_def.get('rule_id'),
                "priority": rule_def.get('priority', 50),
                "origin_match_type": origin_match_type,
                "receiving_match_type": receiving_match_type,
                "odrl_type": rule_def.get('odrl_type', 'Prohibition'),
                "has_pii_required": rule_def.get('requires_pii', False),
            })

            # Create Permission or Prohibition
            rule_name = rule_def.get('name', rule_def.get('rule_id'))
            if rule_def.get('outcome') == 'prohibition':
                self.graph.query("""
                MATCH (r:Rule {rule_id: $rule_id})
                MERGE (pb:Prohibition {name: $name})
                MERGE (r)-[:HAS_PROHIBITION]->(pb)
                """, {
                    "rule_id": rule_def.get('rule_id'),
                    "name": rule_name,
                })

                # Add duties for required actions
                for action in rule_def.get('required_actions', []):
                    self._create_duty(action, "action", "required")
                    self.graph.query("""
                    MATCH (pb:Prohibition {name: $prohib_name})
                    MATCH (d:Duty {name: $duty_name})
                    MERGE (pb)-[:CAN_HAVE_DUTY]->(d)
                    """, {
                        "prohib_name": rule_name,
                        "duty_name": action,
                    })
            else:
                self.graph.query("""
                MATCH (r:Rule {rule_id: $rule_id})
                MERGE (p:Permission {name: $name})
                MERGE (r)-[:HAS_PERMISSION]->(p)
                """, {
                    "rule_id": rule_def.get('rule_id'),
                    "name": rule_name,
                })

            # Link to origin group
            if rule_def.get('origin_group'):
                self.graph.query("""
                MATCH (r:Rule {rule_id: $rule_id})
                MATCH (g:CountryGroup {name: $group})
                MERGE (r)-[:TRIGGERED_BY_ORIGIN]->(g)
                """, {"rule_id": rule_def.get('rule_id'), "group": rule_def.get('origin_group')})

            # Link to receiving group
            if rule_def.get('receiving_group'):
                self.graph.query("""
                MATCH (r:Rule {rule_id: $rule_id})
                MATCH (g:CountryGroup {name: $group})
                MERGE (r)-[:TRIGGERED_BY_RECEIVING]->(g)
                """, {"rule_id": rule_def.get('rule_id'), "group": rule_def.get('receiving_group')})

            # Link to Action
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
        """
        Add a single attribute rule to the graph.

        Args:
            rule_def: Dictionary with rule definition from AI generation

        Returns:
            True if successful, False otherwise
        """
        try:
            # Determine match types
            origin_match_type = "group" if rule_def.get('origin_group') else (
                "specific" if rule_def.get('origin_countries') else "any"
            )
            receiving_match_type = "group" if rule_def.get('receiving_group') else (
                "specific" if rule_def.get('receiving_countries') else "any"
            )

            # Create Rule node
            self.graph.query("""
            MERGE (r:Rule {rule_id: $rule_id})
            SET r.priority = $priority,
                r.origin_match_type = $origin_match_type,
                r.receiving_match_type = $receiving_match_type,
                r.odrl_type = $odrl_type,
                r.has_pii_required = $has_pii_required
            """, {
                "rule_id": rule_def.get('rule_id'),
                "priority": rule_def.get('priority', 50),
                "origin_match_type": origin_match_type,
                "receiving_match_type": receiving_match_type,
                "odrl_type": rule_def.get('odrl_type', 'Prohibition'),
                "has_pii_required": rule_def.get('requires_pii', True),
            })

            # Create Prohibition (attribute rules are typically prohibitions)
            rule_name = rule_def.get('name', rule_def.get('rule_id'))
            if rule_def.get('outcome') == 'prohibition':
                self.graph.query("""
                MATCH (r:Rule {rule_id: $rule_id})
                MERGE (pb:Prohibition {name: $name})
                MERGE (r)-[:HAS_PROHIBITION]->(pb)
                """, {
                    "rule_id": rule_def.get('rule_id'),
                    "name": rule_name,
                })

            # Link to Action
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


def build_rules_graph(clear_existing: bool = True):
    """Build the rules graph (convenience function)"""
    builder = RulesGraphBuilder()
    builder.build(clear_existing)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    build_rules_graph()
