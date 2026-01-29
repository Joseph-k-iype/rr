"""
Data Transfer Compliance Dashboard - Flask Backend
High-performance API with FalkorDB integration
"""

from flask import Flask, render_template, jsonify, request
from flask_cors import CORS
from falkordb import FalkorDB
import redis
from typing import List, Dict, Set, Optional
import re
from functools import lru_cache
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# FalkorDB connection
db = FalkorDB(host='localhost', port=6379)
graph = db.select_graph('DataTransferGraph')

# Country groupings for compliance rules
COUNTRY_GROUPS = {
    'EU_EEA_FULL': {
        'Belgium', 'Bulgaria', 'Czechia', 'Denmark', 'Germany', 'Estonia', 
        'Ireland', 'Greece', 'Spain', 'France', 'Croatia', 'Italy', 'Cyprus', 
        'Latvia', 'Lithuania', 'Luxembourg', 'Hungary', 'Malta', 'Netherlands', 
        'Austria', 'Poland', 'Portugal', 'Romania', 'Slovenia', 'Slovakia', 
        'Finland', 'Sweden'
    },
    'UK_CROWN_DEPENDENCIES': {
        'United Kingdom', 'Jersey', 'Guernsey', 'Isle of Man'
    },
    'SWITZERLAND': {'Switzerland'},
    'ADEQUACY_COUNTRIES': {
        'Andorra', 'Argentina', 'Canada', 'Faroe Islands', 'Guernsey', 'Israel', 
        'Isle of Man', 'Japan', 'Jersey', 'New Zealand', 'Republic of Korea', 
        'Switzerland', 'United Kingdom', 'Uruguay'
    },
    'SWITZERLAND_APPROVED': {
        'Andorra', 'Argentina', 'Canada', 'Faroe Islands', 'Guernsey', 'Israel', 
        'Isle of Man', 'Jersey', 'New Zealand', 'Switzerland', 'Uruguay', 
        'Belgium', 'Bulgaria', 'Czechia', 'Denmark', 'Germany', 'Estonia', 
        'Ireland', 'Greece', 'Spain', 'France', 'Croatia', 'Italy', 'Cyprus', 
        'Latvia', 'Lithuania', 'Luxembourg', 'Hungary', 'Malta', 'Netherlands', 
        'Austria', 'Poland', 'Portugal', 'Romania', 'Slovenia', 'Slovakia', 
        'Finland', 'Sweden', 'Gibraltar', 'Monaco'
    },
    'BCR_COUNTRIES': {
        'Algeria', 'Australia', 'Bahrain', 'Bangladesh', 'Belgium', 'Bermuda', 
        'Brazil', 'Canada', 'Cayman Islands', 'Chile', 'China', 'Czech Republic', 
        'British Virgin Islands', 'Denmark', 'Egypt', 'France', 'Germany', 
        'Guernsey', 'Hong Kong', 'India', 'Indonesia', 'Ireland', 'Isle of Man', 
        'Italy', 'Japan', 'Jersey', 'Korea', 'Republic Of (South)', 'Kuwait', 
        'Luxembourg', 'Macao', 'Malaysia', 'Maldives', 'Malta', 'Mauritius', 
        'Mexico', 'Netherlands', 'New Zealand', 'Oman', 'Philippines', 'Poland', 
        'Qatar', 'Saudi Arabia', 'Singapore', 'South Africa', 'Spain', 'Sri Lanka', 
        'Sweden', 'Switzerland', 'Taiwan', 'Thailand', 'Turkey', 'Turkiye',
        'United Arab Emirates', 'United Kingdom', 'United States of America', 
        'Uruguay', 'Vietnam'
    }
}

# Purpose of Processing options
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


def normalize_country(country: str) -> str:
    """Normalize country name for matching"""
    if not country:
        return ""
    
    # Case insensitive
    normalized = country.strip().lower()
    
    # Handle common variations
    variations = {
        'korea': 'republic of korea',
        'south korea': 'republic of korea',
        'republic of (south)': 'republic of korea',
        'uk': 'united kingdom',
        'usa': 'united states of america',
        'us': 'united states of america',
        'czech republic': 'czechia',
        'luxemborg': 'luxembourg',
        'soth africa': 'south africa',
        'uruguar': 'uruguay',
    }
    
    for variant, standard in variations.items():
        if variant in normalized:
            return standard
    
    return normalized


