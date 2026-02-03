#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Production-Grade Sample Data Generator for DataTransferGraph

Generates realistic, randomized case data with proper relationships.
All multi-value fields are pipe-separated (|) and hierarchies are dash-separated (-).

Usage:
    python create_sample_data.py [--count N] [--output FILE] [--seed SEED]

Arguments:
    --count N: Number of cases to generate (default: 100)
    --output FILE: Output JSON file (default: sample_data.json)
    --seed SEED: Random seed for reproducibility (optional)
"""

import json
import sys
import random
from pathlib import Path
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


# ============================================================================
# REFERENCE DATA - Production-grade lists
# ============================================================================

COUNTRIES = {
    'EU_EEA': ['Germany', 'France', 'Ireland', 'Netherlands', 'Spain', 'Italy',
               'Belgium', 'Austria', 'Sweden', 'Poland', 'Denmark', 'Finland',
               'Portugal', 'Greece', 'Czech Republic', 'Hungary', 'Romania'],
    'UK_CROWN': ['United Kingdom', 'Jersey', 'Guernsey', 'Isle of Man'],
    'ADEQUACY': ['Switzerland', 'Canada', 'Japan', 'New Zealand', 'Argentina',
                 'Uruguay', 'Israel', 'South Korea'],
    'BCR': ['United States', 'India', 'Brazil', 'Australia', 'Singapore',
            'China', 'Mexico', 'South Africa', 'Philippines', 'Malaysia'],
    'OTHER': ['Russia', 'Turkey', 'United Arab Emirates', 'Saudi Arabia',
              'Egypt', 'Thailand', 'Indonesia', 'Vietnam', 'Colombia']
}

ALL_COUNTRIES = []
for country_list in COUNTRIES.values():
    ALL_COUNTRIES.extend(country_list)

PURPOSES = [
    'Marketing',
    'Analytics',
    'Customer Support',
    'Technology Operations',
    'Risk Management',
    'Compliance Monitoring',
    'Office Support',
    'Customer Service',
    'Product Development',
    'User Feedback',
    'Sales',
    'Service Delivery',
    'Reporting',
    'Data Analytics',
    'Business Intelligence',
    'Human Resources',
    'Finance Operations',
    'Legal Compliance',
    'Quality Assurance',
    'Training and Development'
]

PROCESS_HIERARCHIES = [
    ('Finance', 'Accounting', 'Payroll'),
    ('Finance', 'Accounting', 'Accounts Payable'),
    ('Finance', 'Accounting', 'Accounts Receivable'),
    ('Finance', 'Reporting', 'Financial Reporting'),
    ('Finance', 'Risk', 'Assessment'),
    ('HR', 'Recruitment', 'Candidate Screening'),
    ('HR', 'Employee Relations', 'Performance Management'),
    ('HR', 'Payroll', 'Salary Processing'),
    ('HR', 'Benefits', 'Health Insurance'),
    ('IT Operations', 'Cloud Services', 'Infrastructure'),
    ('IT Operations', 'Network', 'Maintenance'),
    ('IT Operations', 'Systems', 'Monitoring'),
    ('IT Support', 'Infrastructure', 'Server Management'),
    ('IT Support', 'Help Desk', 'User Support'),
    ('IT Governance', 'Security', 'Access Control'),
    ('IT Governance', 'Compliance', 'Audit'),
    ('Sales', 'Customer Management', 'CRM Operations'),
    ('Sales', 'Lead Management', 'Qualification'),
    ('Sales', 'B2B', 'Account Management'),
    ('Sales', 'B2C', 'Direct Sales'),
    ('Sales Operations', 'Forecasting', 'Pipeline Management'),
    ('Sales Operations', 'Territory Management', 'Assignment'),
    ('Marketing', 'Campaigns', 'Email Marketing'),
    ('Marketing', 'Digital Marketing', 'SEO'),
    ('Marketing', 'Digital Marketing', 'Social Media'),
    ('Marketing', 'Content', 'Creation'),
    ('Customer Service', 'Support Operations', 'Ticket Management'),
    ('Customer Service', 'Call Center', 'Inbound Support'),
    ('Customer Service', 'Quality', 'Monitoring'),
    ('Product Management', 'Research', 'User Studies'),
    ('Product Management', 'Development', 'Feature Planning'),
    ('Business Intelligence', 'Data Analytics', 'Dashboard'),
    ('Business Intelligence', 'Reporting', 'KPI Tracking'),
    ('Legal', 'Compliance', 'Regulatory'),
    ('Legal', 'Contracts', 'Review'),
    ('Channels', 'Mobile', 'App Support'),
    ('Channels', 'Mail/eMail', 'Communications'),
    ('Channels', 'Web', 'Portal Management'),
    ('Operations', 'Logistics', 'Shipping'),
    ('Operations', 'Supply Chain', 'Vendor Management')
]

PERSONAL_DATA_CATEGORIES = [
    'Contact Information',
    'Customer Data',
    'Employee Data',
    'Financial Data',
    'PII',
    'Authentication Data',
    'Behavioral Data',
    'Support Data',
    'Marketing Data',
    'Legal Data',
    'Technical Data',
    'Health Data',
    'Biometric Data',
    'Location Data',
    'Transaction Data',
    'Communication Data'
]

ASSESSMENT_STATUSES = {
    'Completed': 0.40,      # 40% chance - compliant
    'In Progress': 0.20,    # 20% chance - non-compliant
    'Not Started': 0.15,    # 15% chance - non-compliant
    'N/A': 0.20,           # 20% chance - non-compliant
    'WITHDRAWN': 0.05       # 5% chance - non-compliant
}

CASE_STATUSES = ['Active', 'Completed', 'Pending', 'Under Review']


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def weighted_choice(choices_dict):
    """Select item based on weighted probabilities"""
    items = list(choices_dict.keys())
    weights = list(choices_dict.values())
    return random.choices(items, weights=weights)[0]


def random_countries(count=None):
    """Select random countries, optionally multiple"""
    if count is None:
        count = random.choices([1, 2, 3, 4], weights=[0.60, 0.25, 0.10, 0.05])[0]
    return random.sample(ALL_COUNTRIES, min(count, len(ALL_COUNTRIES)))


def random_purposes(count=None):
    """Select random purposes, often multiple"""
    if count is None:
        count = random.choices([1, 2, 3, 4], weights=[0.40, 0.35, 0.20, 0.05])[0]
    return random.sample(PURPOSES, min(count, len(PURPOSES)))


def random_processes(count=None):
    """Select random process hierarchies"""
    if count is None:
        count = random.choices([1, 2, 3], weights=[0.70, 0.25, 0.05])[0]

    selected = random.sample(PROCESS_HIERARCHIES, min(count, len(PROCESS_HIERARCHIES)))

    # Format: "L1 - L2 - L3|L1 - L2 - L3"
    formatted = []
    for l1, l2, l3 in selected:
        # Randomly omit L3 30% of the time
        if random.random() < 0.30:
            l3 = ''
        formatted.append(f"{l1} - {l2} - {l3}")

    return '|'.join(formatted)


def random_personal_data_categories(count=None, include_pii_bias=True):
    """Select random personal data categories"""
    if count is None:
        # 30% chance of no PII
        if random.random() < 0.30:
            return ''
        count = random.choices([1, 2, 3], weights=[0.50, 0.35, 0.15])[0]

    categories = random.sample(PERSONAL_DATA_CATEGORIES, min(count, len(PERSONAL_DATA_CATEGORIES)))

    # Add PII to 60% of cases that have personal data
    if include_pii_bias and categories and random.random() < 0.60 and 'PII' not in categories:
        categories.append('PII')

    return '|'.join(categories)


def generate_assessment_statuses(origin, receiving_countries):
    """
    Generate realistic assessment statuses based on route.
    Higher compliance for regulated routes (EU, BCR countries).
    """
    # Check if route is highly regulated
    is_eu_route = any(origin in COUNTRIES['EU_EEA'] or r in COUNTRIES['EU_EEA']
                      for r in receiving_countries)
    is_bcr_route = origin in COUNTRIES['BCR'] or any(r in COUNTRIES['BCR']
                                                      for r in receiving_countries)

    # Adjust completion probability based on route
    if is_eu_route:
        completion_boost = 0.30  # EU routes more likely to be compliant
    elif is_bcr_route:
        completion_boost = 0.15
    else:
        completion_boost = 0.00

    # Generate each assessment status
    statuses = {}
    for assessment in ['piaStatus', 'tiaStatus', 'hrprStatus']:
        # Adjust weights for completion
        adjusted_weights = ASSESSMENT_STATUSES.copy()
        if completion_boost > 0:
            adjusted_weights['Completed'] = min(0.70, adjusted_weights['Completed'] + completion_boost)
            # Reduce other probabilities proportionally
            reduction = completion_boost / 4
            for key in ['In Progress', 'Not Started', 'N/A', 'WITHDRAWN']:
                adjusted_weights[key] = max(0.05, adjusted_weights[key] - reduction)

        statuses[assessment] = weighted_choice(adjusted_weights)

    # TIA only required for certain routes
    if not is_eu_route or all(r in COUNTRIES['EU_EEA'] + COUNTRIES['UK_CROWN']
                               for r in receiving_countries):
        # Internal EU or low-risk routes often don't need TIA
        if random.random() < 0.50:
            statuses['tiaStatus'] = 'N/A'

    # HRPR only for BCR routes
    if not is_bcr_route:
        if random.random() < 0.60:
            statuses['hrprStatus'] = 'N/A'

    return statuses


def generate_case(case_number):
    """Generate a single realistic case"""
    # Select origin and receiving countries
    origin = random.choice(ALL_COUNTRIES)
    receiving_count = random.choices([1, 2, 3, 4], weights=[0.65, 0.25, 0.08, 0.02])[0]

    # Ensure receiving countries are different from origin
    available_countries = [c for c in ALL_COUNTRIES if c != origin]
    receiving_countries = random.sample(available_countries, min(receiving_count, len(available_countries)))

    # Generate other fields
    purposes = random_purposes()
    processes = random_processes()
    personal_data = random_personal_data_categories()

    # Generate assessment statuses based on route
    assessment_statuses = generate_assessment_statuses(origin, receiving_countries)

    case = {
        'caseRefId': f'CASE_{case_number:05d}',
        'caseStatus': random.choice(CASE_STATUSES),
        'appId': f'APP_{random.randint(1, 999):03d}',
        'originatingCountry': origin,
        'receivingCountry': '|'.join(receiving_countries),
        'tiaStatus': assessment_statuses['tiaStatus'],
        'piaStatus': assessment_statuses['piaStatus'],
        'hrprStatus': assessment_statuses['hrprStatus'],
        'purposeOfProcessing': '|'.join(purposes),
        'processess': processes,
        'personalDataCategory': personal_data
    }

    return case


# ============================================================================
# MAIN GENERATION FUNCTION
# ============================================================================

def create_sample_data(count=100, output_file='sample_data.json', seed=None):
    """
    Generate randomized sample data

    Args:
        count: Number of cases to generate
        output_file: Output JSON file path
        seed: Random seed for reproducibility
    """
    if seed is not None:
        random.seed(seed)
        logger.info(f"🎲 Random seed: {seed}")

    logger.info("=" * 70)
    logger.info("PRODUCTION-GRADE SAMPLE DATA GENERATOR")
    logger.info("=" * 70)
    logger.info(f"📊 Generating {count} cases...")
    logger.info(f"📁 Output: {output_file}")
    logger.info("")

    # Generate cases
    cases = []
    for i in range(1, count + 1):
        if i % 20 == 0:
            logger.info(f"   Generated {i}/{count} cases...")
        case = generate_case(i)
        cases.append(case)

    logger.info(f"✅ Generated {len(cases)} cases")
    logger.info("")

    # Calculate statistics
    logger.info("📈 Data Statistics:")

    # Count compliant cases
    compliant_count = sum(1 for c in cases
                         if c['piaStatus'] == 'Completed'
                         and c['tiaStatus'] in ['Completed', 'N/A']
                         and c['hrprStatus'] in ['Completed', 'N/A'])
    logger.info(f"   Compliant cases: {compliant_count}/{len(cases)} ({100*compliant_count//len(cases)}%)")

    # Count cases with PII
    pii_count = sum(1 for c in cases if 'PII' in c.get('personalDataCategory', ''))
    logger.info(f"   Cases with PII: {pii_count}/{len(cases)} ({100*pii_count//len(cases)}%)")

    # Count unique countries
    origins = set(c['originatingCountry'] for c in cases)
    all_receiving = set()
    for c in cases:
        all_receiving.update(c['receivingCountry'].split('|'))
    logger.info(f"   Unique origin countries: {len(origins)}")
    logger.info(f"   Unique receiving countries: {len(all_receiving)}")

    # Count multi-value fields
    multi_receiving = sum(1 for c in cases if '|' in c['receivingCountry'])
    multi_purposes = sum(1 for c in cases if '|' in c['purposeOfProcessing'])
    multi_processes = sum(1 for c in cases if '|' in c['processess'])
    logger.info(f"   Multi-receiving cases: {multi_receiving}/{len(cases)} ({100*multi_receiving//len(cases)}%)")
    logger.info(f"   Multi-purpose cases: {multi_purposes}/{len(cases)} ({100*multi_purposes//len(cases)}%)")
    logger.info(f"   Multi-process cases: {multi_processes}/{len(cases)} ({100*multi_processes//len(cases)}%)")

    logger.info("")

    # Write to file
    try:
        output_path = Path(output_file)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(cases, f, indent=4, ensure_ascii=False)

        file_size = output_path.stat().st_size / 1024  # KB
        logger.info(f"💾 Saved to: {output_path.absolute()}")
        logger.info(f"📦 File size: {file_size:.1f} KB")
        logger.info("")
        logger.info("=" * 70)
        logger.info("✓ Sample data file created successfully!")
        logger.info("=" * 70)
        logger.info("")
        logger.info("To upload this data to FalkorDB, run:")
        logger.info(f"  python3 falkor_upload_json.py {output_file} --clear")
        logger.info("")

        return True

    except Exception as e:
        logger.error(f"❌ Error writing file: {e}")
        return False


def main():
    """Main entry point with argument parsing"""
    import argparse

    parser = argparse.ArgumentParser(
        description='Generate production-grade sample data for DataTransferGraph',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument('--count', type=int, default=100,
                       help='Number of cases to generate (default: 100)')
    parser.add_argument('--output', type=str, default='sample_data.json',
                       help='Output JSON file (default: sample_data.json)')
    parser.add_argument('--seed', type=int, default=None,
                       help='Random seed for reproducibility (optional)')

    args = parser.parse_args()

    success = create_sample_data(
        count=args.count,
        output_file=args.output,
        seed=args.seed
    )

    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
