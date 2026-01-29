"""
Data Transfer Compliance Dashboard - Graph-Based FastAPI Backend
All rule logic is in FalkorDB RulesGraph for scalability
Includes automatic Swagger UI at /docs and ReDoc at /redoc
"""

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from typing import Dict, List, Optional
from falkordb import FalkorDB
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Data Transfer Compliance API",
    description="Graph-based compliance rule engine using FalkorDB. All business logic is stored in graphs for scalability.",
    version="2.0.0",
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

class RuleRequirement(BaseModel):
    """A single compliance requirement"""
    module: str
    value: str


class TriggeredRule(BaseModel):
    """A compliance rule that was triggered"""
    rule_id: str
    description: str
    priority: int
    requirements: Dict[str, str] = Field(default_factory=dict)
    origin_group: str = ""
    receiving_group: str = ""


class RulesEvaluationRequest(BaseModel):
    """Request to evaluate compliance rules"""
    origin_country: str = Field(..., description="Originating country name")
    receiving_country: str = Field(..., description="Receiving country name")
    has_pii: Optional[bool] = Field(None, description="Whether transfer contains PII")


class RulesEvaluationResponse(BaseModel):
    """Response from rules evaluation"""
    success: bool = True
    triggered_rules: List[TriggeredRule]
    requirements: Dict[str, str]
    total_rules_triggered: int


class SearchCasesRequest(BaseModel):
    """Request to search for cases"""
    origin_country: Optional[str] = Field(None, description="Originating country (partial match)")
    receiving_country: Optional[str] = Field(None, description="Receiving country (partial match)")
    purposes: Optional[List[str]] = Field(None, description="List of legal processing purposes")
    process_l1: Optional[str] = Field(None, description="Process area (L1)")
    process_l2: Optional[str] = Field(None, description="Process function (L2)")
    process_l3: Optional[str] = Field(None, description="Process detail (L3)")
    has_pii: Optional[str] = Field(None, description="'yes', 'no', or null")


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
# CORE LOGIC FUNCTIONS (unchanged from Flask version)
# ============================================================================

