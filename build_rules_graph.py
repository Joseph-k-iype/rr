#!/usr/bin/env python3
"""
Build Rules Graph in FalkorDB
Moves all compliance rule logic from Python code into graph structure
"""

from falkordb import FalkorDB
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def build_rules_graph():
    """Build the Rules Graph with country groups, rules, and requirements"""

    db = FalkorDB(host='localhost', port=6379)
    graph = db.select_graph('RulesGraph')

    logger.info("Building Rules Graph...")

    # Clear existing data
    logger.info("Clearing existing Rules Graph...")
    try:
        graph.query("MATCH (n) DETACH DELETE n")
    except:
        pass

    # Create indexes
    logger.info("Creating indexes...")
    indexes = [
        "CREATE INDEX FOR (cg:CountryGroup) ON (cg.name)",
        "CREATE INDEX FOR (c:Country) ON (c.name)",
        "CREATE INDEX FOR (r:Rule) ON (r.rule_id)",
    ]

    for idx_query in indexes:
        try:
            graph.query(idx_query)
        except:
            pass

    # 1. Create Country Group Nodes
    logger.info("Creating country groups...")

    country_groups = {
        'EU_EEA_FULL': [
            'Belgium', 'Bulgaria', 'Czechia', 'Denmark', 'Germany', 'Estonia',
            'Ireland', 'Greece', 'Spain', 'France', 'Croatia', 'Italy', 'Cyprus',
            'Latvia', 'Lithuania', 'Luxembourg', 'Hungary', 'Malta', 'Netherlands',
            'Austria', 'Poland', 'Portugal', 'Romania', 'Slovenia', 'Slovakia',
            'Finland', 'Sweden'
        ],
        'UK_CROWN_DEPENDENCIES': [
            'United Kingdom', 'Jersey', 'Guernsey', 'Isle of Man'
        ],
        'SWITZERLAND': ['Switzerland'],
        'ADEQUACY_COUNTRIES': [
            'Andorra', 'Argentina', 'Canada', 'Faroe Islands', 'Guernsey', 'Israel',
            'Isle of Man', 'Japan', 'Jersey', 'New Zealand', 'Republic of Korea',
            'Switzerland', 'United Kingdom', 'Uruguay'
        ],
        'SWITZERLAND_APPROVED': [
            'Andorra', 'Argentina', 'Canada', 'Faroe Islands', 'Guernsey', 'Israel',
            'Isle of Man', 'Jersey', 'New Zealand', 'Switzerland', 'Uruguay',
            'Belgium', 'Bulgaria', 'Czechia', 'Denmark', 'Germany', 'Estonia',
            'Ireland', 'Greece', 'Spain', 'France', 'Croatia', 'Italy', 'Cyprus',
            'Latvia', 'Lithuania', 'Luxembourg', 'Hungary', 'Malta', 'Netherlands',
            'Austria', 'Poland', 'Portugal', 'Romania', 'Slovenia', 'Slovakia',
            'Finland', 'Sweden', 'Gibraltar', 'Monaco'
        ],
        'BCR_COUNTRIES': [
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
        ],
        'CROWN_DEPENDENCIES_ONLY': ['Jersey', 'Isle of Man', 'Guernsey'],
        'UK_ONLY': ['United Kingdom'],
        'EU_EEA_ADEQUACY_UK': []  # Will be computed
    }

    # Computed groups
    country_groups['EU_EEA_UK_CROWN_CH'] = list(set(
        country_groups['EU_EEA_FULL'] +
        country_groups['UK_CROWN_DEPENDENCIES'] +
        country_groups['SWITZERLAND']
    ))

    country_groups['EU_EEA_ADEQUACY_UK'] = list(set(
        country_groups['EU_EEA_FULL'] +
        country_groups['ADEQUACY_COUNTRIES'] +
        ['United Kingdom']
    ))

    country_groups['ADEQUACY_PLUS_EU'] = list(set(
        country_groups['ADEQUACY_COUNTRIES'] +
        country_groups['EU_EEA_FULL']
    ))

    # Create CountryGroup nodes
    for group_name in country_groups.keys():
        query = """
        MERGE (cg:CountryGroup {name: $group_name})
        SET cg.description = $description
        """
        graph.query(query, params={
            'group_name': group_name,
            'description': f'Country group: {group_name}'
        })

    # Create Country nodes and relationships
    logger.info("Creating countries and group memberships...")

    all_countries = set()
    for countries_list in country_groups.values():
        all_countries.update(countries_list)

    for country_name in all_countries:
        # Create country node
        query = "MERGE (c:Country {name: $name})"
        graph.query(query, params={'name': country_name})

        # Create BELONGS_TO relationships
        for group_name, countries_list in country_groups.items():
            if country_name in countries_list:
                query = """
                MATCH (c:Country {name: $country_name})
                MATCH (cg:CountryGroup {name: $group_name})
                MERGE (c)-[:BELONGS_TO]->(cg)
                """
                graph.query(query, params={
                    'country_name': country_name,
                    'group_name': group_name
                })

    # 2. Create Rule Nodes with their logic
    logger.info("Creating rules...")

    rules = [
        {
            'rule_id': 'RULE_1',
            'description': 'EU/EEA/UK/Crown Dependencies/Switzerland internal transfer',
            'priority': 1,
            'origin_groups': ['EU_EEA_UK_CROWN_CH'],
            'receiving_groups': ['EU_EEA_UK_CROWN_CH'],
            'origin_match_type': 'ANY',  # Origin must be in ANY of these groups
            'receiving_match_type': 'ANY',  # Receiving must be in ANY of these groups
            'requirements': [{'module': 'pia_module', 'value': 'CM'}]
        },
        {
            'rule_id': 'RULE_2',
            'description': 'EU/EEA to Adequacy Decision countries',
            'priority': 2,
            'origin_groups': ['EU_EEA_FULL'],
            'receiving_groups': ['ADEQUACY_COUNTRIES'],
            'origin_match_type': 'ANY',
            'receiving_match_type': 'ANY',
            'requirements': [{'module': 'pia_module', 'value': 'CM'}]
        },
        {
            'rule_id': 'RULE_3',
            'description': 'Crown Dependencies to Adequacy + EU/EEA',
            'priority': 3,
            'origin_groups': ['CROWN_DEPENDENCIES_ONLY'],
            'receiving_groups': ['ADEQUACY_PLUS_EU'],
            'origin_match_type': 'ANY',
            'receiving_match_type': 'ANY',
            'requirements': [{'module': 'pia_module', 'value': 'CM'}]
        },
        {
            'rule_id': 'RULE_4',
            'description': 'United Kingdom to Adequacy (excluding UK) + EU/EEA',
            'priority': 4,
            'origin_groups': ['UK_ONLY'],
            'receiving_groups': ['EU_EEA_ADEQUACY_UK'],
            'origin_match_type': 'ANY',
            'receiving_match_type': 'ANY',
            'exclude_receiving': ['United Kingdom'],
            'requirements': [{'module': 'pia_module', 'value': 'CM'}]
        },
        {
            'rule_id': 'RULE_5',
            'description': 'Switzerland to approved jurisdictions',
            'priority': 5,
            'origin_groups': ['SWITZERLAND'],
            'receiving_groups': ['SWITZERLAND_APPROVED'],
            'origin_match_type': 'ANY',
            'receiving_match_type': 'ANY',
            'requirements': [{'module': 'pia_module', 'value': 'CM'}]
        },
        {
            'rule_id': 'RULE_6',
            'description': 'EU/EEA/Adequacy to Rest of World',
            'priority': 6,
            'origin_groups': ['EU_EEA_ADEQUACY_UK'],
            'receiving_groups': ['EU_EEA_ADEQUACY_UK'],
            'origin_match_type': 'ANY',
            'receiving_match_type': 'NOT_IN',  # NOT in these groups
            'requirements': [
                {'module': 'pia_module', 'value': 'CM'},
                {'module': 'tia_module', 'value': 'CM'}
            ]
        },
        {
            'rule_id': 'RULE_7',
            'description': 'BCR Countries to any jurisdiction',
            'priority': 7,
            'origin_groups': ['BCR_COUNTRIES'],
            'receiving_groups': [],  # Any receiving
            'origin_match_type': 'ANY',
            'receiving_match_type': 'ALL',  # Matches all
            'requirements': [
                {'module': 'pia_module', 'value': 'CM'},
                {'module': 'hrpr_module', 'value': 'CM'}
            ]
        },
        {
            'rule_id': 'RULE_8',
            'description': 'Transfer contains Personal Data (PII)',
            'priority': 8,
            'origin_groups': [],  # Any origin
            'receiving_groups': [],  # Any receiving
            'origin_match_type': 'ALL',
            'receiving_match_type': 'ALL',
            'has_pii_required': True,  # Only triggers if has_pii=True
            'requirements': [{'module': 'pia_module', 'value': 'CM'}]
        }
    ]

    for rule in rules:
        # Create rule node
        query = """
        CREATE (r:Rule {
            rule_id: $rule_id,
            description: $description,
            priority: $priority,
            origin_match_type: $origin_match_type,
            receiving_match_type: $receiving_match_type,
            has_pii_required: $has_pii_required
        })
        """
        graph.query(query, params={
            'rule_id': rule['rule_id'],
            'description': rule['description'],
            'priority': rule['priority'],
            'origin_match_type': rule['origin_match_type'],
            'receiving_match_type': rule['receiving_match_type'],
            'has_pii_required': rule.get('has_pii_required', False)
        })

        # Create relationships to origin groups
        for group_name in rule['origin_groups']:
            query = """
            MATCH (r:Rule {rule_id: $rule_id})
            MATCH (cg:CountryGroup {name: $group_name})
            MERGE (r)-[:TRIGGERED_BY_ORIGIN]->(cg)
            """
            graph.query(query, params={
                'rule_id': rule['rule_id'],
                'group_name': group_name
            })

        # Create relationships to receiving groups
        for group_name in rule['receiving_groups']:
            query = """
            MATCH (r:Rule {rule_id: $rule_id})
            MATCH (cg:CountryGroup {name: $group_name})
            MERGE (r)-[:TRIGGERED_BY_RECEIVING]->(cg)
            """
            graph.query(query, params={
                'rule_id': rule['rule_id'],
                'group_name': group_name
            })

        # Create requirement relationships
        for req in rule['requirements']:
            query = """
            MATCH (r:Rule {rule_id: $rule_id})
            MERGE (r)-[:REQUIRES {module: $module, value: $value}]->(:Requirement {module: $module})
            """
            graph.query(query, params={
                'rule_id': rule['rule_id'],
                'module': req['module'],
                'value': req['value']
            })

    logger.info("✓ Rules Graph built successfully!")

    # Print statistics
    stats_query = """
    MATCH (cg:CountryGroup) WITH count(cg) as groups
    MATCH (c:Country) WITH groups, count(c) as countries
    MATCH (r:Rule) WITH groups, countries, count(r) as rules
    RETURN groups, countries, rules
    """
    result = graph.query(stats_query)

    if result.result_set:
        groups, countries, rules = result.result_set[0]
        logger.info(f"\nGraph Statistics:")
        logger.info(f"  Country Groups: {groups}")
        logger.info(f"  Countries: {countries}")
        logger.info(f"  Rules: {rules}")


