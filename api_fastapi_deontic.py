"""
Data Transfer Compliance Dashboard - FastAPI Backend with Deontic Logic
Uses formal policy framework: Actions, Permissions, Prohibitions, Duties
Swagger UI at /docs and ReDoc at /redoc
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from typing import Dict, List, Optional
from falkordb import FalkorDB
import logging
from pathlib import Path
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load health data configuration
HEALTH_CONFIG_PATH = Path(__file__).parent / "health_data_config.json"
HEALTH_CONFIG = {}
if HEALTH_CONFIG_PATH.exists():
    with open(HEALTH_CONFIG_PATH, 'r') as f:
        HEALTH_CONFIG = json.load(f)
        logger.info(f"✓ Loaded health data config: {len(HEALTH_CONFIG['detection_rules']['keywords'])} keywords, "
                   f"{len(HEALTH_CONFIG['detection_rules']['patterns'])} patterns")
else:
    logger.warning("⚠️  health_data_config.json not found - using fallback keywords")

# Initialize FastAPI app
app = FastAPI(
    title="Data Transfer Compliance API - Deontic Logic",
    description="Graph-based compliance engine using deontic logic framework (Actions, Permissions, Prohibitions, Duties)",
    version="3.0.0",
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
    is_blocked: bool = False  # True if has prohibition
    origin_group: str = ""
    receiving_group: str = ""


class RulesEvaluationRequest(BaseModel):
    """Request to evaluate compliance rules - all fields are optional for dynamic evaluation"""
    origin_country: Optional[str] = Field(None, description="Originating country name (e.g., 'United States', 'Germany')")
    receiving_country: Optional[str] = Field(None, description="Receiving country name (e.g., 'China', 'Canada')")
    pii: Optional[bool] = Field(None, description="Whether transfer contains Personal Identifiable Information")
    purpose_of_processing: Optional[List[str]] = Field(None, description="Purpose(s) of data processing (e.g., ['Marketing', 'Analytics'])")
    process_l1: Optional[str] = Field(None, description="Process area Level 1 (e.g., 'Finance', 'HR')")
    process_l2: Optional[str] = Field(None, description="Process function Level 2 (e.g., 'Payroll', 'Recruitment')")
    process_l3: Optional[str] = Field(None, description="Process detail Level 3 (e.g., 'Salary Processing')")
    other_metadata: Optional[Dict[str, str]] = Field(
        None,
        description="Additional metadata as key-value pairs. Example: {'patient_records': 'medical history', 'diagnosis_codes': 'ICD-10'}. System automatically detects health data from column names/descriptions."
    )

    class Config:
        json_schema_extra = {
            "example": {
                "origin_country": "United States",
                "receiving_country": "Canada",
                "pii": True,
                "purpose_of_processing": ["Analytics", "Marketing"],
                "process_l1": "Sales",
                "process_l2": "Customer Management",
                "process_l3": "CRM Operations",
                "other_metadata": {
                    "customer_email": "email addresses",
                    "customer_name": "full names",
                    "transaction_history": "purchase records"
                }
            }
        }


class RulesEvaluationResponse(BaseModel):
    """Response from rules evaluation"""
    success: bool = True
    triggered_rules: List[TriggeredRule]
    total_rules_triggered: int
    has_prohibitions: bool = False
    consolidated_duties: List[Duty] = Field(default_factory=list)


class SearchCasesRequest(BaseModel):
    """Request to search for cases - all fields are optional for flexible searching"""
    origin_country: Optional[str] = Field(None, description="Originating country (partial match, e.g., 'United', 'Germany')")
    receiving_country: Optional[str] = Field(None, description="Receiving country (partial match, e.g., 'China', 'Can')")
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


# ============================================================================
# CORE LOGIC FUNCTIONS
# ============================================================================

def query_triggered_rules_deontic(origin: str, receiving: str, has_pii: bool = None, has_health_data: bool = None) -> Dict:
    """
    Query the RulesGraph using deontic logic structure
    Returns rules with their actions, permissions, prohibitions, and duties

    Args:
        origin: Origin country name
        receiving: Receiving country name
        has_pii: Whether transfer contains PII. None is treated as False (no PII detected)
        has_health_data: Whether transfer contains health data. None is treated as False (no health data detected)

    Note on NULL semantics:
        - None/null values are converted to False for filtering
        - False means "explicitly verified as absent" or "not detected"
        - True means "explicitly verified as present" or "detected"
        - Rules with has_pii_required=True only trigger when has_pii=True
        - Rules with health_data_required=True only trigger when has_health_data=True
    """
    logger.info(f"Querying Deontic RulesGraph for: {origin} → {receiving}, has_pii={has_pii}, has_health_data={has_health_data}")

    # Query with deontic structure
    query = """
    // Get origin country's groups
    MATCH (origin:Country {name: $origin_country})-[:BELONGS_TO]->(origin_group:CountryGroup)
    WITH collect(DISTINCT origin_group.name) as origin_groups

    // Get receiving country's groups
    MATCH (receiving:Country {name: $receiving_country})-[:BELONGS_TO]->(receiving_group:CountryGroup)
    WITH origin_groups, collect(DISTINCT receiving_group.name) as receiving_groups

    // Match all rules and check their conditions
    MATCH (r:Rule)

    // Get rule's origin groups (if any)
    OPTIONAL MATCH (r)-[:TRIGGERED_BY_ORIGIN]->(r_origin:CountryGroup)
    WITH r, origin_groups, receiving_groups, collect(DISTINCT r_origin.name) as rule_origin_groups

    // Get rule's receiving groups (if any)
    OPTIONAL MATCH (r)-[:TRIGGERED_BY_RECEIVING]->(r_receiving:CountryGroup)
    WITH r, origin_groups, receiving_groups, rule_origin_groups,
         collect(DISTINCT r_receiving.name) as rule_receiving_groups

    // Filter rules based on match logic
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

    // Only keep rules where both origin and receiving match
    WHERE origin_matches AND receiving_matches
          AND (NOT r.has_pii_required OR $has_pii = true)
          AND (NOT r.health_data_required OR $has_health_data = true)

    // Get action
    OPTIONAL MATCH (r)-[:HAS_ACTION]->(action:Action)

    // Get permission and its duties
    OPTIONAL MATCH (r)-[:HAS_PERMISSION]->(perm:Permission)
    OPTIONAL MATCH (perm)-[:CAN_HAVE_DUTY]->(perm_duty:Duty)

    // Get prohibition and its duties
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
        result = rules_graph.query(query, params={
            'origin_country': origin,
            'receiving_country': receiving,
            'has_pii': has_pii if has_pii is not None else False,
            'has_health_data': has_health_data if has_health_data is not None else False
        })

        triggered_rules = []
        consolidated_duties_map = {}
        has_prohibitions = False

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

                # Build action
                action_obj = None
                if action_name:
                    action_obj = {
                        'name': action_name,
                        'description': action_description or ''
                    }

                # Build permission with duties
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
                            # Add to consolidated duties
                            consolidated_duties_map[duty['name']] = duty_obj

                    permission_obj = {
                        'name': permission_name,
                        'description': permission_description or '',
                        'duties': perm_duties_list
                    }

                # Build prohibition with duties
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
                            # Add to consolidated duties
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
                    'origin_group': '',
                    'receiving_group': ''
                })

        logger.info(f"Triggered {len(triggered_rules)} rules, {has_prohibitions=}")

        return {
            'triggered_rules': triggered_rules,
            'total_rules_triggered': len(triggered_rules),
            'has_prohibitions': has_prohibitions,
            'consolidated_duties': list(consolidated_duties_map.values())
        }

    except Exception as e:
        logger.error(f"Error querying RulesGraph: {e}", exc_info=True)
        return {
            'triggered_rules': [],
            'total_rules_triggered': 0,
            'has_prohibitions': False,
            'consolidated_duties': []
        }


