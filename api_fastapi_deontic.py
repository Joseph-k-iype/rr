#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Data Transfer Compliance Dashboard - FastAPI Backend with Deontic Logic
OPTIMIZED VERSION for Large Scale (35K+ nodes, 10M+ edges)

Uses formal policy framework: Actions, Permissions, Prohibitions, Duties
Swagger UI at /docs and ReDoc at /redoc

Key Features:
- Case status filtering (only Completed/Complete/Active/Published searchable)
- Dynamic PIA/TIA/HRPR rules evaluation
- Country-specific rules take precedence over assessments
- Optimized queries with caching for large graphs
- Rules Overview endpoint for business users
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any
from falkordb import FalkorDB
import logging
from pathlib import Path
import json
from functools import lru_cache
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============================================================================
# CONSTANTS
# ============================================================================

# Valid case statuses for search (others are skipped)
VALID_CASE_STATUSES = ['Completed', 'Complete', 'Active', 'Published']

# Country-specific rule priority (higher = takes precedence)
COUNTRY_RULE_PRIORITY = 100

# Query timeout in milliseconds (optimized for large graphs)
QUERY_TIMEOUT_MS = 60000  # 60 seconds for very large graphs

# Cache TTL in seconds
CACHE_TTL = 300  # 5 minutes

# ============================================================================
# Query Optimization for Large Graphs (35k+ nodes, 10M+ edges)
# ============================================================================

# Simple in-memory cache
_query_cache = {}
_cache_timestamps = {}


def get_cached_result(cache_key: str):
    """Get cached result if not expired"""
    if cache_key in _query_cache:
        if time.time() - _cache_timestamps.get(cache_key, 0) < CACHE_TTL:
            return _query_cache[cache_key]
    return None


def set_cached_result(cache_key: str, result):
    """Store result in cache"""
    _query_cache[cache_key] = result
    _cache_timestamps[cache_key] = time.time()


def query_with_timeout(graph, query_str, params=None, timeout_ms=QUERY_TIMEOUT_MS, context="", use_cache=False, cache_key=None):
    """
    Execute query with timeout to prevent hanging on large graphs.
    Optionally uses caching for frequently-run queries.
    """
    # Check cache first
    if use_cache and cache_key:
        cached = get_cached_result(cache_key)
        if cached is not None:
            logger.debug(f"Cache hit: {context}")
            return cached

    try:
        if context:
            logger.debug(f"Query: {context} (timeout: {timeout_ms}ms)")

        result = graph.query(query_str, params=params or {}, timeout=timeout_ms)

        # Cache if requested
        if use_cache and cache_key:
            set_cached_result(cache_key, result)

        return result

    except Exception as e:
        error_msg = str(e).lower()
        if 'timeout' in error_msg or 'timed out' in error_msg:
            logger.error(f"TIMEOUT after {timeout_ms}ms - {context}")
            logger.error("Consider: 1) Running optimize_graph_indexes.py, 2) Narrowing search criteria")
            raise HTTPException(
                status_code=504,
                detail=f"Query timeout: exceeded {timeout_ms/1000}s. Graph may be very large - try narrowing search criteria or contact admin to optimize indexes."
            )
        else:
            logger.error(f"Query error ({context}): {e}")
            raise HTTPException(status_code=500, detail=f"Database query error: {str(e)}")


# ============================================================================
# Load health data configuration
# ============================================================================
HEALTH_CONFIG_PATH = Path(__file__).parent / "health_data_config.json"
HEALTH_CONFIG = {}
if HEALTH_CONFIG_PATH.exists():
    with open(HEALTH_CONFIG_PATH, 'r', encoding='utf-8') as f:
        HEALTH_CONFIG = json.load(f)
        logger.info(f"Loaded health data config: {len(HEALTH_CONFIG['detection_rules']['keywords'])} keywords, "
                   f"{len(HEALTH_CONFIG['detection_rules']['patterns'])} patterns")
else:
    logger.warning("health_data_config.json not found - using fallback keywords")

# Load prohibition rules configuration
PROHIBITION_CONFIG_PATH = Path(__file__).parent / "prohibition_rules_config.json"
PROHIBITION_CONFIG = {}
if PROHIBITION_CONFIG_PATH.exists():
    with open(PROHIBITION_CONFIG_PATH, 'r', encoding='utf-8') as f:
        PROHIBITION_CONFIG = json.load(f)
        logger.info(f"Loaded prohibition rules config: {len(PROHIBITION_CONFIG.get('prohibition_rules', {}))} rules")
else:
    logger.warning("prohibition_rules_config.json not found")

