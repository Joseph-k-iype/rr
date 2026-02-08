"""
Rules Overview Router
======================
Endpoints for rules overview and Cypher templates.
"""

import logging
from fastapi import APIRouter

from models.schemas import RulesOverviewResponse, RuleOverview
from rules.dictionaries.rules_definitions import (
    get_enabled_case_matching_rules,
    get_enabled_transfer_rules,
    get_enabled_attribute_rules,
)
from rules.templates.cypher_templates import list_templates

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["rules"])


@router.get("/rules-overview", response_model=RulesOverviewResponse)
async def get_rules_overview():
    """Get overview of all enabled rules."""
    case_matching = get_enabled_case_matching_rules()
    transfer = get_enabled_transfer_rules()
    attribute = get_enabled_attribute_rules()

    def build_overview(rule, rule_type: str) -> RuleOverview:
        if rule_type == "case_matching":
            origin_scope = rule.origin_group or str(rule.origin_countries) if rule.origin_countries else "Any"
            receiving_scope = rule.receiving_group or str(rule.receiving_countries) if rule.receiving_countries else "Any"
            required = rule.required_assessments.to_list()
            conditions = []
            if rule.requires_pii:
                conditions.append("Requires PII")
            if rule.requires_personal_data:
                conditions.append("Requires Personal Data")
        elif rule_type == "transfer":
            origin_scope = rule.origin_group or "Specific countries"
            receiving_scope = rule.receiving_group or "Specific countries"
            required = rule.required_actions
            conditions = []
            if rule.requires_pii:
                conditions.append("Requires PII")
            if rule.requires_any_data:
                conditions.append("Any data")
        else:
            origin_scope = rule.origin_group or str(rule.origin_countries) if rule.origin_countries else "Any"
            receiving_scope = rule.receiving_group or str(rule.receiving_countries) if rule.receiving_countries else "Any"
            required = []
            conditions = [f"Attribute: {rule.attribute_name}"]
            if rule.requires_pii:
                conditions.append("Requires PII")

        return RuleOverview(
            rule_id=rule.rule_id,
            name=rule.name,
            description=rule.description,
            rule_type=rule_type,
            priority=rule.priority,
            origin_scope=origin_scope,
            receiving_scope=receiving_scope,
            outcome=rule.odrl_type,
            required_assessments=required,
            conditions=conditions,
            enabled=rule.enabled,
        )

    return RulesOverviewResponse(
        total_rules=len(case_matching) + len(transfer) + len(attribute),
        case_matching_rules=[build_overview(r, "case_matching") for r in case_matching.values()],
        transfer_rules=[build_overview(r, "transfer") for r in transfer.values()],
        attribute_rules=[build_overview(r, "attribute") for r in attribute.values()],
    )


@router.get("/cypher-templates")
async def get_cypher_templates():
    """Get list of available Cypher query templates."""
    return list_templates()