def country_matches(country: str, reference_set: Set[str]) -> bool:
    """Check if country matches any in reference set (case-insensitive, contains)"""
    if not country:
        return False
    
    normalized_country = normalize_country(country)
    
    for ref_country in reference_set:
        normalized_ref = normalize_country(ref_country)
        if normalized_ref in normalized_country or normalized_country in normalized_ref:
            return True
    
    return False


def evaluate_compliance_rules(origin: str, receiving: str, has_pii: bool) -> Dict:
    """
    Evaluate all compliance rules and return triggered rules with requirements
    """
    triggered_rules = []
    
    # Normalize inputs
    origin_norm = normalize_country(origin)
    receiving_norm = normalize_country(receiving)
    
    # Rule 1: EU/EEA ↔ EU/EEA + UK/Crown + CH
    eu_eea_extended = COUNTRY_GROUPS['EU_EEA_FULL'] | COUNTRY_GROUPS['UK_CROWN_DEPENDENCIES'] | COUNTRY_GROUPS['SWITZERLAND']
    if country_matches(origin, eu_eea_extended) and country_matches(receiving, eu_eea_extended):
        triggered_rules.append({
            'rule_id': 'RULE_1',
            'description': 'EU/EEA/UK/Crown Dependencies/Switzerland internal transfer',
            'requirements': {'pia_module': 'CM'},
            'origin_group': 'EU/EEA/UK/Crown/CH',
            'receiving_group': 'EU/EEA/UK/Crown/CH'
        })
    
    # Rule 2: EU/EEA → Adequacy Countries
    if country_matches(origin, COUNTRY_GROUPS['EU_EEA_FULL']) and country_matches(receiving, COUNTRY_GROUPS['ADEQUACY_COUNTRIES']):
        triggered_rules.append({
            'rule_id': 'RULE_2',
            'description': 'EU/EEA to Adequacy Decision countries',
            'requirements': {'pia_module': 'CM'},
            'origin_group': 'EU/EEA',
            'receiving_group': 'Adequacy Countries'
        })
    
    # Rule 3: Crown Dependencies → Adequacy + EU/EEA
    crown_deps_only = {'Jersey', 'Isle of Man', 'Guernsey'}
    adequacy_plus_eu = COUNTRY_GROUPS['ADEQUACY_COUNTRIES'] | COUNTRY_GROUPS['EU_EEA_FULL']
    if country_matches(origin, crown_deps_only) and country_matches(receiving, adequacy_plus_eu):
        triggered_rules.append({
            'rule_id': 'RULE_3',
            'description': 'Crown Dependencies to Adequacy + EU/EEA',
            'requirements': {'pia_module': 'CM'},
            'origin_group': 'Crown Dependencies',
            'receiving_group': 'Adequacy + EU/EEA'
        })
    
    # Rule 4: UK → Adequacy (minus UK) + EU/EEA
    uk_targets = (COUNTRY_GROUPS['ADEQUACY_COUNTRIES'] | COUNTRY_GROUPS['EU_EEA_FULL']) - {'United Kingdom'}
    if country_matches(origin, {'United Kingdom'}) and country_matches(receiving, uk_targets):
        triggered_rules.append({
            'rule_id': 'RULE_4',
            'description': 'United Kingdom to Adequacy (excluding UK) + EU/EEA',
            'requirements': {'pia_module': 'CM'},
            'origin_group': 'United Kingdom',
            'receiving_group': 'Adequacy + EU/EEA'
        })
    
    # Rule 5: Switzerland → Approved countries
    if country_matches(origin, COUNTRY_GROUPS['SWITZERLAND']) and country_matches(receiving, COUNTRY_GROUPS['SWITZERLAND_APPROVED']):
        triggered_rules.append({
            'rule_id': 'RULE_5',
            'description': 'Switzerland to approved jurisdictions',
            'requirements': {'pia_module': 'CM'},
            'origin_group': 'Switzerland',
            'receiving_group': 'Switzerland Approved'
        })
    
    # Rule 6: Broad origin list → Rest of World
    broad_origin = COUNTRY_GROUPS['ADEQUACY_COUNTRIES'] | COUNTRY_GROUPS['EU_EEA_FULL'] | {'United Kingdom'}
    if country_matches(origin, broad_origin) and not country_matches(receiving, broad_origin):
        triggered_rules.append({
            'rule_id': 'RULE_6',
            'description': 'EU/EEA/Adequacy to Rest of World',
            'requirements': {'pia_module': 'CM', 'tia_module': 'CM'},
            'origin_group': 'EU/EEA/Adequacy/UK',
            'receiving_group': 'Rest of World'
        })
    
    # Rule 7: BCR Countries → Any
    if country_matches(origin, COUNTRY_GROUPS['BCR_COUNTRIES']):
        triggered_rules.append({
            'rule_id': 'RULE_7',
            'description': 'BCR Countries to any jurisdiction',
            'requirements': {'pia_module': 'CM', 'hrpr_module': 'CM'},
            'origin_group': 'BCR Countries',
            'receiving_group': 'Any'
        })
    
    # Rule 8: Contains PII → PIA required
    if has_pii:
        triggered_rules.append({
            'rule_id': 'RULE_8',
            'description': 'Transfer contains Personal Data (PII)',
            'requirements': {'pia_module': 'CM'},
            'origin_group': 'Any',
            'receiving_group': 'Any'
        })
    
    # Consolidate requirements
    consolidated_requirements = {}
    for rule in triggered_rules:
        for req_type, req_value in rule['requirements'].items():
            if req_type not in consolidated_requirements:
                consolidated_requirements[req_type] = req_value
    
    return {
        'triggered_rules': triggered_rules,
        'requirements': consolidated_requirements,
        'total_rules_triggered': len(triggered_rules)
    }