def detect_health_data_from_metadata(other_metadata: Optional[Dict[str, str]], verbose: bool = True) -> Dict[str, any]:
    """
    Automatically detect if metadata contains health-related information
    Analyzes both column names (keys) and descriptions (values)
    Uses comprehensive health data configuration with word boundary matching

    Args:
        other_metadata: Dictionary with column names as keys and descriptions as values
        verbose: If True, returns detailed detection info; if False, returns simple boolean

    Returns:
        Dictionary with detection results:
        {
            'detected': bool,
            'matched_keywords': list,
            'matched_patterns': list,
            'matched_fields': list
        }

    Example:
        {'patient_id': 'medical record number'}
        -> {'detected': True, 'matched_keywords': ['patient', 'medical'], ...}
    """
    if not other_metadata:
        return {'detected': False, 'matched_keywords': [], 'matched_patterns': [], 'matched_fields': []}

    import re

    # Load keywords from config, fallback to basic list
    if HEALTH_CONFIG and 'detection_rules' in HEALTH_CONFIG:
        health_keywords = HEALTH_CONFIG['detection_rules']['keywords']
        health_patterns = HEALTH_CONFIG['detection_rules'].get('patterns', [])
    else:
        # Fallback keywords if config not loaded
        health_keywords = [
            'health', 'medical', 'patient', 'diagnosis', 'treatment', 'prescription',
            'clinical', 'hospital', 'doctor', 'disease', 'illness', 'medication',
            'healthcare', 'wellness', 'fitness', 'biometric', 'genetic', 'vaccine',
            'surgery', 'therapy', 'pharmaceutical', 'radiology', 'lab', 'laboratory'
        ]
        health_patterns = [
            r'icd-?\d+',
            r'cpt-?\d+',
            r'diagnosis code',
            r'medical record'
        ]

    matched_keywords = []
    matched_patterns = []
    matched_fields = []

    # Check each metadata field
    for key, value in other_metadata.items():
        # Normalize text: replace underscores and hyphens with spaces for better keyword matching
        # This allows "patient_id" to match "patient" and "diagnosis-codes" to match "diagnosis"
        field_text = f"{key} {value}".lower()
        normalized_text = field_text.replace('_', ' ').replace('-', ' ')
        field_matched = False

        # Check keywords with word boundaries on normalized text
        for keyword in health_keywords:
            # Use word boundaries on normalized text (underscores replaced with spaces)
            if re.search(r'\b' + re.escape(keyword.lower()) + r'\b', normalized_text):
                if keyword not in matched_keywords:
                    matched_keywords.append(keyword)
                field_matched = True

        # Check patterns on original text (to catch "ICD-10" style patterns)
        for pattern in health_patterns:
            if re.search(pattern, field_text, re.IGNORECASE):
                if pattern not in matched_patterns:
                    matched_patterns.append(pattern)
                field_matched = True

        if field_matched:
            matched_fields.append({'key': key, 'value': value})

    detected = len(matched_keywords) > 0 or len(matched_patterns) > 0

    result = {
        'detected': detected,
        'matched_keywords': matched_keywords,
        'matched_patterns': matched_patterns,
        'matched_fields': matched_fields
    }

    if verbose and detected:
        logger.info(f"🏥 Health data detected: {len(matched_keywords)} keywords, "
                   f"{len(matched_patterns)} patterns in {len(matched_fields)} fields")
        logger.info(f"   Matched keywords: {', '.join(matched_keywords[:5])}{'...' if len(matched_keywords) > 5 else ''}")
        logger.info(f"   Matched fields: {', '.join([f['key'] for f in matched_fields])}")

    return result


