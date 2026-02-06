"""
Tests for Rules Evaluation
==========================
Tests for the compliance engine rules evaluation.
"""

import pytest
import sys
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from rules.dictionaries.country_groups import (
    EU_EEA_COUNTRIES,
    UK_CROWN_DEPENDENCIES,
    ADEQUACY_COUNTRIES,
    BCR_COUNTRIES,
    US_RESTRICTED_COUNTRIES,
    get_country_group,
    is_country_in_group,
)
from rules.dictionaries.rules_definitions import (
    CASE_MATCHING_RULES,
    TRANSFER_RULES,
    ATTRIBUTE_RULES,
    get_enabled_case_matching_rules,
    get_enabled_transfer_rules,
    get_enabled_attribute_rules,
    RuleOutcome,
)
from rules.templates.cypher_templates import (
    CYPHER_TEMPLATES,
    build_origin_filter,
    build_receiving_filter,
    build_purpose_filter,
    build_assessment_filter,
)


class TestCountryGroups:
    """Tests for country groups"""

    def test_eu_eea_countries(self):
        """Test EU/EEA country group has expected countries"""
        assert "Germany" in EU_EEA_COUNTRIES
        assert "France" in EU_EEA_COUNTRIES
        assert "Spain" in EU_EEA_COUNTRIES
        assert len(EU_EEA_COUNTRIES) >= 27

    def test_uk_crown_dependencies(self):
        """Test UK and Crown Dependencies group"""
        assert "United Kingdom" in UK_CROWN_DEPENDENCIES
        assert "Jersey" in UK_CROWN_DEPENDENCIES
        assert "Guernsey" in UK_CROWN_DEPENDENCIES
        assert "Isle of Man" in UK_CROWN_DEPENDENCIES

    def test_adequacy_countries(self):
        """Test adequacy countries group"""
        assert "Japan" in ADEQUACY_COUNTRIES
        assert "Canada" in ADEQUACY_COUNTRIES
        assert "New Zealand" in ADEQUACY_COUNTRIES

    def test_bcr_countries(self):
        """Test BCR countries group"""
        assert "India" in BCR_COUNTRIES
        assert "Singapore" in BCR_COUNTRIES
        assert "United States of America" in BCR_COUNTRIES

    def test_us_restricted_countries(self):
        """Test US restricted countries group"""
        assert "China" in US_RESTRICTED_COUNTRIES
        assert "Russia" in US_RESTRICTED_COUNTRIES
        assert "Iran" in US_RESTRICTED_COUNTRIES

    def test_get_country_group(self):
        """Test getting country group by name"""
        group = get_country_group("EU_EEA")
        assert "Germany" in group
        assert "France" in group

    def test_is_country_in_group(self):
        """Test checking if country is in group"""
        assert is_country_in_group("Germany", "EU_EEA")
        assert is_country_in_group("United Kingdom", "UK_CROWN_DEPENDENCIES")
        assert not is_country_in_group("United States", "EU_EEA")


class TestCaseMatchingRules:
    """Tests for case-matching rules (SET 1)"""

    def test_rules_exist(self):
        """Test that case-matching rules are defined"""
        assert len(CASE_MATCHING_RULES) > 0

    def test_rule_structure(self):
        """Test that rules have required fields"""
        for key, rule in CASE_MATCHING_RULES.items():
            assert rule.rule_id is not None
            assert rule.name is not None
            assert rule.description is not None
            assert rule.priority is not None
            assert rule.required_assessments is not None

    def test_eu_internal_rule(self):
        """Test EU internal transfer rule"""
        rule = CASE_MATCHING_RULES.get("RULE_1_EU_INTERNAL")
        assert rule is not None
        assert rule.origin_group == "EU_EEA_UK_CROWN_CH"
        assert rule.receiving_group == "EU_EEA_UK_CROWN_CH"
        assert rule.required_assessments.pia_required

    def test_bcr_rule(self):
        """Test BCR countries rule"""
        rule = CASE_MATCHING_RULES.get("RULE_7_BCR")
        assert rule is not None
        assert rule.origin_group == "BCR_COUNTRIES"
        assert rule.required_assessments.pia_required
        assert rule.required_assessments.hrpr_required

    def test_get_enabled_rules(self):
        """Test getting enabled rules"""
        enabled = get_enabled_case_matching_rules()
        assert len(enabled) > 0
        for key, rule in enabled.items():
            assert rule.enabled


