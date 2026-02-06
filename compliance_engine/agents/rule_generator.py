"""
AI Rule Generator Agent
=======================
Uses LangGraph workflow with multiple agents to parse natural language
rule descriptions and generate:
- Rule dictionary entries
- Cypher query templates
- Test cases

Features:
- Chain of Thought reasoning
- Mixture of Experts for Cypher generation
- Supervisor coordination
- Validation with max 3 iterations
"""

import json
import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime

from pydantic import BaseModel, Field

from agents.ai_service import get_ai_service
from agents.graph_workflow import (
    generate_rule_with_langgraph,
    RuleGenerationResult,
)
from services.database import get_db_service
from services.agent_audit import (
    get_agent_audit_trail,
    AgentActionType,
    AgentActionStatus,
)
from rules.dictionaries.country_groups import COUNTRY_GROUPS

logger = logging.getLogger(__name__)


@dataclass
class AttributeConfig:
    """Configuration for attribute detection"""
    attribute_name: str
    keywords: List[str] = field(default_factory=list)
    patterns: List[str] = field(default_factory=list)
    categories: List[str] = field(default_factory=list)
    case_sensitive: bool = False
    word_boundaries: bool = True
    config_file_path: Optional[str] = None


@dataclass
class ReferenceDataItem:
    """A piece of reference data created by the agent"""
    data_type: str  # country_group, attribute_config, keyword_dictionary
    name: str
    details: Dict[str, Any] = field(default_factory=dict)
    created: bool = False
    requires_approval: bool = True
    approval_status: str = "pending"


@dataclass
class GeneratedRule:
    """Generated rule with metadata"""
    rule_definition: Dict[str, Any]
    cypher_queries: Dict[str, Any]
    reasoning: Dict[str, Any]
    test_cases: List[Dict[str, Any]]
    attribute_config: Optional[AttributeConfig] = None  # For attribute-level rules
    reference_data: List[ReferenceDataItem] = field(default_factory=list)
    generation_timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    validation_errors: List[str] = field(default_factory=list)
    is_valid: bool = True
    iterations_used: int = 1
    audit_session_id: Optional[str] = None