def contains_health_data(personal_data: List[str], personal_data_categories: List[str]) -> bool:
    """
    Check if personal data or categories contain health-related information
    Uses word boundary matching to avoid false positives

    Note: This is used for DataTransferGraph case search.
    For rules evaluation API, use detect_health_data_from_metadata() instead.
    """
    import re

    health_keywords = [
        'health', 'medical', 'patient', 'diagnosis', 'treatment', 'prescription',
        'clinical', 'hospital', 'doctor', 'disease', 'illness', 'medication',
        'healthcare', 'wellness', 'fitness', 'biometric', 'genetic'
    ]

    all_data = personal_data + personal_data_categories
    all_data_lower = [item.lower() for item in all_data if item]

    # Use word boundary matching to avoid false positives like "doctorate" matching "doctor"
    for data_item in all_data_lower:
        for keyword in health_keywords:
            # Match whole words only using word boundaries
            if re.search(r'\b' + re.escape(keyword) + r'\b', data_item):
                return True

    return False


def search_data_graph(origin: str, receiving: str, purposes: List[str] = None,
                      process_l1: str = None, process_l2: str = None, process_l3: str = None,
                      has_pii: str = None) -> List[Dict]:
    """Query DataTransferGraph for matching cases"""
    logger.info(f"Searching DataTransferGraph: {origin} → {receiving}, purposes={purposes}, processes={process_l1}/{process_l2}/{process_l3}")

    conditions = []
    params = {}

    if origin:
        conditions.append("toLower(origin.name) CONTAINS toLower($origin)")
        params['origin'] = origin.lower()

    if receiving:
        conditions.append("toLower(receiving.name) CONTAINS toLower($receiving)")
        params['receiving'] = receiving.lower()

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
    WITH c, origin
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
        query += "WHERE size(personal_data_items) > 0\n"
    elif has_pii == 'no':
        query += "WHERE size(personal_data_items) = 0\n"

    query += """
    RETURN c.case_id as case_id,
           c.eim_id as eim_id,
           c.business_app_id as business_app_id,
           origin.name as origin_country,
           receiving_countries,
           purposes,
           process_l1,
           process_l2,
           process_l3,
           c.pia_module as pia_module,
           c.tia_module as tia_module,
           c.hrpr_module as hrpr_module,
           personal_data_items,
           pdc_items,
           categories
    ORDER BY c.case_id
    LIMIT 1000
    """

    try:
        result = data_graph.query(query, params=params)

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
                    'has_pii': len(personal_data_items) > 0,
                    'has_health_data': has_health
                }
                cases.append(case_data)

        logger.info(f"Found {len(cases)} cases in DataTransferGraph")
        return cases

    except Exception as e:
        logger.error(f"Error querying DataTransferGraph: {e}", exc_info=True)
        return []


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


