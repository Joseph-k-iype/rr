"""
Validation Models
==================
Pydantic models for validating agent outputs (rule definitions, Cypher queries, etc).
Migrated from the old graph_workflow.py.
"""

from typing import Optional, List, Literal
from pydantic import BaseModel, Field, field_validator

from rules.dictionaries.country_groups import COUNTRY_GROUPS


class RuleDefinitionModel(BaseModel):
    """Pydantic model for validating rule definitions."""
    rule_type: Literal["transfer", "attribute"]
    rule_id: str = Field(..., pattern=r"^RULE_.*$")
    name: str = Field(..., min_length=3, max_length=200)
    description: str = Field(..., min_length=10)
    priority: int = Field(..., ge=1, le=100)
    origin_countries: Optional[List[str]] = None
    origin_group: Optional[str] = None
    receiving_countries: Optional[List[str]] = None
    receiving_group: Optional[str] = None
    outcome: Literal["permission", "prohibition"]
    requires_pii: bool = False
    attribute_name: Optional[str] = None
    attribute_keywords: Optional[List[str]] = None
    required_actions: List[str] = Field(default_factory=list)
    odrl_type: Literal["Permission", "Prohibition"]
    odrl_action: str = "transfer"
    odrl_target: str = "Data"

    @field_validator('origin_group', 'receiving_group')
    @classmethod
    def validate_country_group(cls, v):
        if v is not None and v not in COUNTRY_GROUPS and v != "ANY":
            raise ValueError(f"Unknown country group: {v}")
        return v

    @field_validator('odrl_type')
    @classmethod
    def validate_odrl_matches_outcome(cls, v, info):
        outcome = info.data.get('outcome')
        if outcome == 'prohibition' and v != 'Prohibition':
            raise ValueError("odrl_type must be 'Prohibition' for prohibition outcome")
        if outcome == 'permission' and v != 'Permission':
            raise ValueError("odrl_type must be 'Permission' for permission outcome")
        return v


class CypherQueriesModel(BaseModel):
    """Pydantic model for validating Cypher queries."""
    rule_check: str = Field(..., min_length=10)
    rule_insert: str = Field(..., min_length=10)
    validation: str = Field(..., min_length=10)

    @field_validator('rule_check', 'rule_insert', 'validation')
    @classmethod
    def validate_cypher_syntax(cls, v):
        if not any(keyword in v.upper() for keyword in ['MATCH', 'CREATE', 'MERGE', 'RETURN']):
            raise ValueError("Invalid Cypher query - missing required keywords")
        # FalkorDB: single statement only — no semicolons
        stripped = v.strip().rstrip(';')
        if ';' in stripped:
            raise ValueError("FalkorDB does not support multiple statements in a single query — remove semicolons")
        # FalkorDB: no EXISTS { MATCH ... } subqueries
        if 'EXISTS' in v.upper() and '{' in v and 'MATCH' in v.upper():
            # Check for EXISTS { MATCH pattern (subquery syntax)
            import re
            if re.search(r'EXISTS\s*\{', v, re.IGNORECASE):
                raise ValueError("FalkorDB does not support EXISTS { MATCH ... } subqueries — use OPTIONAL MATCH instead")
        # FalkorDB: no CALL { } subqueries
        if 'CALL' in v.upper() and '{' in v:
            import re
            if re.search(r'CALL\s*\{', v, re.IGNORECASE):
                raise ValueError("FalkorDB does not support CALL { } subqueries")
        return v


class ValidationResultModel(BaseModel):
    """Pydantic model for validation results."""
    overall_valid: bool
    confidence_score: float = Field(..., ge=0.0, le=1.0)
    rule_definition_valid: bool = True
    cypher_valid: bool = True
    logical_valid: bool = True
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    suggested_fixes: List[str] = Field(default_factory=list)
