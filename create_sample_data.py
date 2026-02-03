#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Production-Grade Sample Data Generator for DataTransferGraph
LARGE SCALE VERSION - Optimized for 35K+ nodes and 10M+ edges

Generates realistic, randomized case data with proper relationships.
All multi-value fields are pipe-separated (|) and hierarchies are dash-separated (-).

Usage:
    python create_sample_data.py [--count N] [--output FILE] [--seed SEED] [--large]

    # Generate standard dataset (100 cases)
    python create_sample_data.py

    # Generate large dataset (~35K nodes, 10K+ edges)
    python create_sample_data.py --large

    # Generate custom large dataset
    python create_sample_data.py --count 50000 --output large_sample_data.json

Arguments:
    --count N: Number of cases to generate (default: 100, large: 35000)
    --output FILE: Output JSON file (default: sample_data.json)
    --seed SEED: Random seed for reproducibility (optional)
    --large: Generate large dataset (~35K nodes)
"""

import json
import sys
import random
from pathlib import Path
from datetime import datetime
import logging
from concurrent.futures import ProcessPoolExecutor, as_completed
import multiprocessing

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


# ============================================================================
# REFERENCE DATA - Production-grade lists (EXPANDED for large scale)
# ============================================================================

COUNTRIES = {
    'EU_EEA': ['Germany', 'France', 'Ireland', 'Netherlands', 'Spain', 'Italy',
               'Belgium', 'Austria', 'Sweden', 'Poland', 'Denmark', 'Finland',
               'Portugal', 'Greece', 'Czech Republic', 'Hungary', 'Romania',
               'Bulgaria', 'Croatia', 'Cyprus', 'Estonia', 'Latvia', 'Lithuania',
               'Luxembourg', 'Malta', 'Slovakia', 'Slovenia', 'Norway', 'Iceland',
               'Liechtenstein'],
    'UK_CROWN': ['United Kingdom', 'Jersey', 'Guernsey', 'Isle of Man',
                 'Gibraltar', 'Bermuda', 'Cayman Islands', 'British Virgin Islands'],
    'ADEQUACY': ['Switzerland', 'Canada', 'Japan', 'New Zealand', 'Argentina',
                 'Uruguay', 'Israel', 'South Korea', 'Andorra', 'Faroe Islands'],
    'BCR': ['United States', 'India', 'Brazil', 'Australia', 'Singapore',
            'China', 'Mexico', 'South Africa', 'Philippines', 'Malaysia',
            'Indonesia', 'Thailand', 'Vietnam', 'Taiwan', 'Hong Kong'],
    'OTHER': ['Russia', 'Turkey', 'United Arab Emirates', 'Saudi Arabia',
              'Egypt', 'Thailand', 'Indonesia', 'Vietnam', 'Colombia',
              'Chile', 'Peru', 'Ecuador', 'Pakistan', 'Bangladesh', 'Nigeria',
              'Kenya', 'Morocco', 'Algeria', 'Tunisia', 'Qatar', 'Kuwait',
              'Bahrain', 'Oman', 'Jordan', 'Lebanon', 'Ukraine', 'Kazakhstan']
}

ALL_COUNTRIES = []
for country_list in COUNTRIES.values():
    ALL_COUNTRIES.extend(country_list)
# Remove duplicates while preserving order
ALL_COUNTRIES = list(dict.fromkeys(ALL_COUNTRIES))

# Extended purposes for more variety
PURPOSES = [
    'Marketing', 'Analytics', 'Customer Support', 'Technology Operations',
    'Risk Management', 'Compliance Monitoring', 'Office Support', 'Customer Service',
    'Product Development', 'User Feedback', 'Sales', 'Service Delivery',
    'Reporting', 'Data Analytics', 'Business Intelligence', 'Human Resources',
    'Finance Operations', 'Legal Compliance', 'Quality Assurance', 'Training and Development',
    'Fraud Detection', 'Credit Assessment', 'Insurance Processing', 'Claims Management',
    'Audit', 'Tax Compliance', 'Regulatory Reporting', 'Customer Onboarding',
    'KYC Verification', 'AML Screening', 'Transaction Monitoring', 'Portfolio Management',
    'Investment Analysis', 'Trading Operations', 'Settlement Processing', 'Custody Services',
    'Wealth Management', 'Pension Administration', 'Employee Benefits', 'Payroll Processing'
]

# Extended process hierarchies
PROCESS_HIERARCHIES = [
    ('Finance', 'Accounting', 'Payroll'),
    ('Finance', 'Accounting', 'Accounts Payable'),
    ('Finance', 'Accounting', 'Accounts Receivable'),
    ('Finance', 'Accounting', 'General Ledger'),
    ('Finance', 'Reporting', 'Financial Reporting'),
    ('Finance', 'Reporting', 'Regulatory Reporting'),
    ('Finance', 'Risk', 'Assessment'),
    ('Finance', 'Risk', 'Credit Risk'),
    ('Finance', 'Risk', 'Market Risk'),
    ('Finance', 'Risk', 'Operational Risk'),
    ('Finance', 'Treasury', 'Cash Management'),
    ('Finance', 'Treasury', 'FX Operations'),
    ('HR', 'Recruitment', 'Candidate Screening'),
    ('HR', 'Recruitment', 'Interview Management'),
    ('HR', 'Recruitment', 'Offer Processing'),
    ('HR', 'Employee Relations', 'Performance Management'),
    ('HR', 'Employee Relations', 'Grievance Handling'),
    ('HR', 'Payroll', 'Salary Processing'),
    ('HR', 'Payroll', 'Tax Withholding'),
    ('HR', 'Benefits', 'Health Insurance'),
    ('HR', 'Benefits', 'Retirement Plans'),
    ('HR', 'Training', 'Learning Management'),
    ('HR', 'Training', 'Certification Tracking'),
    ('IT Operations', 'Cloud Services', 'Infrastructure'),
    ('IT Operations', 'Cloud Services', 'Platform Management'),
    ('IT Operations', 'Cloud Services', 'SaaS Administration'),
    ('IT Operations', 'Network', 'Maintenance'),
    ('IT Operations', 'Network', 'Security'),
    ('IT Operations', 'Systems', 'Monitoring'),
    ('IT Operations', 'Systems', 'Backup Recovery'),
    ('IT Support', 'Infrastructure', 'Server Management'),
    ('IT Support', 'Infrastructure', 'Database Administration'),
    ('IT Support', 'Help Desk', 'User Support'),
    ('IT Support', 'Help Desk', 'Incident Management'),
    ('IT Governance', 'Security', 'Access Control'),
    ('IT Governance', 'Security', 'Vulnerability Management'),
    ('IT Governance', 'Compliance', 'Audit'),
    ('IT Governance', 'Compliance', 'Policy Management'),
    ('Sales', 'Customer Management', 'CRM Operations'),
    ('Sales', 'Customer Management', 'Account Planning'),
    ('Sales', 'Lead Management', 'Qualification'),
    ('Sales', 'Lead Management', 'Nurturing'),
    ('Sales', 'B2B', 'Account Management'),
    ('Sales', 'B2B', 'Contract Negotiation'),
    ('Sales', 'B2C', 'Direct Sales'),
    ('Sales', 'B2C', 'E-commerce'),
    ('Sales Operations', 'Forecasting', 'Pipeline Management'),
    ('Sales Operations', 'Forecasting', 'Revenue Planning'),
    ('Sales Operations', 'Territory Management', 'Assignment'),
    ('Sales Operations', 'Territory Management', 'Performance Tracking'),
    ('Marketing', 'Campaigns', 'Email Marketing'),
    ('Marketing', 'Campaigns', 'Event Marketing'),
    ('Marketing', 'Digital Marketing', 'SEO'),
    ('Marketing', 'Digital Marketing', 'SEM'),
    ('Marketing', 'Digital Marketing', 'Social Media'),
    ('Marketing', 'Digital Marketing', 'Display Advertising'),
    ('Marketing', 'Content', 'Creation'),
    ('Marketing', 'Content', 'Distribution'),
    ('Marketing', 'Analytics', 'Campaign Analytics'),
    ('Marketing', 'Analytics', 'Customer Insights'),
    ('Customer Service', 'Support Operations', 'Ticket Management'),
    ('Customer Service', 'Support Operations', 'Escalation Handling'),
    ('Customer Service', 'Call Center', 'Inbound Support'),
    ('Customer Service', 'Call Center', 'Outbound Campaigns'),
    ('Customer Service', 'Quality', 'Monitoring'),
    ('Customer Service', 'Quality', 'Training'),
    ('Product Management', 'Research', 'User Studies'),
    ('Product Management', 'Research', 'Market Research'),
    ('Product Management', 'Development', 'Feature Planning'),
    ('Product Management', 'Development', 'Roadmap Management'),
    ('Business Intelligence', 'Data Analytics', 'Dashboard'),
    ('Business Intelligence', 'Data Analytics', 'Advanced Analytics'),
    ('Business Intelligence', 'Reporting', 'KPI Tracking'),
    ('Business Intelligence', 'Reporting', 'Executive Reporting'),
    ('Legal', 'Compliance', 'Regulatory'),
    ('Legal', 'Compliance', 'Data Privacy'),
    ('Legal', 'Contracts', 'Review'),
    ('Legal', 'Contracts', 'Negotiation'),
    ('Legal', 'Litigation', 'Case Management'),
    ('Channels', 'Mobile', 'App Support'),
    ('Channels', 'Mobile', 'App Development'),
    ('Channels', 'Mail/eMail', 'Communications'),
    ('Channels', 'Mail/eMail', 'Campaigns'),
    ('Channels', 'Web', 'Portal Management'),
    ('Channels', 'Web', 'Self-Service'),
    ('Operations', 'Logistics', 'Shipping'),
    ('Operations', 'Logistics', 'Warehousing'),
    ('Operations', 'Supply Chain', 'Vendor Management'),
    ('Operations', 'Supply Chain', 'Procurement'),
    ('Risk Management', 'Credit Risk', 'Scoring'),
    ('Risk Management', 'Credit Risk', 'Collections'),
    ('Risk Management', 'Fraud', 'Detection'),
    ('Risk Management', 'Fraud', 'Investigation'),
    ('Compliance', 'AML', 'Screening'),
    ('Compliance', 'AML', 'Investigation'),
    ('Compliance', 'KYC', 'Onboarding'),
    ('Compliance', 'KYC', 'Periodic Review'),
]

PERSONAL_DATA_CATEGORIES = [
    'Contact Information', 'Customer Data', 'Employee Data', 'Financial Data',
    'PII', 'Authentication Data', 'Behavioral Data', 'Support Data',
    'Marketing Data', 'Legal Data', 'Technical Data', 'Health Data',
    'Biometric Data', 'Location Data', 'Transaction Data', 'Communication Data',
    'Credit Data', 'Employment History', 'Educational Data', 'Social Media Data',
    'Device Data', 'Network Data', 'Cookies Data', 'Preferences Data',
    'Family Data', 'Government ID', 'Tax Data', 'Insurance Data'
]

# Valid case statuses - ONLY these will be searchable
VALID_CASE_STATUSES = ['Active', 'Completed', 'Complete', 'Published']
# All case statuses for generation (includes non-searchable)
ALL_CASE_STATUSES = VALID_CASE_STATUSES + ['Pending', 'Under Review', 'Draft', 'Withdrawn', 'Archived']

ASSESSMENT_STATUSES = {
    'Completed': 0.45,      # 45% chance - compliant
    'In Progress': 0.15,    # 15% chance - non-compliant
    'Not Started': 0.10,    # 10% chance - non-compliant
    'N/A': 0.25,           # 25% chance - non-compliant
    'WITHDRAWN': 0.05       # 5% chance - non-compliant
}


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def weighted_choice(choices_dict):
    """Select item based on weighted probabilities"""
    items = list(choices_dict.keys())
    weights = list(choices_dict.values())
    return random.choices(items, weights=weights)[0]


def random_countries(count=None, exclude_countries=None):
    """Select random countries, optionally multiple"""
    if exclude_countries is None:
        exclude_countries = set()

    available = [c for c in ALL_COUNTRIES if c not in exclude_countries]

    if count is None:
        count = random.choices([1, 2, 3, 4, 5], weights=[0.50, 0.25, 0.15, 0.07, 0.03])[0]

    return random.sample(available, min(count, len(available)))


def random_purposes(count=None):
    """Select random purposes, often multiple"""
    if count is None:
        count = random.choices([1, 2, 3, 4, 5], weights=[0.30, 0.35, 0.20, 0.10, 0.05])[0]
    return random.sample(PURPOSES, min(count, len(PURPOSES)))


def random_processes(count=None):
    """Select random process hierarchies"""
    if count is None:
        count = random.choices([1, 2, 3, 4], weights=[0.60, 0.25, 0.10, 0.05])[0]

    selected = random.sample(PROCESS_HIERARCHIES, min(count, len(PROCESS_HIERARCHIES)))

    # Format: "L1 - L2 - L3|L1 - L2 - L3"
    formatted = []
    for l1, l2, l3 in selected:
        # Randomly omit L3 20% of the time
        if random.random() < 0.20:
            l3 = ''
        formatted.append(f"{l1} - {l2} - {l3}")

    return '|'.join(formatted)


def random_personal_data_categories(count=None, include_pii_bias=True):
    """Select random personal data categories"""
    if count is None:
        # 20% chance of no PII
        if random.random() < 0.20:
            return ''
        count = random.choices([1, 2, 3, 4], weights=[0.40, 0.35, 0.15, 0.10])[0]

    categories = random.sample(PERSONAL_DATA_CATEGORIES, min(count, len(PERSONAL_DATA_CATEGORIES)))

    # Add PII to 70% of cases that have personal data
    if include_pii_bias and categories and random.random() < 0.70 and 'PII' not in categories:
        categories.append('PII')

    return '|'.join(categories)


def generate_assessment_statuses(origin, receiving_countries, bias_completed=False):
    """
    Generate realistic assessment statuses based on route.
    Higher compliance for regulated routes (EU, BCR countries).

    Args:
        origin: Origin country
        receiving_countries: List of receiving countries
        bias_completed: If True, bias towards "Completed" status for searchable cases
    """
    # Check if route is highly regulated
    is_eu_route = any(origin in COUNTRIES['EU_EEA'] or r in COUNTRIES['EU_EEA']
                      for r in receiving_countries)
    is_bcr_route = origin in COUNTRIES['BCR'] or any(r in COUNTRIES['BCR']
                                                      for r in receiving_countries)

    # Adjust completion probability based on route
    if is_eu_route:
        completion_boost = 0.35
    elif is_bcr_route:
        completion_boost = 0.20
    else:
        completion_boost = 0.00

    # Additional boost for searchable cases
    if bias_completed:
        completion_boost += 0.25

    # Generate each assessment status
    statuses = {}
    for assessment in ['piaStatus', 'tiaStatus', 'hrprStatus']:
        adjusted_weights = ASSESSMENT_STATUSES.copy()
        if completion_boost > 0:
            adjusted_weights['Completed'] = min(0.80, adjusted_weights['Completed'] + completion_boost)
            reduction = completion_boost / 4
            for key in ['In Progress', 'Not Started', 'N/A', 'WITHDRAWN']:
                adjusted_weights[key] = max(0.03, adjusted_weights[key] - reduction)

        statuses[assessment] = weighted_choice(adjusted_weights)

    # TIA only required for certain routes
    if not is_eu_route or all(r in COUNTRIES['EU_EEA'] + COUNTRIES['UK_CROWN']
                               for r in receiving_countries):
        if random.random() < 0.40:
            statuses['tiaStatus'] = 'N/A'

    # HRPR only for BCR routes
    if not is_bcr_route:
        if random.random() < 0.50:
            statuses['hrprStatus'] = 'N/A'

    return statuses


def generate_case(case_number, bias_valid_status=True):
    """
    Generate a single realistic case

    Args:
        case_number: Sequential case number
        bias_valid_status: If True, 85% of cases will have valid/searchable status
    """
    # Select origin and receiving countries
    origin = random.choice(ALL_COUNTRIES)
    receiving_count = random.choices([1, 2, 3, 4, 5], weights=[0.55, 0.25, 0.12, 0.05, 0.03])[0]

    # Ensure receiving countries are different from origin
    receiving_countries = random_countries(receiving_count, exclude_countries={origin})

    # Generate other fields
    purposes = random_purposes()
    processes = random_processes()
    personal_data = random_personal_data_categories()

    # Determine case status - bias towards valid/searchable statuses
    if bias_valid_status and random.random() < 0.85:
        case_status = random.choice(VALID_CASE_STATUSES)
        # Bias assessments towards completed for valid status cases
        assessment_statuses = generate_assessment_statuses(origin, receiving_countries, bias_completed=True)
    else:
        case_status = random.choice(ALL_CASE_STATUSES)
        assessment_statuses = generate_assessment_statuses(origin, receiving_countries, bias_completed=False)

    case = {
        'caseRefId': f'CASE_{case_number:06d}',
        'caseStatus': case_status,
        'appId': f'APP_{random.randint(1, 9999):04d}',
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


def generate_cases_batch(start_num, batch_size, seed_offset=0):
    """Generate a batch of cases (for parallel processing)"""
    # Set seed based on offset for reproducibility
    random.seed(42 + seed_offset)

    cases = []
    for i in range(start_num, start_num + batch_size):
        cases.append(generate_case(i))

    return cases


# ============================================================================
# MAIN GENERATION FUNCTION
# ============================================================================

def create_sample_data(count=100, output_file='sample_data.json', seed=None, use_parallel=False):
    """
    Generate randomized sample data

    Args:
        count: Number of cases to generate
        output_file: Output JSON file path
        seed: Random seed for reproducibility
        use_parallel: Use parallel processing for large datasets
    """
    if seed is not None:
        random.seed(seed)
        logger.info(f"Random seed: {seed}")

    logger.info("=" * 70)
    logger.info("PRODUCTION-GRADE SAMPLE DATA GENERATOR - LARGE SCALE")
    logger.info("=" * 70)
    logger.info(f"Generating {count:,} cases...")
    logger.info(f"Output: {output_file}")
    logger.info("")

    # Calculate expected graph size
    expected_nodes = (
        count +  # Case nodes
        len(ALL_COUNTRIES) +  # Country nodes
        len(PURPOSES) +  # Purpose nodes
        len(PROCESS_HIERARCHIES) * 3 +  # Process nodes (L1, L2, L3)
        len(PERSONAL_DATA_CATEGORIES)  # Personal data category nodes
    )

    # Each case creates multiple edges
    avg_edges_per_case = (
        1 +  # ORIGINATES_FROM
        2.5 +  # TRANSFERS_TO (avg 2.5 receiving countries)
        3 +  # HAS_PURPOSE (avg 3 purposes)
        6 +  # HAS_PROCESS_L1/L2/L3 (avg 2 hierarchies * 3 levels)
        3  # HAS_PERSONAL_DATA_CATEGORY (avg 3 categories)
    )
    expected_edges = int(count * avg_edges_per_case)

    logger.info(f"Expected graph size:")
    logger.info(f"  - Nodes: ~{expected_nodes:,}")
    logger.info(f"  - Edges: ~{expected_edges:,}")
    logger.info("")

    # Generate cases
    cases = []

    if use_parallel and count > 10000:
        # Use parallel processing for large datasets
        num_workers = min(multiprocessing.cpu_count(), 8)
        batch_size = count // num_workers

        logger.info(f"Using {num_workers} parallel workers...")

        with ProcessPoolExecutor(max_workers=num_workers) as executor:
            futures = []
            for i in range(num_workers):
                start_num = i * batch_size + 1
                actual_batch_size = batch_size if i < num_workers - 1 else count - start_num + 1
                futures.append(executor.submit(generate_cases_batch, start_num, actual_batch_size, i))

            for future in as_completed(futures):
                cases.extend(future.result())
                logger.info(f"   Completed batch: {len(cases):,}/{count:,} cases")
    else:
        # Sequential generation
        log_interval = max(count // 20, 100)
        for i in range(1, count + 1):
            if i % log_interval == 0:
                logger.info(f"   Generated {i:,}/{count:,} cases...")
            case = generate_case(i)
            cases.append(case)

    logger.info(f"Generated {len(cases):,} cases")
    logger.info("")

    # Calculate statistics
    logger.info("Data Statistics:")

    # Count compliant cases (all assessments completed or N/A where appropriate)
    compliant_count = sum(1 for c in cases
                         if c['piaStatus'] == 'Completed'
                         and c['tiaStatus'] in ['Completed', 'N/A']
                         and c['hrprStatus'] in ['Completed', 'N/A'])
    logger.info(f"   Compliant cases: {compliant_count:,}/{len(cases):,} ({100*compliant_count//len(cases)}%)")

    # Count cases with valid status (searchable)
    valid_status_count = sum(1 for c in cases if c['caseStatus'] in VALID_CASE_STATUSES)
    logger.info(f"   Searchable cases (valid status): {valid_status_count:,}/{len(cases):,} ({100*valid_status_count//len(cases)}%)")

    # Count cases with PII
    pii_count = sum(1 for c in cases if 'PII' in c.get('personalDataCategory', ''))
    logger.info(f"   Cases with PII: {pii_count:,}/{len(cases):,} ({100*pii_count//len(cases)}%)")

    # Count unique countries
    origins = set(c['originatingCountry'] for c in cases)
    all_receiving = set()
    for c in cases:
        all_receiving.update(c['receivingCountry'].split('|'))
    logger.info(f"   Unique origin countries: {len(origins)}")
    logger.info(f"   Unique receiving countries: {len(all_receiving)}")

    # Count edges
    total_edges = 0
    for c in cases:
        total_edges += 1  # ORIGINATES_FROM
        total_edges += len(c['receivingCountry'].split('|')) if c['receivingCountry'] else 0  # TRANSFERS_TO
        total_edges += len(c['purposeOfProcessing'].split('|')) if c['purposeOfProcessing'] else 0  # HAS_PURPOSE
        processes = c['processess'].split('|') if c['processess'] else []
        for proc in processes:
            parts = [p.strip() for p in proc.split('-') if p.strip()]
            total_edges += len(parts)  # HAS_PROCESS_L1/L2/L3
        total_edges += len(c['personalDataCategory'].split('|')) if c['personalDataCategory'] else 0  # HAS_PERSONAL_DATA_CATEGORY

    logger.info(f"   Total edges to be created: {total_edges:,}")

    logger.info("")

    # Write to file
    try:
        output_path = Path(output_file)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(cases, f, indent=2, ensure_ascii=False)

        file_size = output_path.stat().st_size / (1024 * 1024)  # MB
        logger.info(f"Saved to: {output_path.absolute()}")
        logger.info(f"File size: {file_size:.1f} MB")
        logger.info("")
        logger.info("=" * 70)
        logger.info("Sample data file created successfully!")
        logger.info("=" * 70)
        logger.info("")
        logger.info("To upload this data to FalkorDB, run:")
        logger.info(f"  python3 falkor_upload_json.py {output_file} --clear")
        logger.info("")

        return True

    except Exception as e:
        logger.error(f"Error writing file: {e}")
        return False


def main():
    """Main entry point with argument parsing"""
    import argparse

    parser = argparse.ArgumentParser(
        description='Generate production-grade sample data for DataTransferGraph (Large Scale)',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument('--count', type=int, default=None,
                       help='Number of cases to generate (default: 100, large: 35000)')
    parser.add_argument('--output', type=str, default='sample_data.json',
                       help='Output JSON file (default: sample_data.json)')
    parser.add_argument('--seed', type=int, default=42,
                       help='Random seed for reproducibility (default: 42)')
    parser.add_argument('--large', action='store_true',
                       help='Generate large dataset (~35K nodes)')
    parser.add_argument('--parallel', action='store_true',
                       help='Use parallel processing for large datasets')

    args = parser.parse_args()

    # Determine count
    if args.count:
        count = args.count
    elif args.large:
        count = 35000
        args.output = 'large_sample_data.json' if args.output == 'sample_data.json' else args.output
    else:
        count = 100

    success = create_sample_data(
        count=count,
        output_file=args.output,
        seed=args.seed,
        use_parallel=args.parallel
    )

    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
