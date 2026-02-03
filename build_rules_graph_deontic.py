#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Build Rules Graph with Deontic Logic Structure in FalkorDB
Uses formal policy framework: Rules → Actions, Permissions, Prohibitions → Duties

Structure:
- Rule -[:HAS_ACTION]-> Action
- Rule -[:HAS_PERMISSION]-> Permission
- Permission -[:CAN_HAVE_DUTY]-> Duty
- Rule -[:HAS_PROHIBITION]-> Prohibition
- Prohibition -[:CAN_HAVE_DUTY]-> Duty
- Rule -[:TRIGGERED_BY_ORIGIN]-> CountryGroup
- Rule -[:TRIGGERED_BY_RECEIVING]-> CountryGroup

ODRL Alignment:
- Rules implement ODRL (Open Digital Rights Language) policies
- Each Rule node has odrl_type (Permission/Prohibition), odrl_action, odrl_target
- Permissions map to ODRL permissions with duties as obligations
- Prohibitions map to ODRL prohibitions with duties as remedies/exceptions
- Actions map to ODRL actions (transfer, store, process)
- Assets are represented by data type flags (has_pii_required, health_data_required)
- Constraints are represented by match_type logic and country groups

Schema Conventions:
- empty origin_groups + origin_match_type='ALL' = "any origin"
- empty receiving_groups + receiving_match_type='ALL' = "any destination"
- receiving_match_type='NOT_IN' = inverse match (NOT in specified groups)
- Priority: lower number = higher priority (1 = highest, executes first)
"""

from falkordb import FalkorDB
import logging
import json
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def load_prohibition_rules_config():
    """Load prohibition rules configuration from JSON file"""
    config_path = Path(__file__).parent / "prohibition_rules_config.json"

    if not config_path.exists():
        logger.warning(f"⚠️  prohibition_rules_config.json not found at {config_path}")
        return {'prohibition_rules': {}}

    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
            enabled_count = sum(1 for rule in config.get('prohibition_rules', {}).values() if rule.get('enabled'))
            logger.info(f"✓ Loaded {enabled_count} enabled prohibition rules from config")
            return config
    except Exception as e:
        logger.error(f"Error loading prohibition rules config: {e}")
        return {'prohibition_rules': {}}


def build_rules_graph_deontic():
    """Build the Rules Graph with deontic logic structure"""

    db = FalkorDB(host='localhost', port=6379)
    graph = db.select_graph('RulesGraph')

    logger.info("Building Rules Graph with Deontic Logic...")

    # Load prohibition rules config FIRST (before creating any nodes)
    prohibition_config = load_prohibition_rules_config()

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
        "CREATE INDEX FOR (a:Action) ON (a.name)",
        "CREATE INDEX FOR (p:Permission) ON (p.name)",
        "CREATE INDEX FOR (pr:Prohibition) ON (pr.name)",
        "CREATE INDEX FOR (d:Duty) ON (d.name)",
    ]

    for idx_query in indexes:
        try:
            graph.query(idx_query)
        except:
            pass

    # 1. Create Country Groups and Countries (same as before)
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
        # BCR (Binding Corporate Rules) approved countries
        # Note: This list includes countries with approved BCR frameworks
        # EU/EEA member states are included as they support BCR under GDPR
        'BCR_COUNTRIES': [],  # Will be computed from EU_EEA + additional BCR countries
        'CROWN_DEPENDENCIES_ONLY': ['Jersey', 'Isle of Man', 'Guernsey'],
        'UK_ONLY': ['United Kingdom'],
        'EU_EEA_ADEQUACY_UK': []  # Will be computed
        # Note: US, US_RESTRICTED_COUNTRIES, CHINA_CLOUD now created dynamically from prohibition_rules_config.json
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

    # Compute BCR_COUNTRIES: EU/EEA + additional countries with BCR frameworks
    bcr_additional_countries = [
        'Algeria', 'Australia', 'Bahrain', 'Bangladesh', 'Bermuda',
        'Brazil', 'Canada', 'Cayman Islands', 'Chile', 'China',
        'British Virgin Islands', 'Egypt', 'Hong Kong', 'India', 'Indonesia',
        'Japan', 'Korea', 'Republic Of (South)', 'Kuwait', 'Macao', 'Malaysia',
        'Maldives', 'Mauritius', 'Mexico', 'New Zealand', 'Oman', 'Philippines',
        'Qatar', 'Saudi Arabia', 'Singapore', 'South Africa', 'Sri Lanka',
        'Switzerland', 'Taiwan', 'Thailand', 'Turkey', 'Turkiye',
        'United Arab Emirates', 'United Kingdom', 'United States of America',
        'Uruguay', 'Vietnam'
    ]
    country_groups['BCR_COUNTRIES'] = list(set(
        country_groups['EU_EEA_FULL'] +  # All EU/EEA member states
        bcr_additional_countries  # Additional BCR-approved countries
    ))

    # Add dynamic country groups from prohibition rules config
    logger.info("Adding dynamic country groups from prohibition rules config...")
    for config_key, rule_config in prohibition_config.get('prohibition_rules', {}).items():
        if not rule_config.get('enabled', False):
            continue

        # Create unique group names for origin and receiving countries
        origin_group_name = f"ORIGIN_{config_key}"
        receiving_group_name = f"RECEIVING_{config_key}"

        # Add origin countries to a group
        origin_countries = rule_config.get('origin_countries', [])
        if origin_countries:
            country_groups[origin_group_name] = origin_countries
            logger.info(f"  Added origin group '{origin_group_name}' with {len(origin_countries)} countries")

        # Add receiving countries to a group (skip if ["ANY"])
        receiving_countries = rule_config.get('receiving_countries', [])
        if receiving_countries and receiving_countries != ["ANY"]:
            country_groups[receiving_group_name] = receiving_countries
            logger.info(f"  Added receiving group '{receiving_group_name}' with {len(receiving_countries)} countries")

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

    # 2. Create Actions
    logger.info("Creating actions...")

    actions = [
        {'name': 'Transfer Data', 'description': 'Transfer data between jurisdictions'},
        {'name': 'Transfer PII', 'description': 'Transfer personally identifiable information'},
        {'name': 'Transfer Health Data', 'description': 'Transfer health-related data'},
        {'name': 'Store in Cloud', 'description': 'Store or process data in cloud infrastructure'}
    ]

    for action in actions:
        query = """
        CREATE (a:Action {
            name: $name,
            description: $description
        })
        """
        graph.query(query, params=action)

    # 3. Create Duties
    logger.info("Creating duties...")

    duties = [
        {
            'name': 'Complete PIA Module (CM)',
            'description': 'Complete Privacy Impact Assessment with CM status',
            'module': 'pia_module',
            'value': 'CM'
        },
        {
            'name': 'Complete TIA Module (CM)',
            'description': 'Complete Transfer Impact Assessment with CM status',
            'module': 'tia_module',
            'value': 'CM'
        },
        {
            'name': 'Complete HRPR Module (CM)',
            'description': 'Complete Human Rights Privacy Review with CM status',
            'module': 'hrpr_module',
            'value': 'CM'
        },
        {
            'name': 'Obtain US Legal Approval',
            'description': 'Obtain approval from US legal team before transfer',
            'module': None,
            'value': None
        },
        {
            'name': 'Obtain US Legal Exception',
            'description': 'Obtain legal exception from US legal team',
            'module': None,
            'value': None
        }
    ]

    for duty in duties:
        query = """
        CREATE (d:Duty {
            name: $name,
            description: $description,
            module: $module,
            value: $value
        })
        """
        graph.query(query, params=duty)

    # 4. Create Permissions
    logger.info("Creating permissions...")

    permissions = [
        {
            'name': 'EU/EEA Internal Transfer',
            'description': 'Permission to transfer data within EU/EEA/UK/Crown/Switzerland',
            'duties': ['Complete PIA Module (CM)']
        },
        {
            'name': 'EU to Adequacy Countries Transfer',
            'description': 'Permission to transfer from EU/EEA to adequacy decision countries',
            'duties': ['Complete PIA Module (CM)']
        },
        {
            'name': 'Crown Dependencies Transfer',
            'description': 'Permission to transfer from Crown Dependencies to Adequacy + EU/EEA',
            'duties': ['Complete PIA Module (CM)']
        },
        {
            'name': 'UK to Adequacy Transfer',
            'description': 'Permission to transfer from UK to Adequacy countries and EU/EEA',
            'duties': ['Complete PIA Module (CM)']
        },
        {
            'name': 'Switzerland Transfer',
            'description': 'Permission to transfer from Switzerland to approved jurisdictions',
            'duties': ['Complete PIA Module (CM)']
        },
        {
            'name': 'EU/EEA to Rest of World Transfer',
            'description': 'Permission to transfer from EU/EEA/Adequacy to rest of world',
            'duties': ['Complete PIA Module (CM)', 'Complete TIA Module (CM)']
        },
        {
            'name': 'BCR Countries Transfer',
            'description': 'Permission to transfer from BCR countries to any jurisdiction',
            'duties': ['Complete PIA Module (CM)', 'Complete HRPR Module (CM)']
        },
        {
            'name': 'PII Transfer',
            'description': 'Permission to transfer personal data (PII)',
            'duties': ['Complete PIA Module (CM)']
        }
    ]

    for perm in permissions:
        # Create permission node
        query = """
        CREATE (p:Permission {
            name: $name,
            description: $description
        })
        """
        graph.query(query, params={
            'name': perm['name'],
            'description': perm['description']
        })

        # Link to duties
        for duty_name in perm['duties']:
            query = """
            MATCH (p:Permission {name: $perm_name})
            MATCH (d:Duty {name: $duty_name})
            MERGE (p)-[:CAN_HAVE_DUTY]->(d)
            """
            graph.query(query, params={
                'perm_name': perm['name'],
                'duty_name': duty_name
            })

    # 5. Create Prohibitions
    logger.info("Creating prohibitions...")

    # Note: Static prohibitions removed - now loaded from prohibition_rules_config.json
    prohibitions = []

    # Add dynamic prohibitions from config
    logger.info("Creating prohibitions from config...")
    for config_key, rule_config in prohibition_config.get('prohibition_rules', {}).items():
        if not rule_config.get('enabled', False):
            continue

        prohibition_name = rule_config.get('prohibition_name', config_key)
        prohibition_description = rule_config.get('prohibition_description', '')
        duties_list = rule_config.get('duties', [])

        prohibitions.append({
            'name': prohibition_name,
            'description': prohibition_description,
            'duties': duties_list
        })
        logger.info(f"  Added prohibition: {prohibition_name}")

    for prohib in prohibitions:
        # Create prohibition node
        query = """
        CREATE (pr:Prohibition {
            name: $name,
            description: $description
        })
        """
        graph.query(query, params={
            'name': prohib['name'],
            'description': prohib['description']
        })

        # Link to duties (if any)
        for duty_name in prohib['duties']:
            query = """
            MATCH (pr:Prohibition {name: $prohib_name})
            MATCH (d:Duty {name: $duty_name})
            MERGE (pr)-[:CAN_HAVE_DUTY]->(d)
            """
            graph.query(query, params={
                'prohib_name': prohib['name'],
                'duty_name': duty_name
            })

    # 6. Create Rules with new structure
    logger.info("Creating rules with deontic structure...")

    # Schema conventions:
    # - empty origin_groups + origin_match_type='ALL' means "any origin country"
    # - empty receiving_groups + receiving_match_type='ALL' means "any destination country"
    # - Priority: lower number = higher priority (1 = highest)
    # - ODRL metadata: odrl_type (Permission/Prohibition), odrl_action, odrl_target

    rules = [
        {
            'rule_id': 'RULE_1',
            'description': 'EU/EEA/UK/Crown Dependencies/Switzerland internal transfer',
            'priority': 1,
            'origin_groups': ['EU_EEA_UK_CROWN_CH'],
            'receiving_groups': ['EU_EEA_UK_CROWN_CH'],
            'origin_match_type': 'ANY',
            'receiving_match_type': 'ANY',
            'has_pii_required': False,
            'action': 'Transfer Data',
            'permission': 'EU/EEA Internal Transfer',
            'prohibition': None,
            'odrl_type': 'Permission',
            'odrl_action': 'transfer',
            'odrl_target': 'Data'
        },
        {
            'rule_id': 'RULE_2',
            'description': 'EU/EEA to Adequacy Decision countries',
            'priority': 4,  # Adjusted to allow US rules higher priority
            'origin_groups': ['EU_EEA_FULL'],
            'receiving_groups': ['ADEQUACY_COUNTRIES'],
            'origin_match_type': 'ANY',
            'receiving_match_type': 'ANY',
            'has_pii_required': False,
            'action': 'Transfer Data',
            'permission': 'EU to Adequacy Countries Transfer',
            'prohibition': None,
            'odrl_type': 'Permission',
            'odrl_action': 'transfer',
            'odrl_target': 'Data'
        },
        {
            'rule_id': 'RULE_3',
            'description': 'Crown Dependencies to Adequacy + EU/EEA',
            'priority': 5,
            'origin_groups': ['CROWN_DEPENDENCIES_ONLY'],
            'receiving_groups': ['ADEQUACY_PLUS_EU'],
            'origin_match_type': 'ANY',
            'receiving_match_type': 'ANY',
            'has_pii_required': False,
            'action': 'Transfer Data',
            'permission': 'Crown Dependencies Transfer',
            'prohibition': None,
            'odrl_type': 'Permission',
            'odrl_action': 'transfer',
            'odrl_target': 'Data'
        },
        {
            'rule_id': 'RULE_4',
            'description': 'United Kingdom to Adequacy (excluding UK) + EU/EEA',
            'priority': 6,
            'origin_groups': ['UK_ONLY'],
            'receiving_groups': ['EU_EEA_ADEQUACY_UK'],
            'origin_match_type': 'ANY',
            'receiving_match_type': 'ANY',
            'has_pii_required': False,
            'action': 'Transfer Data',
            'permission': 'UK to Adequacy Transfer',
            'prohibition': None,
            'odrl_type': 'Permission',
            'odrl_action': 'transfer',
            'odrl_target': 'Data'
        },
        {
            'rule_id': 'RULE_5',
            'description': 'Switzerland to approved jurisdictions',
            'priority': 7,
            'origin_groups': ['SWITZERLAND'],
            'receiving_groups': ['SWITZERLAND_APPROVED'],
            'origin_match_type': 'ANY',
            'receiving_match_type': 'ANY',
            'has_pii_required': False,
            'action': 'Transfer Data',
            'permission': 'Switzerland Transfer',
            'prohibition': None,
            'odrl_type': 'Permission',
            'odrl_action': 'transfer',
            'odrl_target': 'Data'
        },
        {
            'rule_id': 'RULE_6',
            'description': 'EU/EEA/Adequacy to Rest of World',
            'priority': 8,
            'origin_groups': ['EU_EEA_ADEQUACY_UK'],
            'receiving_groups': ['EU_EEA_ADEQUACY_UK'],
            'origin_match_type': 'ANY',
            'receiving_match_type': 'NOT_IN',
            'has_pii_required': False,
            'action': 'Transfer Data',
            'permission': 'EU/EEA to Rest of World Transfer',
            'prohibition': None,
            'odrl_type': 'Permission',
            'odrl_action': 'transfer',
            'odrl_target': 'Data'
        },
        {
            'rule_id': 'RULE_7',
            'description': 'BCR Countries to any jurisdiction',
            'priority': 9,
            'origin_groups': ['BCR_COUNTRIES'],
            'receiving_groups': [],  # Empty list with match_type='ALL' means "any destination"
            'origin_match_type': 'ANY',
            'receiving_match_type': 'ALL',
            'has_pii_required': False,
            'action': 'Transfer Data',
            'permission': 'BCR Countries Transfer',
            'prohibition': None,
            'odrl_type': 'Permission',
            'odrl_action': 'transfer',
            'odrl_target': 'Data'
        },
        {
            'rule_id': 'RULE_8',
            'description': 'Transfer contains Personal Data (PII)',
            'priority': 10,
            'origin_groups': [],  # Empty list with match_type='ALL' means "any origin"
            'receiving_groups': [],  # Empty list with match_type='ALL' means "any destination"
            'origin_match_type': 'ALL',
            'receiving_match_type': 'ALL',
            'has_pii_required': True,
            'action': 'Transfer PII',
            'permission': 'PII Transfer',
            'prohibition': None,
            'odrl_type': 'Permission',
            'odrl_action': 'transfer',
            'odrl_target': 'PII'
        }
        # Note: US blocking rules (RULE_9, RULE_10, RULE_11) now loaded from prohibition_rules_config.json
    ]

    # Add dynamic rules from prohibition_rules_config.json
    logger.info("Adding dynamic prohibition rules from config...")
    for config_key, rule_config in prohibition_config.get('prohibition_rules', {}).items():
        if not rule_config.get('enabled', False):
            logger.info(f"  Skipping disabled rule: {config_key}")
            continue

        rule_id = rule_config.get('rule_id', f'RULE_CONFIG_{config_key}')
        priority = rule_config.get('priority', 100)
        origin_countries = rule_config.get('origin_countries', [])
        receiving_countries = rule_config.get('receiving_countries', [])
        bidirectional = rule_config.get('bidirectional', False)
        requires_pii = rule_config.get('requires_pii', False)
        requires_health_data = rule_config.get('requires_health_data', False)
        prohibition_name = rule_config.get('prohibition_name', config_key)
        action_name = rule_config.get('action_name', 'Transfer Data')
        odrl_type = rule_config.get('odrl_type', 'Prohibition')
        odrl_action = rule_config.get('odrl_action', 'transfer')
        odrl_target = rule_config.get('odrl_target', 'Data')

        # Determine groups and match types
        origin_group_name = f"ORIGIN_{config_key}"
        receiving_group_name = f"RECEIVING_{config_key}"

        # Handle receiving_countries = ["ANY"]
        if receiving_countries == ["ANY"]:
            receiving_groups_list = []
            receiving_match_type = 'ALL'
        else:
            receiving_groups_list = [receiving_group_name]
            receiving_match_type = 'ANY'

        # Create the rule
        dynamic_rule = {
            'rule_id': rule_id,
            'description': rule_config.get('prohibition_description', f'Configuration-based rule: {config_key}'),
            'priority': priority,
            'origin_groups': [origin_group_name] if origin_countries else [],
            'receiving_groups': receiving_groups_list,
            'origin_match_type': 'ANY',
            'receiving_match_type': receiving_match_type,
            'has_pii_required': requires_pii,
            'health_data_required': requires_health_data,
            'action': action_name,
            'permission': None,
            'prohibition': prohibition_name,
            'odrl_type': odrl_type,
            'odrl_action': odrl_action,
            'odrl_target': odrl_target
        }

        rules.append(dynamic_rule)
        logger.info(f"  Added dynamic rule {rule_id}: {prohibition_name} (priority {priority})")

        # Create bidirectional rule if requested
        if bidirectional and receiving_countries != ["ANY"]:
            reverse_rule_id = f"{rule_id}_REVERSE"
            reverse_origin_group = receiving_group_name
            reverse_receiving_group = origin_group_name

            reverse_rule = {
                'rule_id': reverse_rule_id,
                'description': f"Reverse: {dynamic_rule['description']}",
                'priority': priority,
                'origin_groups': [reverse_origin_group],
                'receiving_groups': [reverse_receiving_group],
                'origin_match_type': 'ANY',
                'receiving_match_type': 'ANY',
                'has_pii_required': requires_pii,
                'health_data_required': requires_health_data,
                'action': action_name,
                'permission': None,
                'prohibition': prohibition_name,
                'odrl_type': odrl_type,
                'odrl_action': odrl_action,
                'odrl_target': odrl_target
            }

            rules.append(reverse_rule)
            logger.info(f"  Added bidirectional reverse rule {reverse_rule_id}")

    # Load health data configuration for RULE_11
    health_config_path = Path(__file__).parent / "health_data_config.json"
    health_config_json = None
    if health_config_path.exists():
        with open(health_config_path, 'r') as f:
            health_config = json.load(f)
            health_config_json = json.dumps(health_config)
            logger.info(f"✓ Loaded health data config: {len(health_config['detection_rules']['keywords'])} keywords")

    for rule in rules:
        # Create rule node with ODRL metadata
        # For RULE_11 (health data), include the health detection configuration
        if rule['rule_id'] == 'RULE_11' and health_config_json:
            query = """
            CREATE (r:Rule {
                rule_id: $rule_id,
                description: $description,
                priority: $priority,
                origin_match_type: $origin_match_type,
                receiving_match_type: $receiving_match_type,
                has_pii_required: $has_pii_required,
                health_data_required: $health_data_required,
                odrl_type: $odrl_type,
                odrl_action: $odrl_action,
                odrl_target: $odrl_target,
                health_detection_config: $health_config
            })
            """
            graph.query(query, params={
                'rule_id': rule['rule_id'],
                'description': rule['description'],
                'priority': rule['priority'],
                'origin_match_type': rule['origin_match_type'],
                'receiving_match_type': rule['receiving_match_type'],
                'has_pii_required': rule.get('has_pii_required', False),
                'health_data_required': rule.get('health_data_required', False),
                'odrl_type': rule.get('odrl_type', 'Permission'),
                'odrl_action': rule.get('odrl_action', 'transfer'),
                'odrl_target': rule.get('odrl_target', 'Data'),
                'health_config': health_config_json
            })
        else:
            query = """
            CREATE (r:Rule {
                rule_id: $rule_id,
                description: $description,
                priority: $priority,
                origin_match_type: $origin_match_type,
                receiving_match_type: $receiving_match_type,
                has_pii_required: $has_pii_required,
                health_data_required: $health_data_required,
                odrl_type: $odrl_type,
                odrl_action: $odrl_action,
                odrl_target: $odrl_target
            })
            """
            graph.query(query, params={
                'rule_id': rule['rule_id'],
                'description': rule['description'],
                'priority': rule['priority'],
                'origin_match_type': rule['origin_match_type'],
                'receiving_match_type': rule['receiving_match_type'],
                'has_pii_required': rule.get('has_pii_required', False),
                'health_data_required': rule.get('health_data_required', False),
                'odrl_type': rule.get('odrl_type', 'Permission'),
                'odrl_action': rule.get('odrl_action', 'transfer'),
                'odrl_target': rule.get('odrl_target', 'Data')
            })

        # Link to action
        if rule.get('action'):
            query = """
            MATCH (r:Rule {rule_id: $rule_id})
            MATCH (a:Action {name: $action_name})
            MERGE (r)-[:HAS_ACTION]->(a)
            """
            graph.query(query, params={
                'rule_id': rule['rule_id'],
                'action_name': rule['action']
            })

        # Link to permission (if any)
        if rule.get('permission'):
            query = """
            MATCH (r:Rule {rule_id: $rule_id})
            MATCH (p:Permission {name: $perm_name})
            MERGE (r)-[:HAS_PERMISSION]->(p)
            """
            graph.query(query, params={
                'rule_id': rule['rule_id'],
                'perm_name': rule['permission']
            })

        # Link to prohibition (if any)
        if rule.get('prohibition'):
            query = """
            MATCH (r:Rule {rule_id: $rule_id})
            MATCH (pr:Prohibition {name: $prohib_name})
            MERGE (r)-[:HAS_PROHIBITION]->(pr)
            """
            graph.query(query, params={
                'rule_id': rule['rule_id'],
                'prohib_name': rule['prohibition']
            })

        # Link to origin groups
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

        # Link to receiving groups
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

    logger.info("✓ Deontic Rules Graph built successfully!")

    # Print statistics
    stats_query = """
    MATCH (cg:CountryGroup) WITH count(cg) as groups
    MATCH (c:Country) WITH groups, count(c) as countries
    MATCH (r:Rule) WITH groups, countries, count(r) as rules
    MATCH (a:Action) WITH groups, countries, rules, count(a) as actions
    MATCH (p:Permission) WITH groups, countries, rules, actions, count(p) as permissions
    MATCH (pr:Prohibition) WITH groups, countries, rules, actions, permissions, count(pr) as prohibitions
    MATCH (d:Duty) WITH groups, countries, rules, actions, permissions, prohibitions, count(d) as duties
    RETURN groups, countries, rules, actions, permissions, prohibitions, duties
    """
    result = graph.query(stats_query)

    if result.result_set:
        groups, countries, rules, actions, permissions, prohibitions, duties = result.result_set[0]
        logger.info(f"\n{'='*70}")
        logger.info("Graph Statistics:")
        logger.info(f"  Country Groups: {groups}")
        logger.info(f"  Countries: {countries}")
        logger.info(f"  Rules: {rules}")
        logger.info(f"  Actions: {actions}")
        logger.info(f"  Permissions: {permissions}")
        logger.info(f"  Prohibitions: {prohibitions}")
        logger.info(f"  Duties: {duties}")
        logger.info(f"{'='*70}")


def test_deontic_graph():
    """Test the deontic graph structure"""

    db = FalkorDB(host='localhost', port=6379)
    graph = db.select_graph('RulesGraph')

    logger.info("\n" + "="*70)
    logger.info("TESTING DEONTIC GRAPH STRUCTURE")
    logger.info("="*70)

    # Test 1: Ireland → Poland (Permission)
    logger.info("\nTest 1: Ireland → Poland (should have PERMISSIONS)")
    query = """
    MATCH (origin:Country {name: 'Ireland'})-[:BELONGS_TO]->(origin_group:CountryGroup)
    WITH collect(DISTINCT origin_group.name) as origin_groups
    MATCH (receiving:Country {name: 'Poland'})-[:BELONGS_TO]->(receiving_group:CountryGroup)
    WITH origin_groups, collect(DISTINCT receiving_group.name) as receiving_groups
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
    OPTIONAL MATCH (r)-[:HAS_PERMISSION]->(perm:Permission)
    OPTIONAL MATCH (r)-[:HAS_PROHIBITION]->(prohib:Prohibition)
    OPTIONAL MATCH (perm)-[:CAN_HAVE_DUTY]->(duty:Duty)
    RETURN r.rule_id as rule_id, perm.name as permission, prohib.name as prohibition,
           collect(DISTINCT duty.name) as duties
    """

    result = graph.query(query)
    logger.info(f"Found {len(result.result_set)} rules:")
    for row in result.result_set:
        rule_id, permission, prohibition, duties = row
        logger.info(f"  {rule_id}:")
        if permission:
            logger.info(f"    ✓ PERMISSION: {permission}")
            if duties and duties[0]:
                logger.info(f"    Duties: {', '.join(duties)}")
        if prohibition:
            logger.info(f"    ✗ PROHIBITION: {prohibition}")

    # Test 2: US → China (Prohibition)
    logger.info("\nTest 2: US → China (should have PROHIBITIONS)")
    query = """
    MATCH (origin:Country {name: 'United States'})-[:BELONGS_TO]->(origin_group:CountryGroup)
    WITH collect(DISTINCT origin_group.name) as origin_groups
    MATCH (receiving:Country {name: 'China'})-[:BELONGS_TO]->(receiving_group:CountryGroup)
    WITH origin_groups, collect(DISTINCT receiving_group.name) as receiving_groups
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
    OPTIONAL MATCH (r)-[:HAS_PERMISSION]->(perm:Permission)
    OPTIONAL MATCH (r)-[:HAS_PROHIBITION]->(prohib:Prohibition)
    OPTIONAL MATCH (prohib)-[:CAN_HAVE_DUTY]->(duty:Duty)
    RETURN r.rule_id as rule_id, perm.name as permission, prohib.name as prohibition,
           collect(DISTINCT duty.name) as duties
    """

    result = graph.query(query)
    logger.info(f"Found {len(result.result_set)} rules:")
    for row in result.result_set:
        rule_id, permission, prohibition, duties = row
        logger.info(f"  {rule_id}:")
        if permission:
            logger.info(f"    ✓ PERMISSION: {permission}")
        if prohibition:
            logger.info(f"    ✗ PROHIBITION: {prohibition}")
            if duties and duties[0]:
                logger.info(f"    Duties to get exception: {', '.join(duties)}")

    logger.info("="*70)


if __name__ == '__main__':
    print("="*70)
    print("BUILDING DEONTIC RULES GRAPH IN FALKORDB")
    print("="*70)
    print()

    build_rules_graph_deontic()

    print()
    print("="*70)
    print("✓ Deontic Rules Graph is ready!")
    print("  Structure: Rule → Action, Permission/Prohibition → Duties")
    print("="*70)
    print()

    test_deontic_graph()