# Initialize FastAPI app
app = FastAPI(
    title="Data Transfer Compliance API - Deontic Logic (Optimized)",
    description="Graph-based compliance engine using deontic logic framework (Actions, Permissions, Prohibitions, Duties). Optimized for 35K+ nodes and 10M+ edges.",
    version="4.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# FalkorDB connections
db = FalkorDB(host='localhost', port=6379)
rules_graph = db.select_graph('RulesGraph')
data_graph = db.select_graph('DataTransferGraph')


# ============================================================================
# PYDANTIC MODELS
# ============================================================================

class Duty(BaseModel):
    """A duty/obligation that must be fulfilled"""
    name: str
    description: str
    module: Optional[str] = None
    value: Optional[str] = None


class Permission(BaseModel):
    """A permission allowing an action with associated duties"""
    name: str
    description: str
    duties: List[Duty] = Field(default_factory=list)


class Prohibition(BaseModel):
    """A prohibition blocking an action, possibly with duties to get exception"""
    name: str
    description: str
    duties: List[Duty] = Field(default_factory=list)


class Action(BaseModel):
    """The action being evaluated"""
    name: str
    description: str


class TriggeredRule(BaseModel):
    """A compliance rule that was triggered"""
    rule_id: str
    description: str
    priority: int
    action: Optional[Action] = None
    permission: Optional[Permission] = None
    prohibition: Optional[Prohibition] = None
    is_blocked: bool = False
    is_country_specific: bool = False
    origin_group: str = ""
    receiving_group: str = ""


class RulesEvaluationRequest(BaseModel):
    """Request to evaluate compliance rules - all fields are optional for dynamic evaluation"""
    origin_country: Optional[str] = Field(None, description="Originating country name")
    receiving_country: Optional[str] = Field(None, description="Receiving country name")
    pii: Optional[bool] = Field(None, description="Whether transfer contains PII")
    purpose_of_processing: Optional[List[str]] = Field(None, description="Purpose(s) of data processing")
    process_l1: Optional[str] = Field(None, description="Process area Level 1")
    process_l2: Optional[str] = Field(None, description="Process function Level 2")
    process_l3: Optional[str] = Field(None, description="Process detail Level 3")
    other_metadata: Optional[Dict[str, str]] = Field(None, description="Additional metadata for health data detection")

    class Config:
        json_schema_extra = {
            "example": {
                "origin_country": "United States",
                "receiving_country": "China",
                "pii": True,
                "purpose_of_processing": ["Analytics", "Marketing"],
                "process_l1": "Sales",
                "process_l2": "Customer Management",
                "process_l3": "CRM Operations",
                "other_metadata": {"patient_records": "medical history"}
            }
        }


class RulesEvaluationResponse(BaseModel):
    """Response from rules evaluation"""
    success: bool = True
    transfer_status: str  # ALLOWED or PROHIBITED
    transfer_blocked: bool = False
    blocked_reason: Optional[str] = None
    triggered_rules: List[TriggeredRule]
    total_rules_triggered: int
    has_prohibitions: bool = False
    has_country_prohibition: bool = False
    consolidated_duties: List[Duty] = Field(default_factory=list)
    precedent_validation: Optional[Dict] = None
    assessment_compliance: Optional[Dict] = None


class SearchCasesRequest(BaseModel):
    """Request to search for cases"""
    origin_country: Optional[str] = Field(None, description="Originating country (partial match)")
    receiving_country: Optional[str] = Field(None, description="Receiving country (partial match)")
    pii: Optional[bool] = Field(None, description="Whether transfer contains PII")
    purpose_of_processing: Optional[List[str]] = Field(None, description="Purpose(s) of data processing")
    process_l1: Optional[str] = Field(None, description="Process area Level 1")
    process_l2: Optional[str] = Field(None, description="Process function Level 2")
    process_l3: Optional[str] = Field(None, description="Process detail Level 3")
    other_metadata: Optional[Dict[str, str]] = Field(None, description="Additional metadata filters")


class CaseData(BaseModel):
    """A single data transfer case"""
    case_id: str
    eim_id: Optional[str]
    business_app_id: Optional[str]
    origin_country: str
    receiving_countries: List[str]
    purposes: List[str]
    process_l1: Optional[str]
    process_l2: Optional[str]
    process_l3: Optional[str]
    pia_module: Optional[str]
    tia_module: Optional[str]
    hrpr_module: Optional[str]
    personal_data: List[str]
    personal_data_categories: List[str]
    categories: List[str]
    has_pii: bool
    has_health_data: bool = False
    case_status: Optional[str] = None


class SearchCasesResponse(BaseModel):
    """Response from case search"""
    success: bool = True
    cases: List[CaseData]
    total_cases: int


class StatsResponse(BaseModel):
    """Dashboard statistics"""
    success: bool = True
    stats: Dict[str, int]


class CountriesResponse(BaseModel):
    """Available countries"""
    success: bool = True
    countries: List[str]
    origin_countries: List[str]
    receiving_countries: List[str]


class PurposesResponse(BaseModel):
    """Available purposes"""
    success: bool = True
    purposes: List[str]


class ProcessesResponse(BaseModel):
    """Available process levels"""
    success: bool = True
    process_l1: List[str]
    process_l2: List[str]
    process_l3: List[str]


class RuleOverview(BaseModel):
    """Rule overview for business users"""
    rule_id: str
    name: str
    description: str
    rule_type: str  # Permission or Prohibition
    priority: int
    origin_countries: List[str]
    receiving_countries: List[str]
    requires_pii: bool
    requires_health_data: bool
    duties: List[str]
    is_country_specific: bool


class RulesOverviewResponse(BaseModel):
    """Response with all rules for business users"""
    success: bool = True
    total_rules: int
    permission_rules: List[RuleOverview]
    prohibition_rules: List[RuleOverview]
    country_specific_rules: List[RuleOverview]


# ============================================================================
# CORE LOGIC FUNCTIONS
# ============================================================================

def detect_health_data_from_metadata(other_metadata: Optional[Dict[str, str]], verbose: bool = True) -> Dict[str, any]:
    """
    Automatically detect if metadata contains health-related information
    Uses comprehensive health data configuration with word boundary matching
    """
    if not other_metadata:
        return {'detected': False, 'matched_keywords': [], 'matched_patterns': [], 'matched_fields': []}

    import re

    # Load keywords from config, fallback to basic list
    if HEALTH_CONFIG and 'detection_rules' in HEALTH_CONFIG:
        health_keywords = HEALTH_CONFIG['detection_rules']['keywords']
        health_patterns = HEALTH_CONFIG['detection_rules'].get('patterns', [])
    else:
        health_keywords = [
            'health', 'medical', 'patient', 'diagnosis', 'treatment', 'prescription',
            'clinical', 'hospital', 'doctor', 'disease', 'illness', 'medication',
            'healthcare', 'wellness', 'fitness', 'biometric', 'genetic', 'vaccine',
            'surgery', 'therapy', 'pharmaceutical', 'radiology', 'lab', 'laboratory'
        ]
        health_patterns = [r'icd-?\d+', r'cpt-?\d+', r'diagnosis code', r'medical record']

    matched_keywords = []
    matched_patterns = []
    matched_fields = []

    for key, value in other_metadata.items():
        field_text = f"{key} {value}".lower()
        normalized_text = field_text.replace('_', ' ').replace('-', ' ')
        field_matched = False

        for keyword in health_keywords:
            if re.search(r'\b' + re.escape(keyword.lower()) + r'\b', normalized_text):
                if keyword not in matched_keywords:
                    matched_keywords.append(keyword)
                field_matched = True

        for pattern in health_patterns:
            if re.search(pattern, field_text, re.IGNORECASE):
                if pattern not in matched_patterns:
                    matched_patterns.append(pattern)
                field_matched = True

        if field_matched:
            matched_fields.append({'key': key, 'value': value})

    detected = len(matched_keywords) > 0 or len(matched_patterns) > 0

    if verbose and detected:
        logger.info(f"Health data detected: {len(matched_keywords)} keywords in {len(matched_fields)} fields")

    return {
        'detected': detected,
        'matched_keywords': matched_keywords,
        'matched_patterns': matched_patterns,
        'matched_fields': matched_fields
    }


def has_pii_data(personal_data_categories: List[str]) -> bool:
    """Check if a case contains PII based on personalDataCategory field."""
    if not personal_data_categories:
        return False

    non_na_values = [
        pdc.strip()
        for pdc in personal_data_categories
        if pdc and pdc.strip().upper() not in ['N/A', 'NA', 'NULL', '']
    ]

    return len(non_na_values) > 0


def contains_health_data(personal_data: List[str], personal_data_categories: List[str]) -> bool:
    """Check if personal data or categories contain health-related information"""
    import re

    health_keywords = [
        'health', 'medical', 'patient', 'diagnosis', 'treatment', 'prescription',
        'clinical', 'hospital', 'doctor', 'disease', 'illness', 'medication',
        'healthcare', 'wellness', 'fitness', 'biometric', 'genetic'
    ]

    all_data = personal_data + personal_data_categories
    all_data_lower = [item.lower() for item in all_data if item]

    for data_item in all_data_lower:
        for keyword in health_keywords:
            if re.search(r'\b' + re.escape(keyword) + r'\b', data_item):
                return True

    return False


def check_country_specific_prohibition(origin: str, receiving: str, has_pii: bool = None, has_health_data: bool = None) -> Optional[Dict]:
    """
    Check if there's a country-specific prohibition rule that takes precedence.
    Country-specific rules OVERRIDE PIA/TIA/HRPR assessments.

    Returns:
        Dict with prohibition details if found, None otherwise
    """
    if not PROHIBITION_CONFIG or 'prohibition_rules' not in PROHIBITION_CONFIG:
        return None

    for rule_name, rule_config in PROHIBITION_CONFIG['prohibition_rules'].items():
        if not rule_config.get('enabled', True):
            continue

        # Check origin match
        origin_countries = rule_config.get('origin_countries', [])
        origin_match = any(
            origin.lower() == c.lower() or origin.lower() in c.lower()
            for c in origin_countries
        )

        if not origin_match:
            continue

        # Check receiving match
        receiving_countries = rule_config.get('receiving_countries', [])
        if 'ANY' not in receiving_countries:
            receiving_match = any(
                receiving.lower() == c.lower() or receiving.lower() in c.lower()
                for c in receiving_countries
            )
            if not receiving_match:
                continue

        # Check PII requirement
        if rule_config.get('requires_pii') and not has_pii:
            continue

        # Check health data requirement
        if rule_config.get('requires_health_data') and not has_health_data:
            continue

        # Found a matching country-specific prohibition
        return {
            'rule_id': rule_config.get('rule_id', rule_name),
            'rule_name': rule_name,
            'prohibition_name': rule_config.get('prohibition_name', rule_name),
            'prohibition_description': rule_config.get('prohibition_description', ''),
            'duties': rule_config.get('duties', []),
            'origin_countries': origin_countries,
            'receiving_countries': receiving_countries,
            'priority': COUNTRY_RULE_PRIORITY + rule_config.get('priority', 0),
            'is_country_specific': True
        }

    return None


def query_triggered_rules_deontic(origin: str, receiving: str, has_pii: bool = None, has_health_data: bool = None) -> Dict:
    """
    Query the RulesGraph using deontic logic structure.
    Returns rules with their actions, permissions, prohibitions, and duties.
    """
    logger.info(f"Querying Deontic RulesGraph for: {origin} -> {receiving}, pii={has_pii}, health={has_health_data}")

    # First check for country-specific prohibition (takes precedence)
    country_prohibition = check_country_specific_prohibition(origin, receiving, has_pii, has_health_data)

    query = """
    // Get origin country's groups
    MATCH (origin:Country {name: $origin_country})-[:BELONGS_TO]->(origin_group:CountryGroup)
    WITH collect(DISTINCT origin_group.name) as origin_groups

    // Get receiving country's groups
    MATCH (receiving:Country {name: $receiving_country})-[:BELONGS_TO]->(receiving_group:CountryGroup)
    WITH origin_groups, collect(DISTINCT receiving_group.name) as receiving_groups

    // Match all rules and check their conditions
    MATCH (r:Rule)

    OPTIONAL MATCH (r)-[:TRIGGERED_BY_ORIGIN]->(r_origin:CountryGroup)
    WITH r, origin_groups, receiving_groups, collect(DISTINCT r_origin.name) as rule_origin_groups

    OPTIONAL MATCH (r)-[:TRIGGERED_BY_RECEIVING]->(r_receiving:CountryGroup)
    WITH r, origin_groups, receiving_groups, rule_origin_groups,
         collect(DISTINCT r_receiving.name) as rule_receiving_groups

    WITH r, origin_groups, receiving_groups, rule_origin_groups, rule_receiving_groups,
         CASE
             WHEN r.origin_match_type = 'ALL' THEN true
             WHEN r.origin_match_type = 'ANY' AND size(rule_origin_groups) = 0 THEN false
             WHEN r.origin_match_type = 'ANY' THEN any(g IN origin_groups WHERE g IN rule_origin_groups)
             ELSE false
         END as origin_matches,
         CASE
             WHEN r.receiving_match_type = 'ALL' THEN true
             WHEN r.receiving_match_type = 'ANY' AND size(rule_receiving_groups) = 0 THEN false
             WHEN r.receiving_match_type = 'ANY' THEN any(g IN receiving_groups WHERE g IN rule_receiving_groups)
             WHEN r.receiving_match_type = 'NOT_IN' AND size(rule_receiving_groups) = 0 THEN true
             WHEN r.receiving_match_type = 'NOT_IN' THEN NOT any(g IN receiving_groups WHERE g IN rule_receiving_groups)
             ELSE false
         END as receiving_matches

    WHERE origin_matches AND receiving_matches
          AND (NOT r.has_pii_required OR $has_pii = true)
          AND (NOT r.health_data_required OR $has_health_data = true)

    OPTIONAL MATCH (r)-[:HAS_ACTION]->(action:Action)
    OPTIONAL MATCH (r)-[:HAS_PERMISSION]->(perm:Permission)
    OPTIONAL MATCH (perm)-[:CAN_HAVE_DUTY]->(perm_duty:Duty)
    OPTIONAL MATCH (r)-[:HAS_PROHIBITION]->(prohib:Prohibition)
    OPTIONAL MATCH (prohib)-[:CAN_HAVE_DUTY]->(prohib_duty:Duty)

    RETURN r.rule_id as rule_id,
           r.description as description,
           r.priority as priority,
           r.odrl_type as odrl_type,
           r.odrl_action as odrl_action,
           r.odrl_target as odrl_target,
           action.name as action_name,
           action.description as action_description,
           perm.name as permission_name,
           perm.description as permission_description,
           collect(DISTINCT {name: perm_duty.name, description: perm_duty.description,
                            module: perm_duty.module, value: perm_duty.value}) as permission_duties,
           prohib.name as prohibition_name,
           prohib.description as prohibition_description,
           collect(DISTINCT {name: prohib_duty.name, description: prohib_duty.description,
                            module: prohib_duty.module, value: prohib_duty.value}) as prohibition_duties
    ORDER BY r.priority
    """

    try:
        result = query_with_timeout(
            rules_graph,
            query,
            params={
                'origin_country': origin,
                'receiving_country': receiving,
                'has_pii': has_pii if has_pii is not None else False,
                'has_health_data': has_health_data if has_health_data is not None else False
            },
            context="Query triggered rules"
        )

        triggered_rules = []
        consolidated_duties_map = {}
        has_prohibitions = False
        has_country_prohibition = country_prohibition is not None

        # Add country-specific prohibition rule first (highest priority)
        if country_prohibition:
            has_prohibitions = True
            prohibition_duties = [
                {'name': d, 'description': f'Required: {d}', 'module': None, 'value': None}
                for d in country_prohibition['duties']
            ]
            for duty in prohibition_duties:
                consolidated_duties_map[duty['name']] = duty

            triggered_rules.append({
                'rule_id': country_prohibition['rule_id'],
                'description': country_prohibition['prohibition_description'],
                'priority': country_prohibition['priority'],
                'odrl_type': 'Prohibition',
                'odrl_action': 'transfer',
                'odrl_target': 'Data',
                'action': {'name': 'Transfer Data', 'description': 'Cross-border data transfer'},
                'permission': None,
                'prohibition': {
                    'name': country_prohibition['prohibition_name'],
                    'description': country_prohibition['prohibition_description'],
                    'duties': prohibition_duties
                },
                'is_blocked': True,
                'is_country_specific': True,
                'origin_group': ','.join(country_prohibition['origin_countries']),
                'receiving_group': ','.join(country_prohibition['receiving_countries'])
            })

        # Process graph rules
        if result.result_set:
            for row in result.result_set:
                rule_id = row[0]
                description = row[1]
                priority = row[2]
                odrl_type = row[3] if row[3] else None
                odrl_action = row[4] if row[4] else None
                odrl_target = row[5] if row[5] else None
                action_name = row[6] if row[6] else None
                action_description = row[7] if row[7] else None
                permission_name = row[8] if row[8] else None
                permission_description = row[9] if row[9] else None
                permission_duties = row[10] if row[10] else []
                prohibition_name = row[11] if row[11] else None
                prohibition_description = row[12] if row[12] else None
                prohibition_duties = row[13] if row[13] else []

                action_obj = None
                if action_name:
                    action_obj = {'name': action_name, 'description': action_description or ''}

                permission_obj = None
                if permission_name:
                    perm_duties_list = []
                    for duty in permission_duties:
                        if duty.get('name'):
                            duty_obj = {
                                'name': duty['name'],
                                'description': duty.get('description', ''),
                                'module': duty.get('module'),
                                'value': duty.get('value')
                            }
                            perm_duties_list.append(duty_obj)
                            consolidated_duties_map[duty['name']] = duty_obj

                    permission_obj = {
                        'name': permission_name,
                        'description': permission_description or '',
                        'duties': perm_duties_list
                    }

                prohibition_obj = None
                is_blocked = False
                if prohibition_name:
                    prohib_duties_list = []
                    for duty in prohibition_duties:
                        if duty.get('name'):
                            duty_obj = {
                                'name': duty['name'],
                                'description': duty.get('description', ''),
                                'module': duty.get('module'),
                                'value': duty.get('value')
                            }
                            prohib_duties_list.append(duty_obj)
                            consolidated_duties_map[duty['name']] = duty_obj

                    prohibition_obj = {
                        'name': prohibition_name,
                        'description': prohibition_description or '',
                        'duties': prohib_duties_list
                    }
                    is_blocked = True
                    has_prohibitions = True

                triggered_rules.append({
                    'rule_id': rule_id,
                    'description': description,
                    'priority': priority,
                    'odrl_type': odrl_type,
                    'odrl_action': odrl_action,
                    'odrl_target': odrl_target,
                    'action': action_obj,
                    'permission': permission_obj,
                    'prohibition': prohibition_obj,
                    'is_blocked': is_blocked,
                    'is_country_specific': False,
                    'origin_group': '',
                    'receiving_group': ''
                })

        # Sort by priority (country-specific rules first)
        triggered_rules.sort(key=lambda r: (-r.get('priority', 0), r.get('rule_id', '')))

        logger.info(f"Triggered {len(triggered_rules)} rules, has_prohibitions={has_prohibitions}, country_prohibition={has_country_prohibition}")

        return {
            'triggered_rules': triggered_rules,
            'total_rules_triggered': len(triggered_rules),
            'has_prohibitions': has_prohibitions,
            'has_country_prohibition': has_country_prohibition,
            'consolidated_duties': list(consolidated_duties_map.values())
        }

    except Exception as e:
        logger.error(f"Error querying RulesGraph: {e}", exc_info=True)
        return {
            'triggered_rules': [],
            'total_rules_triggered': 0,
            'has_prohibitions': False,
            'has_country_prohibition': False,
            'consolidated_duties': []
        }


def evaluate_assessment_compliance(required_assessments: List[str],
                                   pia_status: str = None,
                                   tia_status: str = None,
                                   hrpr_status: str = None,
                                   case_status: str = None) -> Dict:
    """
    Evaluate if assessment requirements are met.
    STRICT RULES:
    1. Case status MUST be in VALID_CASE_STATUSES
    2. Only "Completed" status = compliant for assessments
    """
    # Check case status validity
    if case_status and case_status not in VALID_CASE_STATUSES:
        return {
            'compliant': False,
            'message': f'NON-COMPLIANT: Case status "{case_status}" is not valid for compliance',
            'required': required_assessments,
            'completed': [],
            'missing': [f'Case Status (current: {case_status}, valid: {VALID_CASE_STATUSES})']
        }

    if not required_assessments:
        return {
            'compliant': True,
            'message': 'COMPLIANT: No specific assessments required',
            'required': [],
            'completed': [],
            'missing': []
        }

    status_map = {
        'PIA': pia_status,
        'TIA': tia_status,
        'HRPR': hrpr_status
    }

    completed = []
    missing = []

    for assessment in required_assessments:
        status = status_map.get(assessment)
        if status and status.lower() == 'completed':
            completed.append(assessment)
        else:
            missing.append(f"{assessment} (status: {status or 'Not Provided'})")

    is_compliant = len(missing) == 0

    if is_compliant:
        message = f"COMPLIANT: All {len(required_assessments)} required assessments are Completed"
    else:
        message = f"NON-COMPLIANT: {len(missing)} assessment(s) not completed: {', '.join(missing)}"

    return {
        'compliant': is_compliant,
        'message': message,
        'required': required_assessments,
        'completed': completed,
        'missing': missing
    }


def validate_precedents(origin: str, receiving: str,
                       purposes: List[str] = None,
                       process_l1: str = None,
                       process_l2: str = None,
                       process_l3: str = None,
                       has_pii: bool = None,
                       required_assessments: List[str] = None,
                       has_country_prohibition: bool = False) -> Dict:
    """
    Validate transfer against historical precedents with STRICT filter matching.
    ONLY searches cases with valid status (Completed, Complete, Active, Published).

    Business Rules:
    1. Country-specific prohibition -> PROHIBITED (overrides everything)
    2. ALL provided filters must match -> find matching cases
    3. NO matching cases -> PROHIBITED (raise governance ticket)
    4. At least ONE matching case with ALL assessments completed -> ALLOWED
    5. All matching cases have incomplete assessments -> PROHIBITED
    """
    # If country-specific prohibition exists, skip precedent search
    if has_country_prohibition:
        return {
            'status': 'country_prohibited',
            'message': 'PROHIBITED: Country-specific rule blocks this transfer regardless of precedents or assessments',
            'matching_cases': 0,
            'compliant_cases': 0,
            'cases': []
        }

    # Search with STRICT filter matching
    matching_cases = search_data_graph_strict(
        origin=origin,
        receiving=receiving,
        purposes=purposes,
        process_l1=process_l1,
        process_l2=process_l2,
        process_l3=process_l3,
        has_pii=has_pii
    )

    total_cases = len(matching_cases)

    if total_cases == 0:
        filters_provided = []
        if purposes:
            filters_provided.append(f"purposes={purposes}")
        if process_l1:
            filters_provided.append(f"process_l1={process_l1}")
        if process_l2:
            filters_provided.append(f"process_l2={process_l2}")
        if process_l3:
            filters_provided.append(f"process_l3={process_l3}")
        if has_pii is not None:
            filters_provided.append(f"has_pii={has_pii}")

        filter_msg = f" with matching filters ({', '.join(filters_provided)})" if filters_provided else ""
        return {
            'status': 'no_precedent',
            'message': f'PROHIBITED: No historical precedent found for {origin} -> {receiving}{filter_msg}. Please raise a governance ticket.',
            'matching_cases': 0,
            'compliant_cases': 0,
            'cases': []
        }

    # Check assessment compliance
    if not required_assessments:
        required_assessments = []

    compliant_cases = []
    for case in matching_cases:
        compliance = evaluate_assessment_compliance(
            required_assessments,
            pia_status=case.get('pia_status'),
            tia_status=case.get('tia_status'),
            hrpr_status=case.get('hrpr_status'),
            case_status=case.get('case_status')
        )

        if compliance['compliant']:
            compliant_cases.append(case)

    compliant_count = len(compliant_cases)

    # DYNAMIC LOGIC: At least ONE compliant case = ALLOWED
    if compliant_count > 0:
        return {
            'status': 'validated',
            'message': f'ALLOWED: Found {total_cases} matching case(s), {compliant_count} have all required assessments completed.',
            'matching_cases': total_cases,
            'compliant_cases': compliant_count,
            'cases': matching_cases[:5]
        }

    # All cases found but none compliant
    return {
        'status': 'non_compliant',
        'message': f'PROHIBITED: Found {total_cases} matching case(s) but NONE have all required assessments completed.',
        'matching_cases': total_cases,
        'compliant_cases': 0,
        'cases': matching_cases[:5]
    }


def search_data_graph_strict(origin: str, receiving: str, purposes: List[str] = None,
                             process_l1: str = None, process_l2: str = None, process_l3: str = None,
                             has_pii: bool = None) -> List[Dict]:
    """
    STRICT precedent search: ALL provided filters must match exactly.
    ONLY searches cases with valid status (Completed, Complete, Active, Published).
    """
    logger.info(f"STRICT search: {origin} -> {receiving}, purposes={purposes}, pii={has_pii}")

    # Build valid status list for WHERE clause
    valid_statuses_str = ', '.join([f"'{s}'" for s in VALID_CASE_STATUSES])

    conditions = []
    params = {}

    if origin:
        conditions.append("origin.name = $origin")
        params['origin'] = origin

    if receiving:
        conditions.append("receiving.name = $receiving")
        params['receiving'] = receiving

    # CRITICAL: Only include valid case statuses
    conditions.append(f"c.case_status IN [{valid_statuses_str}]")

    where_clause = " AND ".join(conditions) if conditions else "true"

    query = f"""
    MATCH (c:Case)-[:ORIGINATES_FROM]->(origin:Country)
    MATCH (c)-[:TRANSFERS_TO]->(receiving:Jurisdiction)
    WHERE {where_clause}
    """

    if purposes and len(purposes) > 0:
        query += """
    WITH c, origin, receiving
    MATCH (c)-[:HAS_PURPOSE]->(purpose:Purpose)
    WITH c, origin, receiving, collect(DISTINCT purpose.name) as case_purposes
    WHERE ALL(p IN $purposes WHERE p IN case_purposes)
        """
        params['purposes'] = purposes

    if process_l1:
        query += """
    WITH c, origin, receiving
    MATCH (c)-[:HAS_PROCESS_L1]->(p1:ProcessL1 {name: $process_l1})
        """
        params['process_l1'] = process_l1

    if process_l2:
        query += """
    WITH c, origin, receiving
    MATCH (c)-[:HAS_PROCESS_L2]->(p2:ProcessL2 {name: $process_l2})
        """
        params['process_l2'] = process_l2

    if process_l3:
        query += """
    WITH c, origin, receiving
    MATCH (c)-[:HAS_PROCESS_L3]->(p3:ProcessL3 {name: $process_l3})
        """
        params['process_l3'] = process_l3

    query += """
    WITH c, origin, receiving LIMIT 1000
    MATCH (c)-[:TRANSFERS_TO]->(recv:Jurisdiction)
    WITH c, origin, receiving, collect(DISTINCT recv.name) as receiving_countries

    OPTIONAL MATCH (c)-[:HAS_PURPOSE]->(purpose:Purpose)
    WITH c, origin, receiving, receiving_countries, collect(DISTINCT purpose.name) as purposes

    OPTIONAL MATCH (c)-[:HAS_PROCESS_L1]->(p1:ProcessL1)
    OPTIONAL MATCH (c)-[:HAS_PROCESS_L2]->(p2:ProcessL2)
    OPTIONAL MATCH (c)-[:HAS_PROCESS_L3]->(p3:ProcessL3)
    WITH c, origin, receiving, receiving_countries, purposes, p1.name as process_l1, p2.name as process_l2, p3.name as process_l3

    OPTIONAL MATCH (c)-[:HAS_PERSONAL_DATA]->(pd:PersonalData)
    WITH c, origin, receiving, receiving_countries, purposes, process_l1, process_l2, process_l3, collect(DISTINCT pd.name) as personal_data_items

    OPTIONAL MATCH (c)-[:HAS_PERSONAL_DATA_CATEGORY]->(pdc:PersonalDataCategory)
    WITH c, origin, receiving, receiving_countries, purposes, process_l1, process_l2, process_l3, personal_data_items, collect(DISTINCT pdc.name) as pdc_items

    OPTIONAL MATCH (c)-[:HAS_CATEGORY]->(cat:Category)
    WITH c, origin, receiving, receiving_countries, purposes, process_l1, process_l2, process_l3, personal_data_items, pdc_items, collect(DISTINCT cat.name) as categories
    """

    if has_pii is True:
        query += "WHERE size(pdc_items) > 0 AND NOT ALL(p IN pdc_items WHERE p IN ['N/A', 'NA', 'null'])\n"
    elif has_pii is False:
        query += "WHERE size(pdc_items) = 0 OR ALL(p IN pdc_items WHERE p IN ['N/A', 'NA', 'null'])\n"

    query += """
    RETURN COALESCE(c.case_id, c.case_ref_id, 'UNKNOWN') as case_id,
           c.eim_id as eim_id,
           c.business_app_id as business_app_id,
           c.app_id as app_id,
           origin.name as origin_country,
           receiving_countries,
           purposes,
           process_l1,
           process_l2,
           process_l3,
           COALESCE(c.pia_module, c.pia_status, 'N/A') as pia_status,
           COALESCE(c.tia_module, c.tia_status, 'N/A') as tia_status,
           COALESCE(c.hrpr_module, c.hrpr_status, 'N/A') as hrpr_status,
           personal_data_items,
           pdc_items,
           categories,
           c.case_status as case_status
    ORDER BY case_id
    LIMIT 1000
    """

    try:
        result = query_with_timeout(data_graph, query, params=params, context="STRICT precedent search")

        cases = []
        if result.result_set:
            for row in result.result_set:
                purposes_list = row[6] if len(row) > 6 and row[6] else []
                process_l1 = row[7] if len(row) > 7 else None
                process_l2 = row[8] if len(row) > 8 else None
                process_l3 = row[9] if len(row) > 9 else None
                personal_data_items = row[13] if len(row) > 13 and row[13] else []
                pdc_items = row[14] if len(row) > 14 and row[14] else []
                categories = row[15] if len(row) > 15 and row[15] else []

                purposes_list = [p for p in purposes_list if p] if purposes_list else []
                personal_data_items = [pd for pd in personal_data_items if pd] if personal_data_items else []
                pdc_items = [pdc for pdc in pdc_items if pdc] if pdc_items else []
                categories = [cat for cat in categories if cat] if categories else []

                has_health = contains_health_data(personal_data_items, pdc_items)
                has_pii_flag = has_pii_data(pdc_items)

                case_data = {
                    'case_id': row[0],
                    'eim_id': row[1],
                    'business_app_id': row[2],
                    'app_id': row[3] if len(row) > 3 else None,
                    'origin_country': row[4],
                    'receiving_countries': row[5] if isinstance(row[5], list) else [row[5]] if row[5] else [],
                    'purposes': purposes_list,
                    'process_l1': process_l1,
                    'process_l2': process_l2,
                    'process_l3': process_l3,
                    'pia_status': row[10],
                    'tia_status': row[11],
                    'hrpr_status': row[12],
                    'personal_data': personal_data_items,
                    'personal_data_categories': pdc_items,
                    'categories': categories,
                    'case_status': row[16] if len(row) > 16 else 'Unknown',
                    'has_pii': has_pii_flag,
                    'has_health_data': has_health
                }
                cases.append(case_data)

        logger.info(f"STRICT search found {len(cases)} exact-match cases (valid status only)")
        return cases

    except Exception as e:
        logger.error(f"Error in strict precedent search: {e}", exc_info=True)
        return []


def search_data_graph(origin: str, receiving: str, purposes: List[str] = None,
                      process_l1: str = None, process_l2: str = None, process_l3: str = None,
                      has_pii: str = None) -> List[Dict]:
    """Query DataTransferGraph for matching cases (partial match for UI search)"""
    logger.info(f"Searching DataTransferGraph: {origin} -> {receiving}")

    valid_statuses_str = ', '.join([f"'{s}'" for s in VALID_CASE_STATUSES])

    conditions = []
    params = {}

    if origin:
        conditions.append("toLower(origin.name) CONTAINS toLower($origin)")
        params['origin'] = origin.lower()

    if receiving:
        conditions.append("toLower(receiving.name) CONTAINS toLower($receiving)")
        params['receiving'] = receiving.lower()

    # Only include valid case statuses
    conditions.append(f"c.case_status IN [{valid_statuses_str}]")

    where_clause = " AND ".join(conditions) if conditions else "true"

    query = f"""
    MATCH (c:Case)-[:ORIGINATES_FROM]->(origin:Country)
    MATCH (c)-[:TRANSFERS_TO]->(receiving:Jurisdiction)
    WHERE {where_clause}
    """

    if purposes and len(purposes) > 0:
        query += """
    WITH c, origin
    MATCH (c)-[:HAS_PURPOSE]->(purpose:Purpose)
    WHERE purpose.name IN $purposes
        """
        params['purposes'] = purposes

    if process_l1:
        query += """
    WITH c, origin
    MATCH (c)-[:HAS_PROCESS_L1]->(p1:ProcessL1 {name: $process_l1})
        """
        params['process_l1'] = process_l1

    if process_l2:
        query += """
    WITH c, origin
    MATCH (c)-[:HAS_PROCESS_L2]->(p2:ProcessL2 {name: $process_l2})
        """
        params['process_l2'] = process_l2

    if process_l3:
        query += """
    WITH c, origin
    MATCH (c)-[:HAS_PROCESS_L3]->(p3:ProcessL3 {name: $process_l3})
        """
        params['process_l3'] = process_l3

    query += """
    WITH c, origin LIMIT 1000
    MATCH (c)-[:TRANSFERS_TO]->(receiving:Jurisdiction)
    WITH c, origin, collect(DISTINCT receiving.name) as receiving_countries

    OPTIONAL MATCH (c)-[:HAS_PURPOSE]->(purpose:Purpose)
    WITH c, origin, receiving_countries, collect(DISTINCT purpose.name) as purposes

    OPTIONAL MATCH (c)-[:HAS_PROCESS_L1]->(p1:ProcessL1)
    OPTIONAL MATCH (c)-[:HAS_PROCESS_L2]->(p2:ProcessL2)
    OPTIONAL MATCH (c)-[:HAS_PROCESS_L3]->(p3:ProcessL3)
    WITH c, origin, receiving_countries, purposes, p1.name as process_l1, p2.name as process_l2, p3.name as process_l3

    OPTIONAL MATCH (c)-[:HAS_PERSONAL_DATA]->(pd:PersonalData)
    WITH c, origin, receiving_countries, purposes, process_l1, process_l2, process_l3, collect(DISTINCT pd.name) as personal_data_items

    OPTIONAL MATCH (c)-[:HAS_PERSONAL_DATA_CATEGORY]->(pdc:PersonalDataCategory)
    WITH c, origin, receiving_countries, purposes, process_l1, process_l2, process_l3, personal_data_items, collect(DISTINCT pdc.name) as pdc_items

    OPTIONAL MATCH (c)-[:HAS_CATEGORY]->(cat:Category)
    WITH c, origin, receiving_countries, purposes, process_l1, process_l2, process_l3, personal_data_items, pdc_items, collect(DISTINCT cat.name) as categories
    """

    if has_pii == 'yes':
        query += "WHERE size(pdc_items) > 0 AND NOT ALL(p IN pdc_items WHERE p IN ['N/A', 'NA', 'null'])\n"
    elif has_pii == 'no':
        query += "WHERE size(pdc_items) = 0 OR ALL(p IN pdc_items WHERE p IN ['N/A', 'NA', 'null'])\n"

    query += """
    RETURN COALESCE(c.case_id, c.case_ref_id, 'UNKNOWN') as case_id,
           c.eim_id as eim_id,
           c.business_app_id as business_app_id,
           origin.name as origin_country,
           receiving_countries,
           purposes,
           process_l1,
           process_l2,
           process_l3,
           COALESCE(c.pia_module, c.pia_status, 'N/A') as pia_module,
           COALESCE(c.tia_module, c.tia_status, 'N/A') as tia_module,
           COALESCE(c.hrpr_module, c.hrpr_status, 'N/A') as hrpr_module,
           personal_data_items,
           pdc_items,
           categories,
           c.case_status as case_status
    ORDER BY case_id
    LIMIT 1000
    """

    try:
        result = query_with_timeout(data_graph, query, params=params, context="UI case search")

        cases = []
        if result.result_set:
            for row in result.result_set:
                purposes = row[5] if len(row) > 5 and row[5] else []
                process_l1 = row[6] if len(row) > 6 else None
                process_l2 = row[7] if len(row) > 7 else None
                process_l3 = row[8] if len(row) > 8 else None
                personal_data_items = row[12] if len(row) > 12 and row[12] else []
                pdc_items = row[13] if len(row) > 13 and row[13] else []
                categories = row[14] if len(row) > 14 and row[14] else []

                purposes = [p for p in purposes if p] if purposes else []
                personal_data_items = [pd for pd in personal_data_items if pd] if personal_data_items else []
                pdc_items = [pdc for pdc in pdc_items if pdc] if pdc_items else []
                categories = [cat for cat in categories if cat] if categories else []

                has_health = contains_health_data(personal_data_items, pdc_items)
                has_pii_flag = has_pii_data(pdc_items)

                case_data = {
                    'case_id': row[0],
                    'eim_id': row[1],
                    'business_app_id': row[2],
                    'origin_country': row[3],
                    'receiving_countries': row[4] if isinstance(row[4], list) else [row[4]] if row[4] else [],
                    'purposes': purposes,
                    'process_l1': process_l1,
                    'process_l2': process_l2,
                    'process_l3': process_l3,
                    'pia_module': row[9],
                    'tia_module': row[10],
                    'hrpr_module': row[11],
                    'personal_data': personal_data_items,
                    'personal_data_categories': pdc_items,
                    'categories': categories,
                    'case_status': row[15] if len(row) > 15 else 'Unknown',
                    'has_pii': has_pii_flag,
                    'has_health_data': has_health
                }
                cases.append(case_data)

        logger.info(f"Found {len(cases)} cases in DataTransferGraph (valid status only)")
        return cases

    except Exception as e:
        logger.error(f"Error querying DataTransferGraph: {e}", exc_info=True)
        return []


def get_all_rules_overview() -> Dict:
    """
    Get all rules for business user overview.
    Returns rules organized by type with aggregated information.
    """
    permission_rules = []
    prohibition_rules = []
    country_specific_rules = []

    # Get prohibition rules from config
    if PROHIBITION_CONFIG and 'prohibition_rules' in PROHIBITION_CONFIG:
        for rule_name, rule_config in PROHIBITION_CONFIG['prohibition_rules'].items():
            if not rule_config.get('enabled', True):
                continue

            rule_overview = {
                'rule_id': rule_config.get('rule_id', rule_name),
                'name': rule_config.get('prohibition_name', rule_name),
                'description': rule_config.get('description', ''),
                'rule_type': 'Prohibition',
                'priority': COUNTRY_RULE_PRIORITY + rule_config.get('priority', 0),
                'origin_countries': rule_config.get('origin_countries', []),
                'receiving_countries': rule_config.get('receiving_countries', []),
                'requires_pii': rule_config.get('requires_pii', False),
                'requires_health_data': rule_config.get('requires_health_data', False),
                'duties': rule_config.get('duties', []),
                'is_country_specific': True
            }
            country_specific_rules.append(rule_overview)
            prohibition_rules.append(rule_overview)

    # Get rules from RulesGraph
    try:
        query = """
        MATCH (r:Rule)
        OPTIONAL MATCH (r)-[:HAS_PERMISSION]->(perm:Permission)
        OPTIONAL MATCH (perm)-[:CAN_HAVE_DUTY]->(perm_duty:Duty)
        OPTIONAL MATCH (r)-[:HAS_PROHIBITION]->(prohib:Prohibition)
        OPTIONAL MATCH (prohib)-[:CAN_HAVE_DUTY]->(prohib_duty:Duty)
        OPTIONAL MATCH (r)-[:TRIGGERED_BY_ORIGIN]->(origin_group:CountryGroup)
        OPTIONAL MATCH (r)-[:TRIGGERED_BY_RECEIVING]->(recv_group:CountryGroup)
        RETURN r.rule_id as rule_id,
               r.description as description,
               r.priority as priority,
               r.has_pii_required as requires_pii,
               r.health_data_required as requires_health_data,
               perm.name as permission_name,
               collect(DISTINCT perm_duty.name) as perm_duties,
               prohib.name as prohibition_name,
               collect(DISTINCT prohib_duty.name) as prohib_duties,
               collect(DISTINCT origin_group.name) as origin_groups,
               collect(DISTINCT recv_group.name) as receiving_groups
        ORDER BY r.priority
        """

        result = query_with_timeout(
            rules_graph, query,
            context="Get rules overview",
            use_cache=True,
            cache_key="rules_overview"
        )

        if result.result_set:
            for row in result.result_set:
                rule_id = row[0]
                description = row[1]
                priority = row[2] or 0
                requires_pii = row[3] or False
                requires_health_data = row[4] or False
                permission_name = row[5]
                perm_duties = [d for d in (row[6] or []) if d]
                prohibition_name = row[7]
                prohib_duties = [d for d in (row[8] or []) if d]
                origin_groups = [g for g in (row[9] or []) if g]
                receiving_groups = [g for g in (row[10] or []) if g]

                if permission_name:
                    rule_overview = {
                        'rule_id': rule_id,
                        'name': permission_name,
                        'description': description,
                        'rule_type': 'Permission',
                        'priority': priority,
                        'origin_countries': origin_groups,
                        'receiving_countries': receiving_groups,
                        'requires_pii': requires_pii,
                        'requires_health_data': requires_health_data,
                        'duties': perm_duties,
                        'is_country_specific': False
                    }
                    permission_rules.append(rule_overview)

                if prohibition_name:
                    rule_overview = {
                        'rule_id': rule_id,
                        'name': prohibition_name,
                        'description': description,
                        'rule_type': 'Prohibition',
                        'priority': priority,
                        'origin_countries': origin_groups,
                        'receiving_countries': receiving_groups,
                        'requires_pii': requires_pii,
                        'requires_health_data': requires_health_data,
                        'duties': prohib_duties,
                        'is_country_specific': False
                    }
                    prohibition_rules.append(rule_overview)

    except Exception as e:
        logger.error(f"Error getting rules overview: {e}")

    return {
        'permission_rules': permission_rules,
        'prohibition_rules': prohibition_rules,
        'country_specific_rules': country_specific_rules,
        'total_rules': len(permission_rules) + len(prohibition_rules)
    }


# ============================================================================
# API ENDPOINTS
# ============================================================================

@app.get("/", response_class=HTMLResponse, tags=["Frontend"])
async def index():
    """Serve the dashboard HTML"""
    template_path = Path(__file__).parent / "templates" / "dashboard.html"
    if template_path.exists():
        return template_path.read_text()
    else:
        return "<h1>Dashboard template not found</h1><p>Expected at: templates/dashboard.html</p>"


@app.get("/rules", response_class=HTMLResponse, tags=["Frontend"])
async def rules_page():
    """Serve the Rules Overview page for business users"""
    template_path = Path(__file__).parent / "templates" / "rules_overview.html"
    if template_path.exists():
        return template_path.read_text()
    else:
        return "<h1>Rules Overview template not found</h1><p>Expected at: templates/rules_overview.html</p>"


@app.get("/api/rules-overview", response_model=RulesOverviewResponse, tags=["Rules"])
async def get_rules_overview():
    """
    Get all compliance rules overview for business users.
    Returns rules organized by type (Permission, Prohibition, Country-Specific)
    with aggregated information suitable for display in accordions.
    """
    try:
        overview = get_all_rules_overview()
        return {
            'success': True,
            'total_rules': overview['total_rules'],
            'permission_rules': overview['permission_rules'],
            'prohibition_rules': overview['prohibition_rules'],
            'country_specific_rules': overview['country_specific_rules']
        }
    except Exception as e:
        logger.error(f"Error getting rules overview: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/purposes", response_model=PurposesResponse, tags=["Metadata"])
async def get_purposes():
    """Get all available legal processing purposes from the graph"""
    try:
        query = "MATCH (p:Purpose) RETURN DISTINCT p.name as name ORDER BY name"
        result = query_with_timeout(data_graph, query, context="Get purposes", use_cache=True, cache_key="purposes")
        purposes = [row[0] for row in result.result_set] if result.result_set else []
        return {'success': True, 'purposes': purposes}
    except Exception as e:
        logger.error(f"Error fetching purposes: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/processes", response_model=ProcessesResponse, tags=["Metadata"])
async def get_processes():
    """Get all available process levels (L1, L2, L3) from the graph"""
    try:
        query_l1 = "MATCH (p:ProcessL1) RETURN DISTINCT p.name as name ORDER BY name"
        result_l1 = query_with_timeout(data_graph, query_l1, context="Get ProcessL1", use_cache=True, cache_key="process_l1")
        process_l1 = [row[0] for row in result_l1.result_set] if result_l1.result_set else []

        query_l2 = "MATCH (p:ProcessL2) RETURN DISTINCT p.name as name ORDER BY name"
        result_l2 = query_with_timeout(data_graph, query_l2, context="Get ProcessL2", use_cache=True, cache_key="process_l2")
        process_l2 = [row[0] for row in result_l2.result_set] if result_l2.result_set else []

        query_l3 = "MATCH (p:ProcessL3) RETURN DISTINCT p.name as name ORDER BY name"
        result_l3 = query_with_timeout(data_graph, query_l3, context="Get ProcessL3", use_cache=True, cache_key="process_l3")
        process_l3 = [row[0] for row in result_l3.result_set] if result_l3.result_set else []

        return {'success': True, 'process_l1': process_l1, 'process_l2': process_l2, 'process_l3': process_l3}
    except Exception as e:
        logger.error(f"Error fetching processes: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/countries", response_model=CountriesResponse, tags=["Metadata"])
async def get_countries():
    """Get all unique countries from the data graph"""
    try:
        query_origin = "MATCH (c:Country) RETURN DISTINCT c.name as name ORDER BY name"
        result_origin = query_with_timeout(data_graph, query_origin, context="Get origin countries", use_cache=True, cache_key="origin_countries")

        query_receiving = "MATCH (j:Jurisdiction) RETURN DISTINCT j.name as name ORDER BY name"
        result_receiving = query_with_timeout(data_graph, query_receiving, context="Get receiving countries", use_cache=True, cache_key="receiving_countries")

        origin_countries = [row[0] for row in result_origin.result_set] if result_origin.result_set else []
        receiving_countries = [row[0] for row in result_receiving.result_set] if result_receiving.result_set else []

        all_countries = sorted(list(set(origin_countries + receiving_countries)))

        return {
            'success': True,
            'countries': all_countries,
            'origin_countries': origin_countries,
            'receiving_countries': receiving_countries
        }
    except Exception as e:
        logger.error(f"Error fetching countries: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/evaluate-rules", tags=["Compliance"])
async def evaluate_rules(request: RulesEvaluationRequest):
    """
    Evaluate compliance rules with precedent validation and assessment compliance.

    Decision Logic (Priority Order):
    1. Country-Specific Prohibitions -> PROHIBITED (absolute, overrides PIA/TIA/HRPR)
    2. Rule-Level Prohibitions -> PROHIBITED
    3. No Precedent Found -> PROHIBITED (raise governance ticket)
    4. PIA/TIA/HRPR Match with Completed Status -> ALLOWED (dynamic filtering)
    5. All matching cases have incomplete assessments -> PROHIBITED

    Note: Country-specific rules (e.g., US to China) take precedence over PIA/TIA/HRPR
    assessments. Even with completed assessments, country rules can block transfers.
    """
    try:
        if not request.origin_country or not request.receiving_country:
            raise HTTPException(status_code=400, detail="origin_country and receiving_country are required")

        # Detect health data
        has_health_data_detected = False
        health_detection_details = {}

        if request.other_metadata:
            health_detection_details = detect_health_data_from_metadata(request.other_metadata, verbose=True)
            has_health_data_detected = health_detection_details['detected']

        has_pii = request.pii

        logger.info(f"Evaluating: {request.origin_country} -> {request.receiving_country}, "
                   f"PII={has_pii}, Health={has_health_data_detected}")

        # Query triggered rules (includes country-specific check)
        rules_result = query_triggered_rules_deontic(
            request.origin_country.strip(),
            request.receiving_country.strip(),
            has_pii,
            has_health_data_detected
        )

        has_country_prohibition = rules_result.get('has_country_prohibition', False)

        # PRIORITY 1: Country-specific prohibition (overrides everything)
        if has_country_prohibition:
            country_rules = [r for r in rules_result['triggered_rules'] if r.get('is_country_specific')]
            prohibition_reasons = [r['prohibition']['name'] for r in country_rules if r.get('prohibition')]

            return {
                'success': True,
                'transfer_status': 'PROHIBITED',
                'transfer_blocked': True,
                'blocked_reason': f"Country-specific prohibition: {', '.join(prohibition_reasons)}. This rule takes precedence over PIA/TIA/HRPR assessments.",
                'triggered_rules': rules_result['triggered_rules'],
                'total_rules_triggered': rules_result['total_rules_triggered'],
                'has_prohibitions': True,
                'has_country_prohibition': True,
                'consolidated_duties': rules_result['consolidated_duties'],
                'precedent_validation': {
                    'status': 'country_prohibited',
                    'message': 'Skipped - country-specific prohibition takes precedence',
                    'matching_cases': 0,
                    'compliant_cases': 0
                },
                'assessment_compliance': {
                    'compliant': False,
                    'message': 'Blocked by country-specific prohibition (overrides assessments)'
                }
            }

        # PRIORITY 2: Other rule-level prohibitions
        if rules_result['has_prohibitions']:
            prohibited_rules = [r for r in rules_result['triggered_rules'] if r.get('is_blocked')]
            prohibition_reasons = [r['prohibition']['name'] for r in prohibited_rules if r.get('prohibition')]

            return {
                'success': True,
                'transfer_status': 'PROHIBITED',
                'transfer_blocked': True,
                'blocked_reason': f"Rule-level prohibition: {', '.join(prohibition_reasons)}",
                'triggered_rules': rules_result['triggered_rules'],
                'total_rules_triggered': rules_result['total_rules_triggered'],
                'has_prohibitions': True,
                'has_country_prohibition': False,
                'consolidated_duties': rules_result['consolidated_duties'],
                'precedent_validation': {
                    'status': 'skipped',
                    'message': 'Skipped due to rule-level prohibition',
                    'matching_cases': 0,
                    'compliant_cases': 0
                },
                'assessment_compliance': {
                    'compliant': False,
                    'message': 'Blocked by prohibition rule'
                }
            }

        # Extract required assessments from permission rules
        required_assessments = set()
        for rule in rules_result['triggered_rules']:
            if rule.get('permission') and rule['permission'].get('duties'):
                for duty in rule['permission']['duties']:
                    if duty.get('module'):
                        if 'pia' in duty['module'].lower():
                            required_assessments.add('PIA')
                        elif 'tia' in duty['module'].lower():
                            required_assessments.add('TIA')
                        elif 'hrpr' in duty['module'].lower():
                            required_assessments.add('HRPR')

        required_assessments = list(required_assessments)

        # PRIORITY 3-5: Validate against precedents
        precedent_validation = validate_precedents(
            origin=request.origin_country.strip(),
            receiving=request.receiving_country.strip(),
            purposes=request.purpose_of_processing,
            process_l1=request.process_l1,
            process_l2=request.process_l2,
            process_l3=request.process_l3,
            has_pii=has_pii,
            required_assessments=required_assessments,
            has_country_prohibition=has_country_prohibition
        )

        # Determine final status
        transfer_blocked = False
        transfer_status = 'ALLOWED'
        blocked_reason = None

        if precedent_validation['status'] == 'no_precedent':
            transfer_blocked = True
            transfer_status = 'PROHIBITED'
            blocked_reason = precedent_validation['message']
        elif precedent_validation['status'] == 'non_compliant':
            transfer_blocked = True
            transfer_status = 'PROHIBITED'
            blocked_reason = precedent_validation['message']
        elif precedent_validation['status'] == 'validated':
            transfer_blocked = False
            transfer_status = 'ALLOWED'

        assessment_compliance = {
            'compliant': not transfer_blocked,
            'message': precedent_validation['message'] if transfer_blocked else 'Transfer validated by precedents',
            'required': required_assessments
        }

        return {
            'success': True,
            'transfer_status': transfer_status,
            'transfer_blocked': transfer_blocked,
            'blocked_reason': blocked_reason,
            'triggered_rules': rules_result['triggered_rules'],
            'total_rules_triggered': rules_result['total_rules_triggered'],
            'has_prohibitions': False,
            'has_country_prohibition': False,
            'consolidated_duties': rules_result['consolidated_duties'],
            'precedent_validation': precedent_validation,
            'assessment_compliance': assessment_compliance
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error evaluating rules: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/search-cases", response_model=SearchCasesResponse, tags=["Cases"])
async def search_cases(request: SearchCasesRequest):
    """
    Search for data transfer cases matching the specified criteria.
    ONLY returns cases with valid status (Completed, Complete, Active, Published).
    """
    try:
        origin = request.origin_country.strip() if request.origin_country else None
        receiving = request.receiving_country.strip() if request.receiving_country else None
        process_l1 = request.process_l1.strip() if request.process_l1 else None
        process_l2 = request.process_l2.strip() if request.process_l2 else None
        process_l3 = request.process_l3.strip() if request.process_l3 else None

        has_pii_str = None
        if request.pii is True:
            has_pii_str = 'yes'
        elif request.pii is False:
            has_pii_str = 'no'

        cases = search_data_graph(
            origin, receiving,
            request.purpose_of_processing if request.purpose_of_processing else None,
            process_l1, process_l2, process_l3,
            has_pii_str
        )

        return {'success': True, 'cases': cases, 'total_cases': len(cases)}

    except Exception as e:
        logger.error(f"Error searching cases: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/stats", response_model=StatsResponse, tags=["Metadata"])
async def get_stats():
    """Get dashboard statistics"""
    try:
        # Count only valid status cases
        valid_statuses_str = ', '.join([f"'{s}'" for s in VALID_CASE_STATUSES])

        query_cases = f"MATCH (c:Case) WHERE c.case_status IN [{valid_statuses_str}] RETURN count(c) as count"
        result_cases = query_with_timeout(data_graph, query_cases, context="Count valid cases")
        total_cases = result_cases.result_set[0][0] if result_cases.result_set else 0

        query_all_cases = "MATCH (c:Case) RETURN count(c) as count"
        result_all = query_with_timeout(data_graph, query_all_cases, context="Count all cases")
        all_cases = result_all.result_set[0][0] if result_all.result_set else 0

        query_countries = "MATCH (c:Country) RETURN count(c) as count"
        result_countries = query_with_timeout(data_graph, query_countries, context="Count countries")
        total_countries = result_countries.result_set[0][0] if result_countries.result_set else 0

        query_jurisdictions = "MATCH (j:Jurisdiction) RETURN count(j) as count"
        result_jurisdictions = query_with_timeout(data_graph, query_jurisdictions, context="Count jurisdictions")
        total_jurisdictions = result_jurisdictions.result_set[0][0] if result_jurisdictions.result_set else 0

        query_pii = f"""
        MATCH (c:Case)-[:HAS_PERSONAL_DATA_CATEGORY]->(pdc:PersonalDataCategory)
        WHERE c.case_status IN [{valid_statuses_str}]
        AND pdc.name <> 'N/A' AND pdc.name <> 'NA' AND pdc.name <> 'null'
        RETURN count(DISTINCT c) as count
        """
        result_pii = query_with_timeout(data_graph, query_pii, context="Count cases with PII")
        cases_with_pii = result_pii.result_set[0][0] if result_pii.result_set else 0

        return {
            'success': True,
            'stats': {
                'total_cases': total_cases,
                'all_cases_in_graph': all_cases,
                'total_countries': total_countries,
                'total_jurisdictions': total_jurisdictions,
                'cases_with_pii': cases_with_pii
            }
        }

    except Exception as e:
        logger.error(f"Error fetching stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/all-dropdown-values", tags=["Metadata"])
async def get_all_dropdown_values():
    """Get all dropdown values in a single call"""
    try:
        query_origin = "MATCH (c:Country) RETURN DISTINCT c.name as name ORDER BY name"
        result_origin = query_with_timeout(data_graph, query_origin, context="Get all origin countries", use_cache=True, cache_key="all_origin")

        query_receiving = "MATCH (j:Jurisdiction) RETURN DISTINCT j.name as name ORDER BY name"
        result_receiving = query_with_timeout(data_graph, query_receiving, context="Get all receiving countries", use_cache=True, cache_key="all_receiving")

        origin_countries = [row[0] for row in result_origin.result_set] if result_origin.result_set else []
        receiving_countries = [row[0] for row in result_receiving.result_set] if result_receiving.result_set else []
        all_countries = sorted(list(set(origin_countries + receiving_countries)))

        query_purposes = "MATCH (p:Purpose) RETURN DISTINCT p.name as name ORDER BY name"
        result_purposes = query_with_timeout(data_graph, query_purposes, context="Get all purposes", use_cache=True, cache_key="all_purposes")
        purposes = [row[0] for row in result_purposes.result_set] if result_purposes.result_set else []

        query_l1 = "MATCH (p:ProcessL1) RETURN DISTINCT p.name as name ORDER BY name"
        result_l1 = query_with_timeout(data_graph, query_l1, context="Get all ProcessL1", use_cache=True, cache_key="all_l1")
        process_l1 = [row[0] for row in result_l1.result_set] if result_l1.result_set else []

        query_l2 = "MATCH (p:ProcessL2) RETURN DISTINCT p.name as name ORDER BY name"
        result_l2 = query_with_timeout(data_graph, query_l2, context="Get all ProcessL2", use_cache=True, cache_key="all_l2")
        process_l2 = [row[0] for row in result_l2.result_set] if result_l2.result_set else []

        query_l3 = "MATCH (p:ProcessL3) RETURN DISTINCT p.name as name ORDER BY name"
        result_l3 = query_with_timeout(data_graph, query_l3, context="Get all ProcessL3", use_cache=True, cache_key="all_l3")
        process_l3 = [row[0] for row in result_l3.result_set] if result_l3.result_set else []

        query_pdc = "MATCH (pdc:PersonalDataCategory) RETURN DISTINCT pdc.name as name ORDER BY name"
        result_pdc = query_with_timeout(data_graph, query_pdc, context="Get all PersonalDataCategories", use_cache=True, cache_key="all_pdc")
        personal_data_categories = [row[0] for row in result_pdc.result_set] if result_pdc.result_set else []

        return {
            'success': True,
            'countries': all_countries,
            'origin_countries': origin_countries,
            'receiving_countries': receiving_countries,
            'purposes': purposes,
            'process_l1': process_l1,
            'process_l2': process_l2,
            'process_l3': process_l3,
            'personal_data_categories': personal_data_categories,
            'valid_case_statuses': VALID_CASE_STATUSES
        }

    except Exception as e:
        logger.error(f"Error fetching all dropdown values: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/test-rules-graph", tags=["Testing"])
async def test_rules_graph():
    """Test endpoint to verify RulesGraph is properly configured"""
    try:
        query = """
        MATCH (cg:CountryGroup) WITH count(cg) as groups
        MATCH (c:Country) WITH groups, count(c) as countries
        MATCH (r:Rule) WITH groups, countries, count(r) as rules
        MATCH (a:Action) WITH groups, countries, rules, count(a) as actions
        MATCH (p:Permission) WITH groups, countries, rules, actions, count(p) as permissions
        MATCH (pr:Prohibition) WITH groups, countries, rules, actions, permissions, count(pr) as prohibitions
        MATCH (d:Duty) WITH groups, countries, rules, actions, permissions, prohibitions, count(d) as duties
        RETURN groups, countries, rules, actions, permissions, prohibitions, duties
        """
        result = query_with_timeout(rules_graph, query, context="Test rules graph")

        if result.result_set:
            groups, countries, rules, actions, permissions, prohibitions, duties = result.result_set[0]

            # Add config-based prohibition count
            config_prohibitions = len(PROHIBITION_CONFIG.get('prohibition_rules', {})) if PROHIBITION_CONFIG else 0

            return {
                'success': True,
                'rules_graph_stats': {
                    'country_groups': groups,
                    'countries': countries,
                    'rules': rules,
                    'actions': actions,
                    'permissions': permissions,
                    'prohibitions': prohibitions,
                    'duties': duties,
                    'config_prohibitions': config_prohibitions
                },
                'message': 'Deontic RulesGraph is operational'
            }
        else:
            raise HTTPException(status_code=500, detail='RulesGraph is empty. Run build_rules_graph_deontic.py first.')

    except Exception as e:
        logger.error(f"Error testing RulesGraph: {e}")
        raise HTTPException(status_code=500, detail=f'RulesGraph may not be built. Run build_rules_graph_deontic.py. Error: {str(e)}')


@app.get("/api/cache/clear", tags=["Admin"])
async def clear_cache():
    """Clear the query cache"""
    global _query_cache, _cache_timestamps
    _query_cache = {}
    _cache_timestamps = {}
    return {'success': True, 'message': 'Cache cleared'}


if __name__ == '__main__':
    import uvicorn

    logger.info("=" * 70)
    logger.info("DEONTIC COMPLIANCE API - FastAPI (Optimized)")
    logger.info("=" * 70)
    logger.info("Features:")
    logger.info("  - Case status filtering (Completed/Complete/Active/Published)")
    logger.info("  - Country-specific rules take precedence over PIA/TIA/HRPR")
    logger.info("  - Dynamic PIA/TIA/HRPR rules evaluation")
    logger.info("  - Query caching for large graphs")
    logger.info("  - Rules Overview endpoint for business users")
    logger.info("")
    logger.info("Starting server on http://0.0.0.0:5001")
    logger.info("Swagger UI: http://localhost:5001/docs")
    logger.info("ReDoc: http://localhost:5001/redoc")
    logger.info("Rules Overview: http://localhost:5001/rules")
    logger.info("=" * 70)

    uvicorn.run(app, host="0.0.0.0", port=5001, log_level="info")
