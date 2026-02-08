"""
Prompt Builder
===============
Assembles prompts with dynamic context injection.
"""

import json
from typing import Dict, Any, Optional, List

from rules.dictionaries.country_groups import COUNTRY_GROUPS


def build_country_groups_context() -> str:
    """Build a prompt section listing available country groups."""
    lines = []
    for name, countries in COUNTRY_GROUPS.items():
        sample = list(countries)[:5]
        lines.append(f"- {name}: {', '.join(sample)}{'...' if len(countries) > 5 else ''}")
    return "\n".join(lines)


def build_supervisor_prompt(
    template: str,
    rule_text: str,
    origin_country: str,
    scenario_type: str,
    receiving_countries: List[str],
    data_categories: List[str],
    current_phase: str,
    iteration: int,
    max_iterations: int,
    agent_outputs: Dict[str, Any],
    validation_status: str,
    feedback: str,
) -> str:
    """Build a fully-assembled supervisor user prompt."""
    return template.format(
        rule_text=rule_text,
        origin_country=origin_country,
        scenario_type=scenario_type,
        receiving_countries=", ".join(receiving_countries),
        data_categories=", ".join(data_categories) if data_categories else "None",
        current_phase=current_phase,
        iteration=iteration,
        max_iterations=max_iterations,
        agent_outputs=json.dumps(agent_outputs, indent=2, default=str),
        validation_status=validation_status,
        feedback=feedback or "None",
    )


def build_analyzer_prompt(
    template: str,
    rule_text: str,
    origin_country: str,
    receiving_countries: List[str],
    scenario_type: str,
    data_categories: List[str],
    feedback: str,
) -> str:
    """Build a fully-assembled analyzer user prompt."""
    return template.format(
        rule_text=rule_text,
        origin_country=origin_country,
        receiving_countries=", ".join(receiving_countries),
        scenario_type=scenario_type,
        data_categories=", ".join(data_categories) if data_categories else "None",
        feedback=feedback or "None",
    )


def build_cypher_prompt(
    template: str,
    rule_definition: Dict[str, Any],
    feedback: str,
) -> str:
    """Build a fully-assembled Cypher generator user prompt."""
    return template.format(
        rule_definition=json.dumps(rule_definition, indent=2),
        feedback=feedback or "None",
    )


def build_validator_prompt(
    template: str,
    rule_text: str,
    rule_definition: Dict[str, Any],
    cypher_queries: Dict[str, Any],
    dictionary: Optional[Dict[str, Any]],
    iteration: int,
    max_iterations: int,
    previous_errors: List[str],
) -> str:
    """Build a fully-assembled validator user prompt."""
    previous_errors_str = "\n".join(previous_errors) if previous_errors else "None"
    return template.format(
        rule_text=rule_text,
        rule_definition=json.dumps(rule_definition, indent=2),
        cypher_queries=json.dumps(cypher_queries, indent=2),
        dictionary=json.dumps(dictionary, indent=2) if dictionary else "None",
        iteration=iteration,
        max_iterations=max_iterations,
        previous_errors=f"Previous errors:\n{previous_errors_str}",
    )


def build_dictionary_prompt(
    template: str,
    data_categories: List[str],
    rule_text: str,
    origin_country: str,
    scenario_type: str,
    feedback: str,
) -> str:
    """Build a fully-assembled dictionary user prompt."""
    return template.format(
        data_categories=", ".join(data_categories),
        rule_text=rule_text,
        origin_country=origin_country,
        scenario_type=scenario_type,
        feedback=feedback or "None",
    )


def build_reference_prompt(
    template: str,
    rule_definition: Dict[str, Any],
    rule_text: str,
    feedback: str,
) -> str:
    """Build a fully-assembled reference data user prompt."""
    existing_groups = list(COUNTRY_GROUPS.keys())
    return template.format(
        rule_definition=json.dumps(rule_definition, indent=2),
        rule_text=rule_text,
        existing_groups=", ".join(existing_groups),
        feedback=feedback or "None",
    )
