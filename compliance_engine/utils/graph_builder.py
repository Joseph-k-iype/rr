"""
Graph Builder
=============
Builds the RulesGraph from rule definitions — the single source of truth.

RulesGraph Schema:
- Country: name
- CountryGroup: name
- LegalEntity: name, country
- Rule: rule_id, rule_type, name, description, priority, priority_order,
        origin_match_type, receiving_match_type, outcome,
        odrl_type, odrl_action, odrl_target,
        has_pii_required, requires_any_data, requires_personal_data,
        valid_until, enabled
- Action: name
- Permission: name
- Prohibition: name
- Duty: name, module, value
- Process: name, category
- Purpose: name, category
- DataSubject: name, category
- GDC: name, category
- DataCategory: name

Relationships:
- Country -[:BELONGS_TO]-> CountryGroup
- Country -[:HAS_LEGAL_ENTITY]-> LegalEntity
- Rule -[:TRIGGERED_BY_ORIGIN]-> CountryGroup | Country | LegalEntity
- Rule -[:TRIGGERED_BY_RECEIVING]-> CountryGroup | Country | LegalEntity
- Rule -[:EXCLUDES_RECEIVING]-> CountryGroup
- Rule -[:HAS_ACTION]-> Action
- Rule -[:HAS_PERMISSION]-> Permission
- Rule -[:HAS_PROHIBITION]-> Prohibition
- Permission -[:CAN_HAVE_DUTY]-> Duty
  (Prohibitions do NOT have duties)
- Rule -[:HAS_DATA_CATEGORY]-> DataCategory
- Rule -[:HAS_PURPOSE]-> Purpose
"""

