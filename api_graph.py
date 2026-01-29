"""
Data Transfer Compliance Dashboard - Graph-Based Flask Backend
All rule logic is now in FalkorDB RulesGraph for scalability
"""

from flask import Flask, render_template, jsonify, request
from flask_cors import CORS
from falkordb import FalkorDB
from typing import Dict, List
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# FalkorDB connections
db = FalkorDB(host='localhost', port=6379)
rules_graph = db.select_graph('RulesGraph')
data_graph = db.select_graph('DataTransferGraph')

# Purpose of Processing options (kept for UI)
PURPOSE_OPTIONS = [
    'Prevention of Financial Crime',
    'Risk Management (excluding any Financial Crime related Risk Mgmt.)',
    'Back Office Operations Support',
    'Security / Prevention and Detecting Crime (excluding Financial Crime)',
    'Compliance with Laws and Regulations',
    'Disclosures to Authorities',
    'Identifying Target Subjects Need',
    'Marketing to Target Subjects',
    'Provision of Banking and Financial Services',
    'Product and Service Improvement',
    'Front Office Operations Support',
    'Personal Data as a Product',
    'Provision of a Communication Platform'
]


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
                    'origin_group': '',  # Could enhance to return this from graph
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
    NEW: Supports purposes (list) and process L1/L2/L3 filtering
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
                # NEW structure: case_id, eim_id, business_app_id, origin_country, receiving_countries,
                #                purposes, process_l1, process_l2, process_l3,
                #                pia_module, tia_module, hrpr_module,
                #                personal_data_items, pdc_items, categories

                # Safely extract data
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
                    'purposes': purposes,  # NEW: Array of purposes
                    'process_l1': process_l1,  # NEW
                    'process_l2': process_l2,  # NEW
                    'process_l3': process_l3,  # NEW
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
# API ROUTES
# ============================================================================

@app.route('/')
def index():
    """Serve the dashboard HTML"""
    return render_template('dashboard.html')


@app.route('/api/purpose-options', methods=['GET'])
def get_purpose_options():
    """Get available purpose options - DEPRECATED, use /api/purposes"""
    return jsonify({
        'success': True,
        'purposes': PURPOSE_OPTIONS
    })


@app.route('/api/purposes', methods=['GET'])
def get_purposes():
    """Get all purposes from the graph"""
    try:
        query = "MATCH (p:Purpose) RETURN DISTINCT p.name as name ORDER BY name"
        result = data_graph.query(query)

        purposes = [row[0] for row in result.result_set] if result.result_set else []

        return jsonify({
            'success': True,
            'purposes': purposes
        })
    except Exception as e:
        logger.error(f"Error fetching purposes: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/processes', methods=['GET'])
def get_processes():
    """Get all process levels from the graph"""
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

        return jsonify({
            'success': True,
            'process_l1': process_l1,
            'process_l2': process_l2,
            'process_l3': process_l3
        })
    except Exception as e:
        logger.error(f"Error fetching processes: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/countries', methods=['GET'])
def get_countries():
    """Get all unique countries from the data graph"""
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

        return jsonify({
            'success': True,
            'countries': all_countries,
            'origin_countries': origin_countries,
            'receiving_countries': receiving_countries
        })

    except Exception as e:
        logger.error(f"Error fetching countries: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/evaluate-rules', methods=['POST'])
def evaluate_rules():
    """
    Evaluate which compliance rules are triggered
    NOW QUERIES THE RULESGRAPH!
    """
    try:
        data = request.json

        origin = data.get('origin_country', '').strip()
        receiving = data.get('receiving_country', '').strip()
        has_pii = data.get('has_pii', False)

        logger.info(f"Evaluating rules via RulesGraph: {origin} → {receiving}")

        # Query the RulesGraph
        result = query_triggered_rules(origin, receiving, has_pii)

        return jsonify({
            'success': True,
            **result
        })

    except Exception as e:
        logger.error(f"Error evaluating rules: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/search-cases', methods=['POST'])
def search_cases():
    """
    Search for cases matching criteria
    NEW: Supports purposes (array) and process L1/L2/L3
    Returns ALL matching cases (no requirements filtering)
    """
    try:
        data = request.json

        origin = data.get('origin_country', '').strip()
        receiving = data.get('receiving_country', '').strip()
        purposes = data.get('purposes', [])  # NEW: Array of purpose names
        process_l1 = data.get('process_l1', '').strip() if data.get('process_l1') else None  # NEW
        process_l2 = data.get('process_l2', '').strip() if data.get('process_l2') else None  # NEW
        process_l3 = data.get('process_l3', '').strip() if data.get('process_l3') else None  # NEW
        has_pii_raw = data.get('has_pii')

        # Convert has_pii to string for query
        has_pii_str = None
        if has_pii_raw is True or has_pii_raw == 'yes':
            has_pii_str = 'yes'
        elif has_pii_raw is False or has_pii_raw == 'no':
            has_pii_str = 'no'

        logger.info(f"Searching cases: {origin} → {receiving}, purposes={purposes}, processes={process_l1}/{process_l2}/{process_l3}")

        # Search DataTransferGraph
        cases = search_data_graph(
            origin or None,
            receiving or None,
            purposes if purposes else None,
            process_l1,
            process_l2,
            process_l3,
            has_pii_str
        )

        return jsonify({
            'success': True,
            'cases': cases,
            'total_cases': len(cases)
        })

    except Exception as e:
        logger.error(f"Error searching cases: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/stats', methods=['GET'])
def get_stats():
    """Get dashboard statistics"""
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

        return jsonify({
            'success': True,
            'stats': {
                'total_cases': total_cases,
                'total_countries': total_countries,
                'total_jurisdictions': total_jurisdictions,
                'cases_with_pii': cases_with_pii
            }
        })

    except Exception as e:
        logger.error(f"Error fetching stats: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/test-rules-graph', methods=['GET'])
def test_rules_graph():
    """Test endpoint to verify RulesGraph is working"""
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
            return jsonify({
                'success': True,
                'rules_graph_stats': {
                    'country_groups': groups,
                    'countries': countries,
                    'rules': rules
                },
                'message': 'RulesGraph is operational'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'RulesGraph is empty. Run build_rules_graph.py first.'
            }), 500

    except Exception as e:
        logger.error(f"Error testing RulesGraph: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'message': 'RulesGraph may not be built. Run build_rules_graph.py'
        }), 500


if __name__ == '__main__':
    logger.info("="*70)
    logger.info("GRAPH-BASED COMPLIANCE API")
    logger.info("="*70)
    logger.info("Rule logic is now in FalkorDB RulesGraph for scalability")
    logger.info("Starting server on http://0.0.0.0:5001")
    logger.info("="*70)

    app.run(debug=True, host='0.0.0.0', port=5001)