class RuleGeneratorAgent:
    """
    AI-powered rule generation agent using LangGraph.

    Takes natural language rule descriptions and generates:
    - Structured rule definitions (with Chain of Thought)
    - Cypher queries (with Mixture of Experts)
    - Validated outputs (with iterative refinement)
    """

    def __init__(self):
        self.ai_service = get_ai_service()
        self.db_service = get_db_service()

    def generate_rule(
        self,
        rule_text: str,
        rule_country: str,
        rule_type_hint: Optional[str] = None,
        max_iterations: int = 3,
        agentic_mode: bool = False,
    ) -> GeneratedRule:
        """
        Generate a rule definition from natural language text using LangGraph.

        Args:
            rule_text: Natural language rule description
            rule_country: Primary country the rule relates to
            rule_type_hint: Optional hint for rule type ('transfer' or 'attribute')
            max_iterations: Max validation retry iterations (default 3)
            agentic_mode: If True, autonomously create required reference data

        Returns:
            GeneratedRule with parsed rule, cypher, and test cases
        """
        audit = get_agent_audit_trail()
        session = audit.start_session(
            session_type="rule_generation",
            initiator="api",
            agentic_mode=agentic_mode,
            metadata={
                "rule_text": rule_text[:200],
                "rule_country": rule_country,
                "rule_type_hint": rule_type_hint,
            },
        )

        if not self.ai_service.is_enabled:
            audit.complete_session(session.session_id, summary="AI service disabled", status="failed")
            return GeneratedRule(
                rule_definition={},
                cypher_queries={},
                reasoning={},
                test_cases=[],
                validation_errors=["AI service is not enabled"],
                is_valid=False,
                audit_session_id=session.session_id,
            )

        # Log the rule analysis action
        analysis_entry = audit.log_action(
            session_id=session.session_id,
            action_type=AgentActionType.RULE_ANALYSIS,
            agent_name="RuleGeneratorAgent",
            status=AgentActionStatus.IN_PROGRESS,
            input_summary=f"Analyzing: {rule_text[:100]}...",
        )

        # Run the LangGraph workflow
        result = generate_rule_with_langgraph(
            rule_text=rule_text,
            rule_country=rule_country,
            rule_type_hint=rule_type_hint,
            max_iterations=max_iterations,
        )

        audit.complete_action(
            entry_id=analysis_entry.entry_id,
            status=AgentActionStatus.COMPLETED if result.success else AgentActionStatus.FAILED,
            output_summary=f"Rule {'generated' if result.success else 'failed'}: {result.message}",
        )

        if result.success:
            rule_def = result.rule_definition or {}

            # Generate test cases based on the rule
            test_cases = self._generate_test_cases(rule_def)

            # Generate attribute config for attribute-level rules
            attribute_config = None
            reference_data = []

            if rule_def.get("rule_type") == "attribute":
                attr_entry = audit.log_action(
                    session_id=session.session_id,
                    action_type=AgentActionType.ATTRIBUTE_CONFIG_CREATION,
                    agent_name="AttributeConfigAgent",
                    status=AgentActionStatus.IN_PROGRESS,
                    input_summary=f"Generating attribute config for: {rule_def.get('attribute_name')}",
                )
                attribute_config = self._generate_attribute_config(rule_def, rule_text)
                audit.complete_action(
                    entry_id=attr_entry.entry_id,
                    status=AgentActionStatus.COMPLETED,
                    output_summary=f"Generated config with {len(attribute_config.keywords)} keywords, {len(attribute_config.patterns)} patterns",
                )

            # Agentic mode: detect and create required reference data
            if agentic_mode:
                reference_data = self._agentic_create_reference_data(
                    rule_def, rule_text, session.session_id, attribute_config
                )

            generated = GeneratedRule(
                rule_definition=rule_def,
                cypher_queries=result.cypher_queries or {},
                reasoning=result.reasoning or {},
                test_cases=test_cases,
                attribute_config=attribute_config,
                reference_data=reference_data,
                is_valid=True,
                iterations_used=result.iterations,
                audit_session_id=session.session_id,
            )

            audit.complete_session(
                session.session_id,
                summary=f"Rule {rule_def.get('rule_id')} generated successfully with {len(reference_data)} reference data items",
            )
            return generated
        else:
            audit.complete_session(
                session.session_id,
                summary=f"Rule generation failed: {result.message}",
                status="failed",
            )
            return GeneratedRule(
                rule_definition=result.rule_definition or {},
                cypher_queries=result.cypher_queries or {},
                reasoning=result.reasoning or {},
                test_cases=[],
                validation_errors=result.errors,
                is_valid=False,
                iterations_used=result.iterations,
                audit_session_id=session.session_id,
            )

    def _agentic_create_reference_data(
        self,
        rule_def: Dict[str, Any],
        rule_text: str,
        session_id: str,
        attribute_config: Optional[AttributeConfig] = None,
    ) -> List[ReferenceDataItem]:
        """
        Autonomously detect what reference data is needed and create it.

        This is the agentic behavior - the agent analyzes the rule and
        determines what supporting reference data (country groups, attribute
        configs, keyword dictionaries) needs to exist for the rule to work.
        """
        audit = get_agent_audit_trail()
        reference_items = []

        # Step 1: Detect what reference data is needed
        detect_entry = audit.log_action(
            session_id=session_id,
            action_type=AgentActionType.REFERENCE_DATA_DETECTION,
            agent_name="ReferenceDataDetector",
            status=AgentActionStatus.IN_PROGRESS,
            input_summary="Analyzing rule for required reference data",
        )

        needs = self._detect_reference_data_needs(rule_def, rule_text)

        audit.complete_action(
            entry_id=detect_entry.entry_id,
            status=AgentActionStatus.COMPLETED,
            output_summary=f"Detected {len(needs)} reference data needs: {[n['type'] for n in needs]}",
            output_data={"needs": needs},
        )

        # Step 2: Create each needed reference data item
        for need in needs:
            if need["type"] == "country_group":
                item = self._create_country_group_reference(
                    need, rule_def, session_id
                )
                if item:
                    reference_items.append(item)

            elif need["type"] == "attribute_config":
                item = self._create_attribute_config_reference(
                    need, rule_def, rule_text, session_id, attribute_config
                )
                if item:
                    reference_items.append(item)

            elif need["type"] == "keyword_dictionary":
                item = self._create_keyword_dictionary_reference(
                    need, rule_def, rule_text, session_id
                )
                if item:
                    reference_items.append(item)

        return reference_items

    def _detect_reference_data_needs(
        self,
        rule_def: Dict[str, Any],
        rule_text: str,
    ) -> List[Dict[str, Any]]:
        """Use AI to detect what reference data the rule needs"""
        needs = []

        # Check if origin/receiving groups exist
        origin_group = rule_def.get("origin_group")
        if origin_group and origin_group not in COUNTRY_GROUPS and origin_group != "ANY":
            needs.append({
                "type": "country_group",
                "name": origin_group,
                "reason": f"Origin group '{origin_group}' referenced but not defined in COUNTRY_GROUPS",
                "direction": "origin",
            })

        receiving_group = rule_def.get("receiving_group")
        if receiving_group and receiving_group not in COUNTRY_GROUPS and receiving_group != "ANY":
            needs.append({
                "type": "country_group",
                "name": receiving_group,
                "reason": f"Receiving group '{receiving_group}' referenced but not defined in COUNTRY_GROUPS",
                "direction": "receiving",
            })

        # Check if attribute rules need config files
        if rule_def.get("rule_type") == "attribute":
            attr_name = rule_def.get("attribute_name", "")
            if attr_name:
                # Check if a config file exists for this attribute
                from pathlib import Path
                from config.settings import settings
                config_path = settings.paths.config_dir / f"{attr_name}_config.json"
                if not config_path.exists():
                    needs.append({
                        "type": "attribute_config",
                        "name": attr_name,
                        "reason": f"Attribute config file for '{attr_name}' does not exist",
                        "config_path": str(config_path),
                    })

                # Check if attribute keywords are insufficient
                keywords = rule_def.get("attribute_keywords", [])
                if len(keywords) < 10:
                    needs.append({
                        "type": "keyword_dictionary",
                        "name": f"{attr_name}_keywords",
                        "reason": f"Attribute '{attr_name}' has only {len(keywords)} keywords (minimum 10 recommended)",
                        "current_count": len(keywords),
                    })

        # Use AI to detect additional needs
        try:
            prompt = f"""Analyze this compliance rule and determine if any additional reference data is needed.

Rule text: {rule_text}
Rule definition: {json.dumps(rule_def, indent=2)}

Existing country groups: {list(COUNTRY_GROUPS.keys())}

Return a JSON object with:
{{
    "additional_needs": [
        {{
            "type": "country_group" | "attribute_config" | "keyword_dictionary",
            "name": "<name>",
            "reason": "<why it's needed>"
        }}
    ],
    "reasoning": "<your analysis>"
}}

Only include needs that are NOT already covered. Return empty additional_needs if everything is covered.
"""
            response = self.ai_service.chat(
                prompt,
                "You are a compliance data architecture expert. Analyze rules for missing reference data. Return only valid JSON."
            )

            import re
            json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', response)
            json_str = json_match.group(1) if json_match else response

            parsed = json.loads(json_str)
            additional = parsed.get("additional_needs", [])

            # Deduplicate with existing needs
            existing_names = {n["name"] for n in needs}
            for item in additional:
                if item.get("name") and item["name"] not in existing_names:
                    needs.append(item)
                    existing_names.add(item["name"])

        except Exception as e:
            logger.warning(f"AI reference data detection failed: {e}")

        return needs

    def _create_country_group_reference(
        self,
        need: Dict[str, Any],
        rule_def: Dict[str, Any],
        session_id: str,
    ) -> Optional[ReferenceDataItem]:
        """Create a country group reference data item"""
        audit = get_agent_audit_trail()
        group_name = need["name"]

        entry = audit.log_action(
            session_id=session_id,
            action_type=AgentActionType.COUNTRY_GROUP_CREATION,
            agent_name="CountryGroupAgent",
            status=AgentActionStatus.IN_PROGRESS,
            input_summary=f"Creating country group: {group_name}",
            requires_approval=True,
        )

        try:
            # Use AI to determine the countries for this group
            prompt = f"""Generate a list of countries for the country group "{group_name}".

Context: This group is needed for a compliance rule about: {rule_def.get('description', '')}
Direction: {need.get('direction', 'unknown')}

Existing country groups for reference:
{json.dumps({k: list(v)[:5] for k, v in list(COUNTRY_GROUPS.items())[:8]}, indent=2)}

Return a JSON object:
{{
    "group_name": "{group_name}",
    "countries": ["Country1", "Country2", ...],
    "description": "<description of what this group represents>",
    "source": "<regulatory or legal basis for this grouping>"
}}
"""
            response = self.ai_service.chat(
                prompt,
                "You are a compliance geography expert. Generate accurate country groupings. Return only valid JSON."
            )

            import re
            json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', response)
            json_str = json_match.group(1) if json_match else response
            parsed = json.loads(json_str)

            countries = parsed.get("countries", [])

            item = ReferenceDataItem(
                data_type="country_group",
                name=group_name,
                details={
                    "countries": countries,
                    "description": parsed.get("description", ""),
                    "source": parsed.get("source", ""),
                    "python_code": f'COUNTRY_GROUPS["{group_name}"] = frozenset({json.dumps(countries)})',
                },
                created=True,
                requires_approval=True,
                approval_status="pending",
            )

            audit.complete_action(
                entry_id=entry.entry_id,
                status=AgentActionStatus.PENDING_APPROVAL,
                output_summary=f"Generated country group '{group_name}' with {len(countries)} countries",
                output_data=item.details,
            )

            return item

        except Exception as e:
            logger.error(f"Failed to create country group {group_name}: {e}")
            audit.complete_action(
                entry_id=entry.entry_id,
                status=AgentActionStatus.FAILED,
                error_message=str(e),
            )
            return None

    def _create_attribute_config_reference(
        self,
        need: Dict[str, Any],
        rule_def: Dict[str, Any],
        rule_text: str,
        session_id: str,
        existing_config: Optional[AttributeConfig] = None,
    ) -> Optional[ReferenceDataItem]:
        """Create an attribute configuration reference data item"""
        audit = get_agent_audit_trail()
        attr_name = need["name"]

        entry = audit.log_action(
            session_id=session_id,
            action_type=AgentActionType.ATTRIBUTE_CONFIG_CREATION,
            agent_name="AttributeConfigAgent",
            status=AgentActionStatus.IN_PROGRESS,
            input_summary=f"Creating attribute config: {attr_name}",
            requires_approval=True,
        )

        try:
            # Use existing config or generate new one
            if existing_config:
                config = existing_config
            else:
                config = self._generate_attribute_config(rule_def, rule_text)

            # Build the config JSON
            config_dict = {
                "attribute_name": config.attribute_name,
                "enabled": True,
                "keywords": config.keywords,
                "patterns": config.patterns,
                "categories": config.categories,
                "detection_settings": {
                    "case_sensitive": config.case_sensitive,
                    "word_boundaries": config.word_boundaries,
                    "min_confidence": 0.3,
                    "require_multiple_matches": False,
                },
                "generated_at": datetime.now().isoformat(),
                "generated_by": "ReferenceDataAgent",
                "version": "1.0.0",
            }

            # Save the config file
            config_path = need.get("config_path", "")
            if config_path:
                from pathlib import Path
                Path(config_path).parent.mkdir(parents=True, exist_ok=True)
                with open(config_path, 'w') as f:
                    json.dump(config_dict, f, indent=2)
                logger.info(f"Saved attribute config to {config_path}")

            item = ReferenceDataItem(
                data_type="attribute_config",
                name=attr_name,
                details={
                    "config": config_dict,
                    "config_path": config_path,
                    "keywords_count": len(config.keywords),
                    "patterns_count": len(config.patterns),
                    "categories": config.categories,
                },
                created=True,
                requires_approval=True,
                approval_status="pending",
            )

            audit.complete_action(
                entry_id=entry.entry_id,
                status=AgentActionStatus.PENDING_APPROVAL,
                output_summary=(
                    f"Generated attribute config '{attr_name}' with "
                    f"{len(config.keywords)} keywords, {len(config.patterns)} patterns"
                ),
                output_data={"config_path": config_path},
            )

            return item

        except Exception as e:
            logger.error(f"Failed to create attribute config {attr_name}: {e}")
            audit.complete_action(
                entry_id=entry.entry_id,
                status=AgentActionStatus.FAILED,
                error_message=str(e),
            )
            return None

    def _create_keyword_dictionary_reference(
        self,
        need: Dict[str, Any],
        rule_def: Dict[str, Any],
        rule_text: str,
        session_id: str,
    ) -> Optional[ReferenceDataItem]:
        """Create an expanded keyword dictionary reference data item"""
        audit = get_agent_audit_trail()
        dict_name = need["name"]
        attr_name = rule_def.get("attribute_name", "")

        entry = audit.log_action(
            session_id=session_id,
            action_type=AgentActionType.KEYWORD_DICTIONARY_CREATION,
            agent_name="KeywordDictionaryAgent",
            status=AgentActionStatus.IN_PROGRESS,
            input_summary=f"Expanding keyword dictionary: {dict_name}",
            requires_approval=True,
        )

        try:
            existing_keywords = rule_def.get("attribute_keywords", [])

            prompt = f"""Expand this keyword dictionary for detecting "{attr_name}" data in compliance metadata.

Context: {rule_text}
Existing keywords: {existing_keywords}
Current count: {len(existing_keywords)}
Minimum recommended: 20

Generate a comprehensive keyword dictionary with:
1. All existing keywords preserved
2. Additional relevant keywords (aim for 30-50 total)
3. Keywords should be lowercase with underscores for multi-word terms
4. Include domain-specific terms, abbreviations, and common field names

Return a JSON object:
{{
    "dictionary_name": "{dict_name}",
    "attribute_name": "{attr_name}",
    "keywords": ["keyword1", "keyword2", ...],
    "categories": {{
        "category1": ["keyword1", "keyword2"],
        "category2": ["keyword3", "keyword4"]
    }},
    "description": "<what this dictionary covers>"
}}
"""
            response = self.ai_service.chat(
                prompt,
                "You are a data classification expert. Generate comprehensive keyword dictionaries for sensitive data detection. Return only valid JSON."
            )

            import re
            json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', response)
            json_str = json_match.group(1) if json_match else response
            parsed = json.loads(json_str)

            all_keywords = list(set(existing_keywords + parsed.get("keywords", [])))

            item = ReferenceDataItem(
                data_type="keyword_dictionary",
                name=dict_name,
                details={
                    "attribute_name": attr_name,
                    "keywords": all_keywords,
                    "categories": parsed.get("categories", {}),
                    "description": parsed.get("description", ""),
                    "original_count": len(existing_keywords),
                    "expanded_count": len(all_keywords),
                    "python_code": f"# Updated keywords for {attr_name}\nattribute_keywords={json.dumps(all_keywords, indent=4)}",
                },
                created=True,
                requires_approval=True,
                approval_status="pending",
            )

            audit.complete_action(
                entry_id=entry.entry_id,
                status=AgentActionStatus.PENDING_APPROVAL,
                output_summary=(
                    f"Expanded keyword dictionary '{dict_name}' from "
                    f"{len(existing_keywords)} to {len(all_keywords)} keywords"
                ),
            )

            return item

        except Exception as e:
            logger.error(f"Failed to create keyword dictionary {dict_name}: {e}")
            audit.complete_action(
                entry_id=entry.entry_id,
                status=AgentActionStatus.FAILED,
                error_message=str(e),
            )
            return None

    def _generate_test_cases(self, rule_def: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate test cases based on the rule definition"""
        test_cases = []

        rule_type = rule_def.get("rule_type")
        outcome = rule_def.get("outcome")
        origin_countries = rule_def.get("origin_countries") or []
        origin_group = rule_def.get("origin_group")
        receiving_countries = rule_def.get("receiving_countries") or []
        receiving_group = rule_def.get("receiving_group")
        requires_pii = rule_def.get("requires_pii", False)

        # Get sample countries
        if origin_group and origin_group in COUNTRY_GROUPS:
            sample_origins = list(COUNTRY_GROUPS[origin_group])[:2]
        elif origin_countries:
            sample_origins = origin_countries[:2]
        else:
            sample_origins = ["United Kingdom", "Germany"]

        if receiving_group and receiving_group in COUNTRY_GROUPS:
            sample_receiving = list(COUNTRY_GROUPS[receiving_group])[:2]
        elif receiving_countries:
            sample_receiving = receiving_countries[:2]
        else:
            sample_receiving = ["India", "China"]

        expected = "PROHIBITED" if outcome == "prohibition" else "ALLOWED"

        # Test case 1: Direct match
        if sample_origins and sample_receiving:
            test_cases.append({
                "description": f"Direct match: {sample_origins[0]} to {sample_receiving[0]}",
                "input": {
                    "origin": sample_origins[0],
                    "receiving": sample_receiving[0],
                    "pii": requires_pii,
                },
                "expected_outcome": expected,
            })

        # Test case 2: With PII
        if requires_pii and sample_origins and sample_receiving:
            test_cases.append({
                "description": f"With PII flag: {sample_origins[0]} to {sample_receiving[0]}",
                "input": {
                    "origin": sample_origins[0],
                    "receiving": sample_receiving[0],
                    "pii": True,
                },
                "expected_outcome": expected,
            })

        # Test case 3: Negative test (no match)
        test_cases.append({
            "description": "Negative test: Unrelated countries",
            "input": {
                "origin": "Australia",
                "receiving": "New Zealand",
                "pii": False,
            },
            "expected_outcome": "ALLOWED" if outcome == "prohibition" else "REQUIRES_REVIEW",
        })

        return test_cases

    def _generate_attribute_config(
        self,
        rule_def: Dict[str, Any],
        rule_text: str
    ) -> AttributeConfig:
        """
        Generate attribute detection configuration for attribute-level rules.

        Uses AI to generate comprehensive keywords and patterns for detecting
        the specified attribute type in metadata.
        """
        attribute_name = rule_def.get("attribute_name", "custom_data")
        existing_keywords = rule_def.get("attribute_keywords", [])

        # Use AI to expand keywords and generate patterns
        prompt = f"""Generate a comprehensive attribute detection configuration for detecting "{attribute_name}" data.

Original rule: {rule_text}

The configuration should include:
1. Keywords: Common terms that indicate this type of data (minimum 20 keywords)
2. Patterns: Regex patterns to match this type of data
3. Categories: Data categories this attribute falls under

Existing keywords from rule: {existing_keywords}

Return a JSON object with this structure:
{{
    "keywords": ["keyword1", "keyword2", ...],
    "patterns": ["regex_pattern1", "regex_pattern2", ...],
    "categories": ["category1", "category2", ...],
    "example_metadata_values": ["example1", "example2", ...]
}}

IMPORTANT:
- Keywords should be lowercase with underscores for multi-word terms
- Patterns should be valid Python regex patterns (double-escape backslashes)
- Include both specific and general terms
- Consider column names, field names, and data values that might contain this type of data
"""
        system_prompt = """You are an expert at data classification and attribute detection.
Generate comprehensive detection configurations that will accurately identify specific types of sensitive data.
Return only valid JSON."""

        try:
            response = self.ai_service.chat(prompt, system_prompt)

            # Parse response
            import re
            json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', response)
            if json_match:
                json_str = json_match.group(1)
            else:
                json_str = response

            parsed = json.loads(json_str)

            # Merge with existing keywords
            all_keywords = list(set(existing_keywords + parsed.get("keywords", [])))

            return AttributeConfig(
                attribute_name=attribute_name,
                keywords=all_keywords,
                patterns=parsed.get("patterns", []),
                categories=parsed.get("categories", []),
                case_sensitive=False,
                word_boundaries=True,
            )

        except Exception as e:
            logger.warning(f"Failed to generate attribute config with AI: {e}")
            # Fallback to basic config
            return AttributeConfig(
                attribute_name=attribute_name,
                keywords=existing_keywords,
                patterns=[],
                categories=[attribute_name],
            )

    def save_attribute_config(
        self,
        config: AttributeConfig,
        config_dir: Optional[str] = None
    ) -> str:
        """
        Save attribute configuration to a JSON file.

        Args:
            config: The attribute configuration to save
            config_dir: Directory to save to (default: config/)

        Returns:
            Path to the saved config file
        """
        from pathlib import Path
        from config.settings import settings

        if config_dir is None:
            config_dir = settings.paths.config_dir

        # Create config file path
        config_file = Path(config_dir) / f"{config.attribute_name}_config.json"

        # Build config dict
        config_dict = {
            "attribute_name": config.attribute_name,
            "enabled": True,
            "keywords": config.keywords,
            "patterns": config.patterns,
            "categories": config.categories,
            "detection_settings": {
                "case_sensitive": config.case_sensitive,
                "word_boundaries": config.word_boundaries,
            },
            "generated_at": datetime.now().isoformat(),
            "version": "1.0.0"
        }

        # Save to file
        with open(config_file, 'w') as f:
            json.dump(config_dict, f, indent=2)

        config.config_file_path = str(config_file)
        logger.info(f"Saved attribute config to {config_file}")

        return str(config_file)

    def test_rule_in_temp_graph(
        self,
        generated_rule: GeneratedRule
    ) -> Dict[str, Any]:
        """
        Test a generated rule in a temporary graph.

        Args:
            generated_rule: The generated rule to test

        Returns:
            Test results dictionary
        """
        if not generated_rule.is_valid:
            return {
                "success": False,
                "message": "Cannot test invalid rule",
                "validation_errors": generated_rule.validation_errors
            }

        try:
            # Create temporary graph
            temp_graph, graph_name = self.db_service.get_temp_graph()

            # Get rule definition
            rule_def = generated_rule.rule_definition
            origin_countries = rule_def.get("origin_countries", []) or []
            receiving_countries = rule_def.get("receiving_countries", []) or []

            # Add sample data to temp graph
            for country in origin_countries[:3]:
                temp_graph.query(f"CREATE (:Country {{name: '{country}'}})")
            for country in receiving_countries[:3]:
                temp_graph.query(f"CREATE (:Jurisdiction {{name: '{country}'}})")

            # Try to execute the validation Cypher
            cypher_queries = generated_rule.cypher_queries.get("queries", {})
            validation_query = cypher_queries.get("validation", "")

            cypher_success = True
            cypher_error = None

            if validation_query:
                try:
                    temp_graph.query(validation_query)
                except Exception as e:
                    cypher_success = False
                    cypher_error = str(e)

            # Run test cases
            test_results = []
            for test_case in generated_rule.test_cases:
                test_results.append({
                    "description": test_case.get("description", ""),
                    "expected": test_case.get("expected_outcome", ""),
                    "status": "pending",
                    "message": "Test case defined successfully"
                })

            # Cleanup temp graph
            self.db_service.delete_temp_graph(graph_name)

            return {
                "success": cypher_success,
                "graph_name": graph_name,
                "cypher_execution": {
                    "success": cypher_success,
                    "error": cypher_error
                },
                "test_cases_count": len(test_results),
                "test_results": test_results,
                "message": "Rule tested successfully" if cypher_success else f"Test failed: {cypher_error}"
            }

        except Exception as e:
            logger.error(f"Error testing rule in temp graph: {e}")
            return {
                "success": False,
                "message": f"Test failed: {str(e)}"
            }

    def export_rule_for_review(
        self,
        generated_rule: GeneratedRule,
        include_test_results: bool = True,
        save_attribute_config: bool = False
    ) -> Dict[str, Any]:
        """
        Export generated rule for developer review.

        Returns a dictionary with the rule, code snippets, reasoning,
        and attribute configuration for attribute-level rules.
        """
        export = {
            "generated_at": generated_rule.generation_timestamp,
            "is_valid": generated_rule.is_valid,
            "iterations_used": generated_rule.iterations_used,
            "validation_errors": generated_rule.validation_errors,
            "rule_definition": generated_rule.rule_definition,
            "cypher_queries": generated_rule.cypher_queries,
            "reasoning": generated_rule.reasoning,
        }

        if include_test_results:
            export["test_cases"] = generated_rule.test_cases

        # Generate Python code to add this rule
        rule_def = generated_rule.rule_definition
        rule_type = rule_def.get("rule_type", "transfer")

        if rule_type == "transfer":
            python_code = self._generate_transfer_rule_code(rule_def)
        else:
            python_code = self._generate_attribute_rule_code(rule_def)

            # Include attribute configuration for attribute rules
            if generated_rule.attribute_config:
                config = generated_rule.attribute_config

                # Save config file if requested
                if save_attribute_config:
                    config_path = self.save_attribute_config(config)
                    export["attribute_config_file"] = config_path

                # Include config details in export
                export["attribute_config"] = {
                    "attribute_name": config.attribute_name,
                    "keywords": config.keywords,
                    "patterns": config.patterns,
                    "categories": config.categories,
                    "detection_settings": {
                        "case_sensitive": config.case_sensitive,
                        "word_boundaries": config.word_boundaries,
                    }
                }

                # Generate config JSON code
                export["attribute_config_json"] = self._generate_attribute_config_json(config)

        export["python_code"] = python_code

        return export

    def _generate_attribute_config_json(self, config: AttributeConfig) -> str:
        """Generate JSON configuration for attribute detection"""
        config_dict = {
            "attribute_name": config.attribute_name,
            "enabled": True,
            "keywords": config.keywords,
            "patterns": config.patterns,
            "categories": config.categories,
            "detection_settings": {
                "case_sensitive": config.case_sensitive,
                "word_boundaries": config.word_boundaries,
            }
        }
        return f'''
# Save this as config/{config.attribute_name}_config.json

{json.dumps(config_dict, indent=2)}
'''

    def _generate_transfer_rule_code(self, rule_def: Dict[str, Any]) -> str:
        """Generate Python code for a transfer rule"""
        origin_countries = rule_def.get("origin_countries")
        receiving_countries = rule_def.get("receiving_countries")

        origin_str = f"frozenset({origin_countries})" if origin_countries else "None"
        receiving_str = f"frozenset({receiving_countries})" if receiving_countries else "None"

        return f'''
# Add to rules/dictionaries/rules_definitions.py in TRANSFER_RULES

"{rule_def.get("rule_id", "RULE_NEW")}": TransferRule(
    rule_id="{rule_def.get("rule_id", "RULE_NEW")}",
    name="{rule_def.get("name", "")}",
    description="""{rule_def.get("description", "")}""",
    priority={rule_def.get("priority", 10)},
    origin_countries={origin_str},
    origin_group={f'"{rule_def["origin_group"]}"' if rule_def.get("origin_group") else "None"},
    receiving_countries={receiving_str},
    receiving_group={f'"{rule_def["receiving_group"]}"' if rule_def.get("receiving_group") else "None"},
    outcome=RuleOutcome.{"PROHIBITION" if rule_def.get("outcome") == "prohibition" else "PERMISSION"},
    requires_pii={rule_def.get("requires_pii", False)},
    required_actions={rule_def.get("required_actions", [])},
    odrl_type="{rule_def.get("odrl_type", "Prohibition")}",
    odrl_action="{rule_def.get("odrl_action", "transfer")}",
    odrl_target="{rule_def.get("odrl_target", "Data")}",
    enabled=True,
),
'''

    def _generate_attribute_rule_code(self, rule_def: Dict[str, Any]) -> str:
        """Generate Python code for an attribute rule"""
        origin_countries = rule_def.get("origin_countries")
        receiving_countries = rule_def.get("receiving_countries")

        origin_str = f"frozenset({origin_countries})" if origin_countries else "None"
        receiving_str = f"frozenset({receiving_countries})" if receiving_countries else "None"

        return f'''
# Add to rules/dictionaries/rules_definitions.py in ATTRIBUTE_RULES

"{rule_def.get("rule_id", "RULE_NEW")}": AttributeRule(
    rule_id="{rule_def.get("rule_id", "RULE_NEW")}",
    name="{rule_def.get("name", "")}",
    description="""{rule_def.get("description", "")}""",
    priority={rule_def.get("priority", 10)},
    attribute_name="{rule_def.get("attribute_name", "")}",
    attribute_keywords={rule_def.get("attribute_keywords", [])},
    origin_countries={origin_str},
    origin_group={f'"{rule_def["origin_group"]}"' if rule_def.get("origin_group") else "None"},
    receiving_countries={receiving_str},
    receiving_group={f'"{rule_def["receiving_group"]}"' if rule_def.get("receiving_group") else "None"},
    outcome=RuleOutcome.{"PROHIBITION" if rule_def.get("outcome") == "prohibition" else "PERMISSION"},
    requires_pii={rule_def.get("requires_pii", False)},
    odrl_type="{rule_def.get("odrl_type", "Prohibition")}",
    odrl_action="{rule_def.get("odrl_action", "transfer")}",
    odrl_target="{rule_def.get("odrl_target", "Data")}",
    enabled=True,
),
'''


# Singleton instance
_generator: Optional[RuleGeneratorAgent] = None


def get_rule_generator() -> RuleGeneratorAgent:
    """Get the rule generator instance"""
    global _generator
    if _generator is None:
        _generator = RuleGeneratorAgent()
    return _generator