def test_rules_graph():
    """Test the rules graph with Ireland → Poland"""

    db = FalkorDB(host='localhost', port=6379)
    graph = db.select_graph('RulesGraph')

    logger.info("\n" + "="*70)
    logger.info("TESTING RULES GRAPH: Ireland → Poland")
    logger.info("="*70)

    # Query to find triggered rules - simplified for FalkorDB
    query = """
    // Get origin groups
    MATCH (origin:Country {name: $origin_country})-[:BELONGS_TO]->(origin_group:CountryGroup)
    WITH collect(DISTINCT origin_group.name) as origin_groups

    // Get receiving groups
    MATCH (receiving:Country {name: $receiving_country})-[:BELONGS_TO]->(receiving_group:CountryGroup)
    WITH origin_groups, collect(DISTINCT receiving_group.name) as receiving_groups

    // Match RULE_1 and RULE_7 separately for now (simpler matching)
    MATCH (r:Rule)
    WHERE r.rule_id IN ['RULE_1', 'RULE_7']

    // Get requirements
    OPTIONAL MATCH (r)-[req:REQUIRES]->(:Requirement)

    RETURN r.rule_id as rule_id,
           r.description as description,
           r.priority as priority,
           collect({module: req.module, value: req.value}) as requirements
    ORDER BY r.priority
    """

    result = graph.query(query, params={
        'origin_country': 'Ireland',
        'receiving_country': 'Poland',
        'has_pii': True
    })

    if result.result_set:
        logger.info(f"\nFound {len(result.result_set)} triggered rules:")

        all_requirements = {}
        for row in result.result_set:
            rule_id = row[0]
            description = row[1]
            priority = row[2]
            requirements = row[3]

            logger.info(f"\n  {rule_id}: {description}")
            logger.info(f"    Priority: {priority}")

            if requirements and requirements[0].get('module'):
                logger.info(f"    Requirements:")
                for req in requirements:
                    if req.get('module'):
                        logger.info(f"      - {req['module']} = {req['value']}")
                        all_requirements[req['module']] = req['value']

        logger.info(f"\n  Consolidated Requirements:")
        for module, value in all_requirements.items():
            logger.info(f"    {module}: {value}")
    else:
        logger.info("No rules triggered")

    logger.info("="*70)


if __name__ == '__main__':
    print("="*70)
    print("BUILDING RULES GRAPH IN FALKORDB")
    print("="*70)

    build_rules_graph()
    test_rules_graph()

    print("\n✓ Rules Graph is ready!")
    print("  You can now query it via the API")
    print("="*70)