def query_triggered_rules(origin: str, receiving: str, has_pii: bool = None) -> Dict:
    """
    Query the RulesGraph to find triggered rules and their requirements
    All rule logic is now in the graph!
    """
    logger.info(f"Querying RulesGraph for: {origin} → {receiving}, has_pii={has_pii}")

    # Comprehensive rule matching query
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
         // Check if origin matches
         CASE
             WHEN r.origin_match_type = 'ALL' THEN true
             WHEN r.origin_match_type = 'ANY' AND size(rule_origin_groups) = 0 THEN false
             WHEN r.origin_match_type = 'ANY' THEN any(g IN origin_groups WHERE g IN rule_origin_groups)
             ELSE false
         END as origin_matches,
         // Check if receiving matches
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
          // Additional PII filter for RULE_8
          AND (NOT r.has_pii_required OR $has_pii = true)

    // Get requirements for each matched rule
    OPTIONAL MATCH (r)-[req:REQUIRES]->(:Requirement)

    RETURN r.rule_id as rule_id,
           r.description as description,
           r.priority as priority,
           collect({module: req.module, value: req.value}) as requirements
    ORDER BY r.priority
    """

    try:
        result = rules_graph.query(query, params={
            'origin_country': origin,
            'receiving_country': receiving,
            'has_pii': has_pii if has_pii is not None else False
        })

        triggered_rules = []
        consolidated_requirements = {}

        if result.result_set:
            for row in result.result_set:
                rule_id = row[0]
                description = row[1]
                priority = row[2]
                requirements = row[3]

                # Build requirements dict
                rule_requirements = {}
                if requirements and requirements[0].get('module'):
                    for req in requirements:
                        if req.get('module'):
                            rule_requirements[req['module']] = req['value']
                            consolidated_requirements[req['module']] = req['value']

                triggered_rules.append({
                    'rule_id': rule_id,
                    'description': description,
                    'priority': priority,
                    'requirements': rule_requirements,
                    'origin_group': '',
                    'receiving_group': ''
                })

        logger.info(f"Triggered {len(triggered_rules)} rules with requirements: {consolidated_requirements}")

        return {
            'triggered_rules': triggered_rules,
            'requirements': consolidated_requirements,
            'total_rules_triggered': len(triggered_rules)
        }

    except Exception as e:
        logger.error(f"Error querying RulesGraph: {e}", exc_info=True)
        return {
            'triggered_rules': [],
            'requirements': {},
            'total_rules_triggered': 0
        }


def search_data_graph(origin: str, receiving: str, purposes: List[str] = None,
                      process_l1: str = None, process_l2: str = None, process_l3: str = None,
                      has_pii: str = None) -> List[Dict]:
    """
    Query DataTransferGraph for matching cases
    Supports purposes (list) and process L1/L2/L3 filtering
    NO FILTERING BY REQUIREMENTS - shows all matching cases
    """
    logger.info(f"Searching DataTransferGraph: {origin} → {receiving}, purposes={purposes}, processes={process_l1}/{process_l2}/{process_l3}")

    conditions = []
    params = {}

    # Country matching - use CONTAINS for flexibility
    if origin:
        conditions.append("toLower(origin.name) CONTAINS toLower($origin)")
        params['origin'] = origin.lower()

    if receiving:
        conditions.append("toLower(receiving.name) CONTAINS toLower($receiving)")
        params['receiving'] = receiving.lower()

    where_clause = " AND ".join(conditions) if conditions else "true"

    # Build query with purpose and process filtering
    query = f"""
    MATCH (c:Case)-[:ORIGINATES_FROM]->(origin:Country)
    MATCH (c)-[:TRANSFERS_TO]->(receiving:Jurisdiction)
    WHERE {where_clause}
    """

    # Filter by purposes if provided
    if purposes and len(purposes) > 0:
        query += """
    WITH c, origin
    MATCH (c)-[:HAS_PURPOSE]->(purpose:Purpose)
    WHERE purpose.name IN $purposes
        """
        params['purposes'] = purposes

    # Filter by process L1 if provided
    if process_l1:
        query += """
    WITH c, origin
    MATCH (c)-[:HAS_PROCESS_L1]->(p1:ProcessL1 {name: $process_l1})
        """
        params['process_l1'] = process_l1

    # Filter by process L2 if provided
    if process_l2:
        query += """
    WITH c, origin
    MATCH (c)-[:HAS_PROCESS_L2]->(p2:ProcessL2 {name: $process_l2})
        """
        params['process_l2'] = process_l2

    # Filter by process L3 if provided
    if process_l3:
        query += """
    WITH c, origin
    MATCH (c)-[:HAS_PROCESS_L3]->(p3:ProcessL3 {name: $process_l3})
        """
        params['process_l3'] = process_l3

    # Collect receiving jurisdictions
    query += """
    WITH c, origin
    MATCH (c)-[:TRANSFERS_TO]->(receiving:Jurisdiction)
    WITH c, origin, collect(DISTINCT receiving.name) as receiving_countries

    // Get purposes
    OPTIONAL MATCH (c)-[:HAS_PURPOSE]->(purpose:Purpose)
    WITH c, origin, receiving_countries, collect(DISTINCT purpose.name) as purposes

    // Get processes
    OPTIONAL MATCH (c)-[:HAS_PROCESS_L1]->(p1:ProcessL1)
    OPTIONAL MATCH (c)-[:HAS_PROCESS_L2]->(p2:ProcessL2)
    OPTIONAL MATCH (c)-[:HAS_PROCESS_L3]->(p3:ProcessL3)
    WITH c, origin, receiving_countries, purposes, p1.name as process_l1, p2.name as process_l2, p3.name as process_l3

    // Get personal data
    OPTIONAL MATCH (c)-[:HAS_PERSONAL_DATA]->(pd:PersonalData)
    WITH c, origin, receiving_countries, purposes, process_l1, process_l2, process_l3, collect(DISTINCT pd.name) as personal_data_items

    // Get personal data categories
    OPTIONAL MATCH (c)-[:HAS_PERSONAL_DATA_CATEGORY]->(pdc:PersonalDataCategory)
    WITH c, origin, receiving_countries, purposes, process_l1, process_l2, process_l3, personal_data_items, collect(DISTINCT pdc.name) as pdc_items

    // Get categories
    OPTIONAL MATCH (c)-[:HAS_CATEGORY]->(cat:Category)
    WITH c, origin, receiving_countries, purposes, process_l1, process_l2, process_l3, personal_data_items, pdc_items, collect(DISTINCT cat.name) as categories
    """

    # Add PII filter if specified
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
                # Extract data safely
                purposes = row[5] if len(row) > 5 and row[5] else []
                process_l1 = row[6] if len(row) > 6 else None
                process_l2 = row[7] if len(row) > 7 else None
                process_l3 = row[8] if len(row) > 8 else None
                personal_data_items = row[12] if len(row) > 12 and row[12] else []
                pdc_items = row[13] if len(row) > 13 and row[13] else []
                categories = row[14] if len(row) > 14 and row[14] else []

                # Clean up None values
                purposes = [p for p in purposes if p] if purposes else []
                personal_data_items = [pd for pd in personal_data_items if pd] if personal_data_items else []
                pdc_items = [pdc for pdc in pdc_items if pdc] if pdc_items else []
                categories = [cat for cat in categories if cat] if categories else []

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
                    'has_pii': len(personal_data_items) > 0
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
    """
    Get all available legal processing purposes from the graph

    Returns a list of all unique purpose names that can be used for filtering cases.
    """
    try:
        query = "MATCH (p:Purpose) RETURN DISTINCT p.name as name ORDER BY name"
        result = data_graph.query(query)

        purposes = [row[0] for row in result.result_set] if result.result_set else []

        return {
            'success': True,
            'purposes': purposes
        }
    except Exception as e:
        logger.error(f"Error fetching purposes: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/processes", response_model=ProcessesResponse, tags=["Metadata"])
async def get_processes():
    """
    Get all available process levels (L1, L2, L3) from the graph

    - **L1**: Process area (e.g., Back Office, Front Office)
    - **L2**: Process function (e.g., HR, Finance)
    - **L3**: Process detail (e.g., Payroll, AP)
    """
    try:
        # Get Process L1
        query_l1 = "MATCH (p:ProcessL1) RETURN DISTINCT p.name as name ORDER BY name"
        result_l1 = data_graph.query(query_l1)
        process_l1 = [row[0] for row in result_l1.result_set] if result_l1.result_set else []

        # Get Process L2
        query_l2 = "MATCH (p:ProcessL2) RETURN DISTINCT p.name as name ORDER BY name"
        result_l2 = data_graph.query(query_l2)
        process_l2 = [row[0] for row in result_l2.result_set] if result_l2.result_set else []

        # Get Process L3
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
    """
    Get all unique countries from the data graph

    Returns both origin countries and receiving jurisdictions.
    """
    try:
        # Get origin countries
        query_origin = "MATCH (c:Country) RETURN DISTINCT c.name as name ORDER BY name"
        result_origin = data_graph.query(query_origin)

        # Get receiving jurisdictions
        query_receiving = "MATCH (j:Jurisdiction) RETURN DISTINCT j.name as name ORDER BY name"
        result_receiving = data_graph.query(query_receiving)

        origin_countries = [row[0] for row in result_origin.result_set] if result_origin.result_set else []
        receiving_countries = [row[0] for row in result_receiving.result_set] if result_receiving.result_set else []

        # Combine and deduplicate
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
    Evaluate which compliance rules are triggered for a data transfer

    This endpoint queries the RulesGraph to determine which compliance rules apply
    to a specific origin-to-receiving country transfer.

    - **origin_country**: The country from which data originates
    - **receiving_country**: The country receiving the data
    - **has_pii**: Whether the transfer contains personally identifiable information

    Returns all triggered rules with their compliance requirements.
    """
    try:
        logger.info(f"Evaluating rules via RulesGraph: {request.origin_country} → {request.receiving_country}")

        # Query the RulesGraph
        result = query_triggered_rules(
            request.origin_country.strip(),
            request.receiving_country.strip(),
            request.has_pii
        )

        return {
            'success': True,
            **result
        }

    except Exception as e:
        logger.error(f"Error evaluating rules: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/search-cases", response_model=SearchCasesResponse, tags=["Cases"])