@app.get("/api/purposes", response_model=PurposesResponse, tags=["Metadata"])
async def get_purposes():
    """Get all available legal processing purposes from the graph"""
    try:
        query = "MATCH (p:Purpose) RETURN DISTINCT p.name as name ORDER BY name"
        result = data_graph.query(query)
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
        result_l1 = data_graph.query(query_l1)
        process_l1 = [row[0] for row in result_l1.result_set] if result_l1.result_set else []

        query_l2 = "MATCH (p:ProcessL2) RETURN DISTINCT p.name as name ORDER BY name"
        result_l2 = data_graph.query(query_l2)
        process_l2 = [row[0] for row in result_l2.result_set] if result_l2.result_set else []

        query_l3 = "MATCH (p:ProcessL3) RETURN DISTINCT p.name as name ORDER BY name"
        result_l3 = data_graph.query(query_l3)
        process_l3 = [row[0] for row in result_l3.result_set] if result_l3.result_set else []

        return {
            'success': True,
            'process_l1': process_l1,
            'process_l2': process_l2,
            'process_l3': process_l3
        }
    except Exception as e:
        logger.error(f"Error fetching processes: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/countries", response_model=CountriesResponse, tags=["Metadata"])
async def get_countries():
    """Get all unique countries from the data graph"""
    try:
        query_origin = "MATCH (c:Country) RETURN DISTINCT c.name as name ORDER BY name"
        result_origin = data_graph.query(query_origin)

        query_receiving = "MATCH (j:Jurisdiction) RETURN DISTINCT j.name as name ORDER BY name"
        result_receiving = data_graph.query(query_receiving)

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