@lru_cache(maxsize=1000)
def build_cypher_query(origin: Optional[str], receiving: Optional[str], 
                       purpose_l1: Optional[str], purpose_l2: Optional[str], 
                       purpose_l3: Optional[str], has_pii: Optional[str],
                       requirements_tuple: tuple) -> tuple:
    """Build optimized Cypher query with caching"""
    
    # Convert requirements tuple back to dict
    requirements = dict(requirements_tuple) if requirements_tuple else {}
    
    conditions = []
    params_desc = {}
    
    # Country matching - use CONTAINS for flexibility
    if origin:
        conditions.append("toLower(origin.name) CONTAINS toLower($origin)")
        params_desc['origin'] = origin.lower()
    
    if receiving:
        conditions.append("toLower(receiving.name) CONTAINS toLower($receiving)")
        params_desc['receiving'] = receiving.lower()
    
    # Purpose matching - hierarchical with exact match on non-null values
    if purpose_l1:
        conditions.append("toLower(coalesce(c.purpose_level1, '')) CONTAINS toLower($purpose_l1)")
        params_desc['purpose_l1'] = purpose_l1.lower()

    if purpose_l2:
        conditions.append("toLower(coalesce(c.purpose_level2, '')) CONTAINS toLower($purpose_l2)")
        params_desc['purpose_l2'] = purpose_l2.lower()

    if purpose_l3:
        conditions.append("toLower(coalesce(c.purpose_level3, '')) CONTAINS toLower($purpose_l3)")
        params_desc['purpose_l3'] = purpose_l3.lower()

    # Module requirements - REMOVED FROM FILTERING
    # Requirements are used for compliance checking in the UI, not for filtering results
    # The dashboard should show ALL matching cases and mark them as compliant/non-compliant
    # OLD CODE (caused 0 results issue):
    # for module, value in requirements.items():
    #     conditions.append(f"c.{module} = ${module}")
    #     params_desc[module] = value

    where_clause = " AND ".join(conditions) if conditions else "true"
    
    # Build query - collect all data first, then filter by PII if needed
    query = f"""
    MATCH (c:Case)-[:ORIGINATES_FROM]->(origin:Country)
    MATCH (c)-[:TRANSFERS_TO]->(receiving:Jurisdiction)
    WHERE {where_clause}
    WITH c, origin, collect(DISTINCT receiving.name) as receiving_countries
    OPTIONAL MATCH (c)-[:HAS_PERSONAL_DATA]->(pd:PersonalData)
    WITH c, origin, receiving_countries, collect(DISTINCT pd.name) as personal_data_items
    OPTIONAL MATCH (c)-[:HAS_PERSONAL_DATA_CATEGORY]->(pdc:PersonalDataCategory)
    WITH c, origin, receiving_countries, personal_data_items, collect(DISTINCT pdc.name) as pdc_items
    OPTIONAL MATCH (c)-[:HAS_CATEGORY]->(cat:Category)
    WITH c, origin, receiving_countries, personal_data_items, pdc_items, collect(DISTINCT cat.name) as categories
    """
    
    # Add PII filter after collecting data
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
           c.purpose_level1 as purpose_l1,
           c.purpose_level2 as purpose_l2,
           c.purpose_level3 as purpose_l3,
           c.pia_module as pia_module,
           c.tia_module as tia_module,
           c.hrpr_module as hrpr_module,
           personal_data_items,
           pdc_items,
           categories
    ORDER BY c.case_id
    LIMIT 1000
    """
    
    return query, params_desc


@app.route('/')
def index():
    """Serve the dashboard HTML"""
    return render_template('dashboard.html')


@app.route('/api/purpose-options', methods=['GET'])
def get_purpose_options():
    """Get available purpose options"""
    return jsonify({
        'success': True,
        'purposes': PURPOSE_OPTIONS
    })


@app.route('/api/countries', methods=['GET'])
def get_countries():
    """Get all unique countries from the graph"""
    try:
        # Get origin countries
        query_origin = "MATCH (c:Country) RETURN DISTINCT c.name as name ORDER BY name"
        result_origin = graph.query(query_origin)
        
        # Get receiving jurisdictions
        query_receiving = "MATCH (j:Jurisdiction) RETURN DISTINCT j.name as name ORDER BY name"
        result_receiving = graph.query(query_receiving)
        
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
    """Evaluate which compliance rules are triggered"""
    try:
        data = request.json
        
        origin = data.get('origin_country', '').strip()
        receiving = data.get('receiving_country', '').strip()
        has_pii = data.get('has_pii', False)
        
        # Evaluate rules
        result = evaluate_compliance_rules(origin, receiving, has_pii)
        
        return jsonify({
            'success': True,
            **result
        })
    
    except Exception as e:
        logger.error(f"Error evaluating rules: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/search-cases', methods=['POST'])
def search_cases():
    """Search for cases matching criteria"""
    try:
        data = request.json
        
        origin = data.get('origin_country', '').strip()
        receiving = data.get('receiving_country', '').strip()
        purpose_l1 = data.get('purpose_level1', '').strip()
        purpose_l2 = data.get('purpose_level2', '').strip()
        purpose_l3 = data.get('purpose_level3', '').strip()
        has_pii = data.get('has_pii')  # Will be 'yes', 'no', or None
        requirements = data.get('requirements', {})
        
        # Convert has_pii to string for query building
        has_pii_str = None
        if has_pii is True or has_pii == 'yes':
            has_pii_str = 'yes'
        elif has_pii is False or has_pii == 'no':
            has_pii_str = 'no'
        
        # Build query
        requirements_tuple = tuple(sorted(requirements.items())) if requirements else ()
        query, params = build_cypher_query(
            origin or None,
            receiving or None,
            purpose_l1 or None,
            purpose_l2 or None,
            purpose_l3 or None,
            has_pii_str,
            requirements_tuple
        )
        
        logger.info(f"Executing search query")
        logger.info(f"Parameters: {params}")
        logger.info(f"Has PII filter: {has_pii_str}")
        logger.debug(f"Query: {query}")
        
        # Execute query
        result = graph.query(query, params=params)
        
        # Parse results
        cases = []
        if result.result_set:
            for row in result.result_set:
                # Safely extract data with proper indexing
                personal_data_items = row[11] if len(row) > 11 and row[11] else []
                pdc_items = row[12] if len(row) > 12 and row[12] else []
                categories = row[13] if len(row) > 13 and row[13] else []
                
                # Clean up None values in lists
                personal_data_items = [pd for pd in personal_data_items if pd] if personal_data_items else []
                pdc_items = [pdc for pdc in pdc_items if pdc] if pdc_items else []
                categories = [cat for cat in categories if cat] if categories else []
                
                case_data = {
                    'case_id': row[0],
                    'eim_id': row[1],
                    'business_app_id': row[2],
                    'origin_country': row[3],
                    'receiving_countries': row[4] if isinstance(row[4], list) else [row[4]] if row[4] else [],
                    'purpose_level1': row[5],
                    'purpose_level2': row[6],
                    'purpose_level3': row[7],
                    'pia_module': row[8],
                    'tia_module': row[9],
                    'hrpr_module': row[10],
                    'personal_data': personal_data_items,
                    'personal_data_categories': pdc_items,
                    'categories': categories,
                    'has_pii': len(personal_data_items) > 0
                }
                cases.append(case_data)
        
        logger.info(f"Found {len(cases)} cases matching criteria")
        
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
        result_cases = graph.query(query_cases)
        total_cases = result_cases.result_set[0][0] if result_cases.result_set else 0
        
        # Total countries
        query_countries = "MATCH (c:Country) RETURN count(c) as count"
        result_countries = graph.query(query_countries)
        total_countries = result_countries.result_set[0][0] if result_countries.result_set else 0
        
        # Total jurisdictions
        query_jurisdictions = "MATCH (j:Jurisdiction) RETURN count(j) as count"
        result_jurisdictions = graph.query(query_jurisdictions)
        total_jurisdictions = result_jurisdictions.result_set[0][0] if result_jurisdictions.result_set else 0
        
        # Cases with PII
        query_pii = """
        MATCH (c:Case)
        OPTIONAL MATCH (c)-[:HAS_PERSONAL_DATA]->(pd:PersonalData)
        WITH c, collect(pd.name) as pds
        WHERE size(pds) > 0
        RETURN count(c) as count
        """
        result_pii = graph.query(query_pii)
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


@app.route('/api/test-case', methods=['GET'])
def test_case():
    """Test endpoint to verify case data structure"""
    try:
        query = """
        MATCH (c:Case)-[:ORIGINATES_FROM]->(origin:Country)
        MATCH (c)-[:TRANSFERS_TO]->(receiving:Jurisdiction)
        WITH c, origin, collect(DISTINCT receiving.name) as receiving_countries
        OPTIONAL MATCH (c)-[:HAS_PERSONAL_DATA]->(pd:PersonalData)
        WITH c, origin, receiving_countries, collect(DISTINCT pd.name) as personal_data_items
        OPTIONAL MATCH (c)-[:HAS_PERSONAL_DATA_CATEGORY]->(pdc:PersonalDataCategory)
        WITH c, origin, receiving_countries, personal_data_items, collect(DISTINCT pdc.name) as pdc_items
        OPTIONAL MATCH (c)-[:HAS_CATEGORY]->(cat:Category)
        WITH c, origin, receiving_countries, personal_data_items, pdc_items, collect(DISTINCT cat.name) as categories
        RETURN c.case_id as case_id,
               c.eim_id as eim_id,
               c.business_app_id as business_app_id,
               origin.name as origin_country,
               receiving_countries,
               c.purpose_level1 as purpose_l1,
               c.purpose_level2 as purpose_l2,
               c.purpose_level3 as purpose_l3,
               c.pia_module as pia_module,
               c.tia_module as tia_module,
               c.hrpr_module as hrpr_module,
               personal_data_items,
               pdc_items,
               categories
        LIMIT 5
        """
        
        result = graph.query(query)
        
        cases = []
        if result.result_set:
            for row in result.result_set:
                personal_data_items = row[11] if len(row) > 11 and row[11] else []
                pdc_items = row[12] if len(row) > 12 and row[12] else []
                categories = row[13] if len(row) > 13 and row[13] else []
                
                # Clean up None values
                personal_data_items = [pd for pd in personal_data_items if pd] if personal_data_items else []
                pdc_items = [pdc for pdc in pdc_items if pdc] if pdc_items else []
                categories = [cat for cat in categories if cat] if categories else []
                
                case_data = {
                    'case_id': row[0],
                    'eim_id': row[1],
                    'business_app_id': row[2],
                    'origin_country': row[3],
                    'receiving_countries': row[4] if isinstance(row[4], list) else [row[4]] if row[4] else [],
                    'purpose_level1': row[5],
                    'purpose_level2': row[6],
                    'purpose_level3': row[7],
                    'pia_module': row[8],
                    'tia_module': row[9],
                    'hrpr_module': row[10],
                    'personal_data': personal_data_items,
                    'personal_data_categories': pdc_items,
                    'categories': categories,
                    'has_pii': len(personal_data_items) > 0
                }
                cases.append(case_data)
        
        return jsonify({
            'success': True,
            'sample_cases': cases,
            'count': len(cases)
        })
        
    except Exception as e:
        logger.error(f"Test case error: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)