async def search_cases(request: SearchCasesRequest):
    """
    Search for data transfer cases matching the specified criteria

    All filters are optional. If no filters are provided, returns all cases (up to 1000).

    - **origin_country**: Filter by origin country (partial match)
    - **receiving_country**: Filter by receiving country (partial match)
    - **purposes**: Filter by legal processing purposes (must match ANY)
    - **process_l1**: Filter by process area
    - **process_l2**: Filter by process function
    - **process_l3**: Filter by process detail
    - **has_pii**: Filter by PII presence ('yes', 'no', or null for any)

    Returns all matching cases WITHOUT filtering by compliance requirements.
    """
    try:
        origin = request.origin_country.strip() if request.origin_country else None
        receiving = request.receiving_country.strip() if request.receiving_country else None
        process_l1 = request.process_l1.strip() if request.process_l1 else None
        process_l2 = request.process_l2.strip() if request.process_l2 else None
        process_l3 = request.process_l3.strip() if request.process_l3 else None

        logger.info(f"Searching cases: {origin} → {receiving}, purposes={request.purposes}, processes={process_l1}/{process_l2}/{process_l3}")

        # Search DataTransferGraph
        cases = search_data_graph(
            origin,
            receiving,
            request.purposes if request.purposes else None,
            process_l1,
            process_l2,
            process_l3,
            request.has_pii
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
    """
    Get dashboard statistics

    Returns counts of total cases, countries, jurisdictions, and cases with PII.
    """
    try:
        # Total cases
        query_cases = "MATCH (c:Case) RETURN count(c) as count"
        result_cases = data_graph.query(query_cases)
        total_cases = result_cases.result_set[0][0] if result_cases.result_set else 0

        # Total countries
        query_countries = "MATCH (c:Country) RETURN count(c) as count"
        result_countries = data_graph.query(query_countries)
        total_countries = result_countries.result_set[0][0] if result_countries.result_set else 0

        # Total jurisdictions
        query_jurisdictions = "MATCH (j:Jurisdiction) RETURN count(j) as count"
        result_jurisdictions = data_graph.query(query_jurisdictions)
        total_jurisdictions = result_jurisdictions.result_set[0][0] if result_jurisdictions.result_set else 0

        # Cases with PII
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
    """
    Test endpoint to verify RulesGraph is properly configured

    Returns statistics about the RulesGraph (country groups, countries, rules).
    """
    try:
        # Query rules graph statistics
        query = """
        MATCH (cg:CountryGroup) WITH count(cg) as groups
        MATCH (c:Country) WITH groups, count(c) as countries
        MATCH (r:Rule) WITH groups, countries, count(r) as rules
        RETURN groups, countries, rules
        """
        result = rules_graph.query(query)

        if result.result_set:
            groups, countries, rules = result.result_set[0]
            return {
                'success': True,
                'rules_graph_stats': {
                    'country_groups': groups,
                    'countries': countries,
                    'rules': rules
                },
                'message': 'RulesGraph is operational'
            }
        else:
            raise HTTPException(
                status_code=500,
                detail='RulesGraph is empty. Run build_rules_graph.py first.'
            )

    except Exception as e:
        logger.error(f"Error testing RulesGraph: {e}")
        raise HTTPException(
            status_code=500,
            detail=f'RulesGraph may not be built. Run build_rules_graph.py. Error: {str(e)}'
        )


if __name__ == '__main__':
    import uvicorn

    logger.info("=" * 70)
    logger.info("GRAPH-BASED COMPLIANCE API - FastAPI")
    logger.info("=" * 70)
    logger.info("Rule logic is in FalkorDB RulesGraph for scalability")
    logger.info("Starting server on http://0.0.0.0:5001")
    logger.info("Swagger UI: http://localhost:5001/docs")
    logger.info("ReDoc: http://localhost:5001/redoc")
    logger.info("=" * 70)

    uvicorn.run(app, host="0.0.0.0", port=5001, log_level="info")