@app.post("/api/evaluate-rules", response_model=RulesEvaluationResponse, tags=["Compliance"])
async def evaluate_rules(request: RulesEvaluationRequest):
    """
    Evaluate which compliance rules are triggered using deontic logic structure

    All parameters are optional for flexible, dynamic evaluation:
    - origin_country, receiving_country: Required for most evaluations
    - pii: Whether transfer contains PII
    - purpose_of_processing: Purpose(s) of data processing
    - process_l1, process_l2, process_l3: Process hierarchy levels
    - other_metadata: Additional data attributes (system auto-detects health data)

    Returns rules with their actions, permissions/prohibitions, and associated duties.
    Prohibitions indicate blocked transfers.

    Example:
        {
            "origin_country": "United States",
            "receiving_country": "China",
            "pii": true,
            "other_metadata": {
                "patient_records": "medical history",
                "diagnosis_codes": "ICD-10 codes"
            }
        }
        -> System automatically detects health data and triggers RULE_11
    """
    try:
        # Validate required fields
        if not request.origin_country or not request.receiving_country:
            raise HTTPException(
                status_code=400,
                detail="origin_country and receiving_country are required"
            )

        # Automatically detect health data from other_metadata
        has_health_data_detected = False
        health_detection_details = {}

        if request.other_metadata:
            health_detection_details = detect_health_data_from_metadata(request.other_metadata, verbose=True)
            has_health_data_detected = health_detection_details['detected']

            if has_health_data_detected:
                logger.info(f"🏥 Health data DETECTED from {len(request.other_metadata)} metadata fields:")
                for field in health_detection_details['matched_fields']:
                    logger.info(f"   • {field['key']}: {field['value']}")
            else:
                logger.info(f"✓ No health data detected in {len(request.other_metadata)} metadata fields")

        # Use pii flag from request, or None if not provided
        has_pii = request.pii

        logger.info(f"Evaluating rules: {request.origin_country} → {request.receiving_country}, "
                   f"PII={has_pii}, Health={has_health_data_detected}, "
                   f"Purpose={request.purpose_of_processing}, "
                   f"Process={request.process_l1}/{request.process_l2}/{request.process_l3}")

        result = query_triggered_rules_deontic(
            request.origin_country.strip(),
            request.receiving_country.strip(),
            has_pii,
            has_health_data_detected
        )

        return {
            'success': True,
            **result
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error evaluating rules: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/search-cases", response_model=SearchCasesResponse, tags=["Cases"])
async def search_cases(request: SearchCasesRequest):
    """
    Search for data transfer cases matching the specified criteria

    All parameters are optional for flexible searching:
    - origin_country: Partial match on originating country
    - receiving_country: Partial match on receiving country  - pii: Filter by PII presence
    - purpose_of_processing: Filter by processing purpose(s)
    - process_l1, process_l2, process_l3: Filter by process hierarchy
    - other_metadata: Additional metadata filters (future enhancement)

    Returns matching cases from the DataTransferGraph with auto-detected health data.
    """
    try:
        origin = request.origin_country.strip() if request.origin_country else None
        receiving = request.receiving_country.strip() if request.receiving_country else None
        process_l1 = request.process_l1.strip() if request.process_l1 else None
        process_l2 = request.process_l2.strip() if request.process_l2 else None
        process_l3 = request.process_l3.strip() if request.process_l3 else None

        # Convert pii boolean to legacy 'yes'/'no'/None format for search_data_graph
        has_pii_str = None
        if request.pii is True:
            has_pii_str = 'yes'
        elif request.pii is False:
            has_pii_str = 'no'

        logger.info(f"Searching cases: {origin} → {receiving}, "
                   f"purposes={request.purpose_of_processing}, "
                   f"processes={process_l1}/{process_l2}/{process_l3}, "
                   f"pii={has_pii_str}")

        cases = search_data_graph(
            origin,
            receiving,
            request.purpose_of_processing if request.purpose_of_processing else None,
            process_l1,
            process_l2,
            process_l3,
            has_pii_str
        )

        return {
            'success': True,
            'cases': cases,
            'total_cases': len(cases)
        }

    except Exception as e:
        logger.error(f"Error searching cases: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/stats", response_model=StatsResponse, tags=["Metadata"])
async def get_stats():
    """Get dashboard statistics"""
    try:
        query_cases = "MATCH (c:Case) RETURN count(c) as count"
        result_cases = data_graph.query(query_cases)
        total_cases = result_cases.result_set[0][0] if result_cases.result_set else 0

        query_countries = "MATCH (c:Country) RETURN count(c) as count"
        result_countries = data_graph.query(query_countries)
        total_countries = result_countries.result_set[0][0] if result_countries.result_set else 0

        query_jurisdictions = "MATCH (j:Jurisdiction) RETURN count(j) as count"
        result_jurisdictions = data_graph.query(query_jurisdictions)
        total_jurisdictions = result_jurisdictions.result_set[0][0] if result_jurisdictions.result_set else 0

        query_pii = """
        MATCH (c:Case)
        OPTIONAL MATCH (c)-[:HAS_PERSONAL_DATA]->(pd:PersonalData)
        WITH c, collect(pd.name) as pds
        WHERE size(pds) > 0
        RETURN count(c) as count
        """
        result_pii = data_graph.query(query_pii)
        cases_with_pii = result_pii.result_set[0][0] if result_pii.result_set else 0

        return {
            'success': True,
            'stats': {
                'total_cases': total_cases,
                'total_countries': total_countries,
                'total_jurisdictions': total_jurisdictions,
                'cases_with_pii': cases_with_pii
            }
        }

    except Exception as e:
        logger.error(f"Error fetching stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/test-rules-graph", tags=["Testing"])
async def test_rules_graph():
    """Test endpoint to verify RulesGraph is properly configured with deontic structure"""
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
        result = rules_graph.query(query)

        if result.result_set:
            groups, countries, rules, actions, permissions, prohibitions, duties = result.result_set[0]
            return {
                'success': True,
                'rules_graph_stats': {
                    'country_groups': groups,
                    'countries': countries,
                    'rules': rules,
                    'actions': actions,
                    'permissions': permissions,
                    'prohibitions': prohibitions,
                    'duties': duties
                },
                'message': 'Deontic RulesGraph is operational'
            }
        else:
            raise HTTPException(
                status_code=500,
                detail='RulesGraph is empty. Run build_rules_graph_deontic.py first.'
            )

    except Exception as e:
        logger.error(f"Error testing RulesGraph: {e}")
        raise HTTPException(
            status_code=500,
            detail=f'RulesGraph may not be built. Run build_rules_graph_deontic.py. Error: {str(e)}'
        )


if __name__ == '__main__':
    import uvicorn

    logger.info("=" * 70)
    logger.info("DEONTIC COMPLIANCE API - FastAPI")
    logger.info("=" * 70)
    logger.info("Using formal deontic logic: Actions, Permissions, Prohibitions, Duties")
    logger.info("Starting server on http://0.0.0.0:5001")
    logger.info("Swagger UI: http://localhost:5001/docs")
    logger.info("ReDoc: http://localhost:5001/redoc")
    logger.info("=" * 70)

    uvicorn.run(app, host="0.0.0.0", port=5001, log_level="info")