class TestTransferRules:
    """Tests for transfer rules (SET 2A)"""

    def test_rules_exist(self):
        """Test that transfer rules are defined"""
        assert len(TRANSFER_RULES) > 0

    def test_us_restricted_pii_rule(self):
        """Test US to restricted countries PII rule"""
        rule = TRANSFER_RULES.get("RULE_9_US_RESTRICTED_PII")
        assert rule is not None
        assert rule.outcome == RuleOutcome.PROHIBITION
        assert rule.requires_pii
        assert len(rule.transfer_pairs) > 0

    def test_us_china_cloud_rule(self):
        """Test US to China cloud storage rule"""
        rule = TRANSFER_RULES.get("RULE_10_US_CHINA_CLOUD")
        assert rule is not None
        assert rule.outcome == RuleOutcome.PROHIBITION
        assert rule.requires_any_data
        assert rule.priority == 1  # Highest priority

    def test_transfer_pairs(self):
        """Test transfer pairs structure"""
        rule = TRANSFER_RULES.get("RULE_9_US_RESTRICTED_PII")
        for origin, receiving in rule.transfer_pairs:
            assert origin in ["United States", "United States of America"]
            assert receiving in US_RESTRICTED_COUNTRIES


class TestAttributeRules:
    """Tests for attribute rules (SET 2B)"""

    def test_rules_exist(self):
        """Test that attribute rules are defined"""
        assert len(ATTRIBUTE_RULES) > 0

    def test_health_data_rule(self):
        """Test US health data transfer rule"""
        rule = ATTRIBUTE_RULES.get("RULE_11_US_HEALTH")
        assert rule is not None
        assert rule.attribute_name == "health_data"
        assert rule.outcome == RuleOutcome.PROHIBITION
        assert "United States" in rule.origin_countries

    def test_attribute_keywords(self):
        """Test attribute rules have keywords or config"""
        for key, rule in ATTRIBUTE_RULES.items():
            has_keywords = len(rule.attribute_keywords) > 0
            has_config = rule.attribute_config_file is not None
            # Rule should have either keywords or config file
            assert has_keywords or has_config or rule.attribute_name


class TestCypherTemplates:
    """Tests for Cypher query templates"""

    def test_templates_exist(self):
        """Test that templates are defined"""
        assert len(CYPHER_TEMPLATES) > 0

    def test_template_structure(self):
        """Test that templates have required fields"""
        for key, template in CYPHER_TEMPLATES.items():
            assert template.template_id is not None
            assert template.name is not None
            assert template.query_template is not None

    def test_build_origin_filter(self):
        """Test building origin country filter"""
        filter_str = build_origin_filter("United Kingdom")
        assert "Country" in filter_str
        assert "United Kingdom" in filter_str

    def test_build_origin_filter_none(self):
        """Test building origin filter with None"""
        filter_str = build_origin_filter(None)
        assert filter_str == ""

    def test_build_receiving_filter(self):
        """Test building receiving country filter"""
        filter_str = build_receiving_filter("India")
        assert "Jurisdiction" in filter_str
        assert "India" in filter_str

    def test_build_purpose_filter(self):
        """Test building purpose filter"""
        filter_str = build_purpose_filter(["Marketing", "Analytics"])
        assert "Purpose" in filter_str
        assert "Marketing" in filter_str

    def test_build_assessment_filter(self):
        """Test building assessment filter"""
        filter_str = build_assessment_filter(pia_required=True, tia_required=True)
        assert "pia_status" in filter_str
        assert "tia_status" in filter_str


class TestRulePriorities:
    """Tests for rule priority ordering"""

    def test_transfer_rules_high_priority(self):
        """Test that transfer prohibition rules have high priority"""
        for key, rule in TRANSFER_RULES.items():
            if rule.outcome == RuleOutcome.PROHIBITION:
                assert rule.priority <= 10, f"Prohibition rule {key} should have priority <= 10"

    def test_case_matching_rules_lower_priority(self):
        """Test that case-matching rules have moderate priority"""
        for key, rule in CASE_MATCHING_RULES.items():
            assert rule.priority >= 10, f"Case-matching rule {key} should have priority >= 10"


class TestRuleConsistency:
    """Tests for rule consistency and validity"""

    def test_unique_rule_ids(self):
        """Test that all rule IDs are unique"""
        all_ids = set()

        for rule in CASE_MATCHING_RULES.values():
            assert rule.rule_id not in all_ids, f"Duplicate rule ID: {rule.rule_id}"
            all_ids.add(rule.rule_id)

        for rule in TRANSFER_RULES.values():
            assert rule.rule_id not in all_ids, f"Duplicate rule ID: {rule.rule_id}"
            all_ids.add(rule.rule_id)

        for rule in ATTRIBUTE_RULES.values():
            assert rule.rule_id not in all_ids, f"Duplicate rule ID: {rule.rule_id}"
            all_ids.add(rule.rule_id)

    def test_odrl_properties(self):
        """Test ODRL properties are valid"""
        valid_types = ["Permission", "Prohibition"]
        valid_actions = ["transfer", "store", "process"]

        for rule in CASE_MATCHING_RULES.values():
            assert rule.odrl_type in valid_types
            assert rule.odrl_action in valid_actions

        for rule in TRANSFER_RULES.values():
            assert rule.odrl_type in valid_types
            assert rule.odrl_action in valid_actions


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