import csv
import json
import logging
from typing import Set, Dict, Any, List

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.database import get_db_service
from rules.dictionaries.country_groups import COUNTRY_GROUPS, get_all_countries
from rules.dictionaries.rules_definitions import (
    get_enabled_case_matching_rules,
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
        self._created_legal_entities: Set[str] = set()

    def build(self, clear_existing: bool = True):
        """Build the complete RulesGraph."""
        logger.info("Building RulesGraph...")

        if clear_existing:
            self._clear_graph()

        self._create_indexes()
        self._build_country_groups()
        self._build_countries()
        self._build_legal_entities()
        self._build_actions()
        self._build_case_matching_rules()
        self._ingest_data_dictionaries()

        logger.info("RulesGraph build complete!")
        self._print_stats()

    def build_incremental(self):
        """Build the RulesGraph incrementally — no clearing, uses MERGE for all operations."""
        logger.info("Building RulesGraph incrementally (no clear)...")

        self._create_indexes()
        self._build_country_groups_merge()
        self._build_countries_merge()
        self._build_legal_entities()
        self._build_actions_merge()
        self._build_case_matching_rules()
        self._ingest_data_dictionaries()

        logger.info("RulesGraph incremental build complete!")
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
            "CREATE INDEX IF NOT EXISTS FOR (n:LegalEntity) ON (n.name)",
            "CREATE INDEX IF NOT EXISTS FOR (n:Rule) ON (n.rule_id)",
            "CREATE INDEX IF NOT EXISTS FOR (n:Action) ON (n.name)",
            "CREATE INDEX IF NOT EXISTS FOR (n:Permission) ON (n.name)",
            "CREATE INDEX IF NOT EXISTS FOR (n:Prohibition) ON (n.name)",
            "CREATE INDEX IF NOT EXISTS FOR (n:Duty) ON (n.name)",
            "CREATE INDEX IF NOT EXISTS FOR (n:Process) ON (n.name)",
            "CREATE INDEX IF NOT EXISTS FOR (n:Purpose) ON (n.name)",
            "CREATE INDEX IF NOT EXISTS FOR (n:DataSubject) ON (n.name)",
            "CREATE INDEX IF NOT EXISTS FOR (n:GDC) ON (n.name)",
            "CREATE INDEX IF NOT EXISTS FOR (n:DataCategory) ON (n.name)",
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

    def _build_country_groups_merge(self):
        logger.info("Building country groups (merge)...")
        for group_name in COUNTRY_GROUPS.keys():
            self.graph.query("MERGE (g:CountryGroup {name: $name})", {"name": group_name})
        logger.info(f"Merged {len(COUNTRY_GROUPS)} country groups")

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

    def _build_countries_merge(self):
        logger.info("Building countries (merge)...")
        all_countries = get_all_countries()
        for country in all_countries:
            self.graph.query("MERGE (c:Country {name: $name})", {"name": country})
            self._created_countries.add(country)
            for group_name, group_countries in COUNTRY_GROUPS.items():
                if country in group_countries:
                    self.graph.query("""
                    MATCH (c:Country {name: $country})
                    MATCH (g:CountryGroup {name: $group})
                    MERGE (c)-[:BELONGS_TO]->(g)
                    """, {"country": country, "group": group_name})
        logger.info(f"Merged {len(all_countries)} country nodes")

    def _ensure_country(self, country_name: str):
        """Create a Country node if it doesn't already exist in the graph."""
        if country_name not in self._created_countries:
            self.graph.query("MERGE (c:Country {name: $name})", {"name": country_name})
            self._created_countries.add(country_name)

    def _build_legal_entities(self):
        """Load legal entities from CSV (preferred) or JSON fallback."""
        logger.info("Building legal entities...")

        # Try CSV first
        csv_file = Path(__file__).parent.parent / "rules" / "data_dictionaries" / "csv" / "legal_entities.csv"
        if csv_file.exists():
            self._build_legal_entities_from_csv(csv_file)
            return

        # Fallback to JSON
        le_file = Path(__file__).parent.parent / "rules" / "data_dictionaries" / "legal_entities.json"
        if not le_file.exists():
            logger.warning("Legal entities file not found")
            return

        try:
            with open(le_file) as f:
                data = json.load(f)

            count = 0
            for country_name, entities in data.get("entities", {}).items():
                self._ensure_country(country_name)
                for entity_name in entities:
                    entity_key = f"{entity_name}:{country_name}"
                    if entity_key not in self._created_legal_entities:
                        self.graph.query("""
                        MERGE (le:LegalEntity {name: $name, country: $country})
                        """, {"name": entity_name, "country": country_name})
                        self._created_legal_entities.add(entity_key)
                        count += 1

                    self.graph.query("""
                    MATCH (c:Country {name: $country})
                    MATCH (le:LegalEntity {name: $entity_name, country: $country})
                    MERGE (c)-[:HAS_LEGAL_ENTITY]->(le)
                    """, {"country": country_name, "entity_name": entity_name})

            logger.info(f"Created {count} legal entity nodes from JSON")
        except Exception as e:
            logger.error(f"Failed to build legal entities: {e}")

    def _build_legal_entities_from_csv(self, csv_file: Path):
        """Load legal entities from CSV file using MERGE."""
        try:
            count = 0
            with open(csv_file, newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    entity_name = row.get('entity_name', '').strip()
                    country_name = row.get('country', '').strip()
                    if not entity_name or not country_name:
                        continue

                    self._ensure_country(country_name)
                    entity_key = f"{entity_name}:{country_name}"
                    if entity_key not in self._created_legal_entities:
                        self.graph.query("""
                        MERGE (le:LegalEntity {name: $name, country: $country})
                        """, {"name": entity_name, "country": country_name})
                        self._created_legal_entities.add(entity_key)
                        count += 1

                    self.graph.query("""
                    MATCH (c:Country {name: $country})
                    MATCH (le:LegalEntity {name: $entity_name, country: $country})
                    MERGE (c)-[:HAS_LEGAL_ENTITY]->(le)
                    """, {"country": country_name, "entity_name": entity_name})

            logger.info(f"Merged {count} legal entity nodes from CSV")
        except Exception as e:
            logger.error(f"Failed to build legal entities from CSV: {e}")

    def _build_actions(self):
        logger.info("Building actions...")
        actions = [
            "Transfer Data", "Transfer PII", "Store in Cloud", "Process Data",
            "Anonymisation", "Consent", "Consult/Approve Legal",
            "Consult/Approve Risk and Compliance", "Notification to Regulator",
            "Privacy Notice", "Local Authority/Regulatory Approval",
            "Enhanced Technical and Organisational Security Measures",
            "Public Availability", "Services Agreement", "Storage Limitation",
            "Outsourcing Agreement", "Explicit Consent",
        ]
        for name in actions:
            self.graph.query("CREATE (a:Action {name: $name})", {"name": name})
        logger.info(f"Created {len(actions)} action nodes")

    def _build_actions_merge(self):
        logger.info("Building actions (merge)...")
        actions = [
            "Transfer Data", "Transfer PII", "Store in Cloud", "Process Data",
            "Anonymisation", "Consent", "Consult/Approve Legal",
            "Consult/Approve Risk and Compliance", "Notification to Regulator",
            "Privacy Notice", "Local Authority/Regulatory Approval",
            "Enhanced Technical and Organisational Security Measures",
            "Public Availability", "Services Agreement", "Storage Limitation",
            "Outsourcing Agreement", "Explicit Consent",
        ]
        for name in actions:
            self.graph.query("MERGE (a:Action {name: $name})", {"name": name})
        logger.info(f"Merged {len(actions)} action nodes")

    def _create_duty(self, name: str, module: str, value: str):
        duty_key = f"{name}:{module}:{value}"
        if duty_key not in self._created_duties:
            self.graph.query("""
            MERGE (d:Duty {name: $name, module: $module, value: $value})
            """, {"name": name, "module": module, "value": value})
            self._created_duties.add(duty_key)

    # -------------------------------------------------------------------------
    # Case-Matching Rules
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
            MERGE (r:Rule {rule_id: $rule_id})
            SET r.rule_type = 'case_matching',
                r.name = $name,
                r.description = $description,
                r.priority = $priority,
                r.priority_order = $priority_order,
                r.origin_match_type = $origin_match_type,
                r.receiving_match_type = $receiving_match_type,
                r.outcome = 'permission',
                r.odrl_type = $odrl_type,
                r.odrl_action = $odrl_action,
                r.odrl_target = $odrl_target,
                r.has_pii_required = $has_pii_required,
                r.requires_any_data = false,
                r.requires_personal_data = $requires_personal_data,
                r.enabled = true
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
            MERGE (p:Permission {name: $name})
            MERGE (r)-[:HAS_PERMISSION]->(p)
            """, {"rule_id": rule.rule_id, "name": perm_name})

            for assessment in rule.required_assessments.to_list():
                duty_name = f"Complete {assessment} Module"
                self._create_duty(duty_name, assessment, "Completed")
                self.graph.query("""
                MATCH (p:Permission {name: $perm_name})
                MATCH (d:Duty {name: $duty_name, module: $module, value: $value})
                MERGE (p)-[:CAN_HAVE_DUTY]->(d)
                """, {"perm_name": perm_name, "duty_name": duty_name, "module": assessment, "value": "Completed"})

            # Origin relationships
            if rule.origin_group:
                self.graph.query("""
                MATCH (r:Rule {rule_id: $rule_id})
                MATCH (g:CountryGroup {name: $group})
                MERGE (r)-[:TRIGGERED_BY_ORIGIN]->(g)
                """, {"rule_id": rule.rule_id, "group": rule.origin_group})

            if rule.origin_countries:
                for country in rule.origin_countries:
                    self._ensure_country(country)
                    self.graph.query("""
                    MATCH (r:Rule {rule_id: $rule_id})
                    MATCH (c:Country {name: $country})
                    MERGE (r)-[:TRIGGERED_BY_ORIGIN]->(c)
                    """, {"rule_id": rule.rule_id, "country": country})

            # Receiving relationships
            if rule.receiving_group:
                self.graph.query("""
                MATCH (r:Rule {rule_id: $rule_id})
                MATCH (g:CountryGroup {name: $group})
                MERGE (r)-[:TRIGGERED_BY_RECEIVING]->(g)
                """, {"rule_id": rule.rule_id, "group": rule.receiving_group})

            if rule.receiving_countries:
                for country in rule.receiving_countries:
                    self._ensure_country(country)
                    self.graph.query("""
                    MATCH (r:Rule {rule_id: $rule_id})
                    MATCH (c:Country {name: $country})
                    MERGE (r)-[:TRIGGERED_BY_RECEIVING]->(c)
                    """, {"rule_id": rule.rule_id, "country": country})

            # Receiving exclusion
            if rule.receiving_not_in:
                for group_marker in rule.receiving_not_in:
                    self.graph.query("""
                    MATCH (r:Rule {rule_id: $rule_id})
                    MATCH (g:CountryGroup {name: $group})
                    MERGE (r)-[:EXCLUDES_RECEIVING]->(g)
                    """, {"rule_id": rule.rule_id, "group": group_marker})

            # Link to Action
            self.graph.query("""
            MATCH (r:Rule {rule_id: $rule_id})
            MATCH (a:Action {name: 'Transfer Data'})
            MERGE (r)-[:HAS_ACTION]->(a)
            """, {"rule_id": rule.rule_id})

        logger.info(f"Created {len(rules)} case-matching rules")

    # -------------------------------------------------------------------------
    # Data Dictionary Ingestion (CSV preferred, JSON fallback)
    # -------------------------------------------------------------------------

    def _ingest_data_dictionaries(self):
        """Load data dictionaries from CSV (preferred) or JSON fallback."""
        csv_dir = Path(__file__).parent.parent / "rules" / "data_dictionaries" / "csv"
        dict_dir = Path(__file__).parent.parent / "rules" / "data_dictionaries"

        node_type_map = {
            "processes": "Process",
            "purposes": "Purpose",
            "data_subjects": "DataSubject",
            "gdc": "GDC",
        }

        # Try CSV files first
        if csv_dir.exists():
            csv_loaded = set()
            for csv_file in csv_dir.glob("*.csv"):
                stem = csv_file.stem
                if stem in ("legal_entities", "purpose_of_processing"):
                    continue
                node_type = node_type_map.get(stem)
                if not node_type:
                    continue
                self._ingest_csv_dictionary(csv_file, node_type)
                csv_loaded.add(stem)

            # Fall back to JSON for any not covered by CSV
            for json_file in dict_dir.glob("*.json"):
                try:
                    with open(json_file) as f:
                        data = json.load(f)
                    dict_name = data.get("name", json_file.stem)
                    if dict_name in ("legal_entities", "purpose_of_processing"):
                        continue
                    if dict_name in csv_loaded:
                        continue
                    node_type = node_type_map.get(dict_name)
                    if not node_type:
                        continue
                    self._ingest_json_dictionary(data, node_type, json_file.name)
                except Exception as e:
                    logger.error(f"Failed to ingest {json_file}: {e}")
        else:
            # No CSV directory, use JSON only
            if not dict_dir.exists():
                logger.warning(f"Data dictionaries directory not found: {dict_dir}")
                return
            for json_file in dict_dir.glob("*.json"):
                try:
                    with open(json_file) as f:
                        data = json.load(f)
                    dict_name = data.get("name", json_file.stem)
                    if dict_name in ("legal_entities", "purpose_of_processing"):
                        continue
                    node_type = node_type_map.get(dict_name)
                    if not node_type:
                        continue
                    self._ingest_json_dictionary(data, node_type, json_file.name)
                except Exception as e:
                    logger.error(f"Failed to ingest {json_file}: {e}")

    def _ingest_csv_dictionary(self, csv_file: Path, node_type: str):
        """Ingest a CSV data dictionary file using MERGE."""
        try:
            count = 0
            with open(csv_file, newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    name = row.get('name', '').strip()
                    category = row.get('category', '').strip()
                    if not name:
                        continue
                    self.graph.query(
                        f"MERGE (n:{node_type} {{name: $name}}) "
                        f"SET n.category = $category",
                        {"name": name, "category": category}
                    )
                    count += 1
            logger.info(f"Ingested {count} {node_type} nodes from {csv_file.name}")
        except Exception as e:
            logger.error(f"Failed to ingest CSV {csv_file}: {e}")

    def _ingest_json_dictionary(self, data: dict, node_type: str, filename: str):
        """Ingest a JSON data dictionary using MERGE."""
        count = 0
        for category_name, category_data in data.get("categories", {}).items():
            for entry in category_data.get("entries", []):
                self.graph.query(
                    f"MERGE (n:{node_type} {{name: $name}}) "
                    f"SET n.category = $category",
                    {"name": entry, "category": category_name}
                )
                count += 1
        logger.info(f"Ingested {count} {node_type} nodes from {filename}")

    # -------------------------------------------------------------------------
    # Dynamic rule addition (wizard/sandbox) — unified method
    # -------------------------------------------------------------------------

    def add_rule(self, rule_def: dict) -> bool:
        """Add any rule type to the graph from AI-generated definition."""
        try:
            rule_type = rule_def.get('rule_type') or 'attribute'
            origin_match_type = "group" if rule_def.get('origin_group') else (
                "specific" if rule_def.get('origin_countries') else "any"
            )
            receiving_match_type = "group" if rule_def.get('receiving_group') else (
                "specific" if rule_def.get('receiving_countries') else "any"
            )
            priority = rule_def.get('priority', 'medium')
            outcome = rule_def.get('outcome', 'permission')
            valid_until = rule_def.get('valid_until')

            self.graph.query("""
            MERGE (r:Rule {rule_id: $rule_id})
            SET r.rule_type = $rule_type,
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
                r.requires_personal_data = $requires_personal_data,
                r.required_actions = $required_actions,
                r.valid_until = $valid_until,
                r.case_matching_module = $case_matching_module,
                r.enabled = true
            """, {
                "rule_id": rule_def.get('rule_id'),
                "rule_type": rule_type,
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
                "requires_personal_data": rule_def.get('requires_personal_data', False),
                "required_actions": ",".join(rule_def.get('required_actions') or []),
                "valid_until": valid_until,
                "case_matching_module": rule_def.get('case_matching_module') or None,
            })

            # Permission/Prohibition
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

                for action in (rule_def.get('required_actions') or []):
                    self._create_duty(action, "action", "required")
                    self.graph.query("""
                    MATCH (p:Permission {name: $perm_name})
                    MATCH (d:Duty {name: $duty_name})
                    MERGE (p)-[:CAN_HAVE_DUTY]->(d)
                    """, {"perm_name": rule_name, "duty_name": action})

            # Origin
            if rule_def.get('origin_group'):
                self.graph.query("""
                MATCH (r:Rule {rule_id: $rule_id})
                MATCH (g:CountryGroup {name: $group})
                MERGE (r)-[:TRIGGERED_BY_ORIGIN]->(g)
                """, {"rule_id": rule_def.get('rule_id'), "group": rule_def['origin_group']})
            for country in (rule_def.get('origin_countries') or []):
                self._ensure_country(country)
                self.graph.query("""
                MATCH (r:Rule {rule_id: $rule_id})
                MATCH (c:Country {name: $country})
                MERGE (r)-[:TRIGGERED_BY_ORIGIN]->(c)
                """, {"rule_id": rule_def.get('rule_id'), "country": country})
            for entity in (rule_def.get('origin_legal_entities') or []):
                self.graph.query("""
                MATCH (r:Rule {rule_id: $rule_id})
                MATCH (le:LegalEntity {name: $entity})
                MERGE (r)-[:TRIGGERED_BY_ORIGIN]->(le)
                """, {"rule_id": rule_def.get('rule_id'), "entity": entity})

            # Receiving
            if rule_def.get('receiving_group'):
                self.graph.query("""
                MATCH (r:Rule {rule_id: $rule_id})
                MATCH (g:CountryGroup {name: $group})
                MERGE (r)-[:TRIGGERED_BY_RECEIVING]->(g)
                """, {"rule_id": rule_def.get('rule_id'), "group": rule_def['receiving_group']})
            for country in (rule_def.get('receiving_countries') or []):
                self._ensure_country(country)
                self.graph.query("""
                MATCH (r:Rule {rule_id: $rule_id})
                MATCH (c:Country {name: $country})
                MERGE (r)-[:TRIGGERED_BY_RECEIVING]->(c)
                """, {"rule_id": rule_def.get('rule_id'), "country": country})
            for entity in (rule_def.get('receiving_legal_entities') or []):
                self.graph.query("""
                MATCH (r:Rule {rule_id: $rule_id})
                MATCH (le:LegalEntity {name: $entity})
                MERGE (r)-[:TRIGGERED_BY_RECEIVING]->(le)
                """, {"rule_id": rule_def.get('rule_id'), "entity": entity})

            # Action
            action_name = "Transfer PII" if rule_def.get('requires_pii') else "Transfer Data"
            self.graph.query("""
            MATCH (r:Rule {rule_id: $rule_id})
            MATCH (a:Action {name: $action_name})
            MERGE (r)-[:HAS_ACTION]->(a)
            """, {"rule_id": rule_def.get('rule_id'), "action_name": action_name})

            # Data Categories — MERGE nodes and link to rule
            for cat in (rule_def.get('data_categories') or []):
                cat_name = str(cat).strip()
                if cat_name:
                    self.graph.query("""
                    MERGE (dc:DataCategory {name: $name})
                    """, {"name": cat_name})
                    self.graph.query("""
                    MATCH (r:Rule {rule_id: $rule_id})
                    MATCH (dc:DataCategory {name: $name})
                    MERGE (r)-[:HAS_DATA_CATEGORY]->(dc)
                    """, {"rule_id": rule_def.get('rule_id'), "name": cat_name})

            # Purposes — MERGE nodes and link to rule
            for purpose in (rule_def.get('purposes_of_processing') or []):
                purpose_name = str(purpose).strip()
                if purpose_name:
                    self.graph.query("""
                    MERGE (p:Purpose {name: $name})
                    """, {"name": purpose_name})
                    self.graph.query("""
                    MATCH (r:Rule {rule_id: $rule_id})
                    MATCH (p:Purpose {name: $name})
                    MERGE (r)-[:HAS_PURPOSE]->(p)
                    """, {"rule_id": rule_def.get('rule_id'), "name": purpose_name})

            logger.info(f"Added rule: {rule_def.get('rule_id')} (type={rule_type})")
            return True
        except Exception as e:
            logger.error(f"Failed to add rule: {e}")
            return False

    def _print_stats(self):
        stats = self.db.get_graph_stats(settings.database.rules_graph_name)
        logger.info(f"RulesGraph stats: {stats['node_count']} nodes, {stats['edge_count']} edges")


def build_rules_graph(clear_existing: bool = True):
    """Build the rules graph (convenience function)"""
    builder = RulesGraphBuilder()
    if clear_existing:
        builder.build(clear_existing=True)
    else:
        builder.build_incremental()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    build_rules_graph()
