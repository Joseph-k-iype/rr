#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FalkorDB Data Upload - Load JSON data into DataTransferGraph

This script loads case data from a JSON file into FalkorDB's DataTransferGraph.
Handles pipe-separated (|) values and dash-separated (-) process hierarchies.

Usage:
    python falkor_upload_json.py [json_file] [--clear]

Arguments:
    json_file: Path to JSON file (default: sample_data.json)
    --clear: Clear existing graph before loading (optional)

JSON Format:
[
    {
        "caseRefId": "CASE_12345",
        "caseStatus": "Completed",
        "appId": "APP_67890",
        "originatingCountry": "United States",
        "receivingCountry": "Germany|France|United Kingdom",
        "tiaStatus": "Completed",
        "piaStatus": "N/A",
        "hrprStatus": "WITHDRAWN",
        "purposeOfProcessing": "Office Support|Customer Service",
        "processess": "Channels - Mobile - |Channels - Mail/eMail - ",
        "personalDataCategory": "PII|Financial Data"
    }
]

Process Format:
- Pipe (|) separates multiple process hierarchies
- Dash (-) separates levels within a hierarchy: "ProcessL1 - ProcessL2 - ProcessL3"
- Example: "Finance - Accounting - Payroll|HR - Recruitment - "
  Creates: (Finance, Accounting, Payroll) and (HR, Recruitment, empty)
"""

import json
import sys
from pathlib import Path
from falkordb import FalkorDB
import logging

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


def parse_pipe_separated(value: str) -> list:
    """
    Parse pipe-separated OR comma-separated string into list of unique values

    - Splits by pipe (|) OR comma (,) OR both
    - Strips whitespace
    - Filters empty values
    - Removes duplicates while preserving order

    Examples:
        "China|China|India" -> ["China", "India"]
        "Germany,France,Spain" -> ["Germany", "France", "Spain"]
        "UK|USA,Canada" -> ["UK", "USA", "Canada"]
    """
    if not value:
        return []

    # Replace pipes with commas for unified splitting
    # This allows mixed separators: "A|B,C" -> "A,B,C"
    normalized = value.replace('|', ',')

    # Split, strip, and filter empty
    items = [item.strip() for item in normalized.split(',') if item.strip()]

    # Deduplicate while preserving order
    seen = set()
    unique_items = []
    for item in items:
        if item not in seen:
            seen.add(item)
            unique_items.append(item)

    return unique_items


def parse_process_hierarchy(process_string: str) -> list:
    """
    Parse process hierarchy string into (L1, L2, L3) tuples

    Format: "ProcessL1 - ProcessL2 - ProcessL3|ProcessL1 - ProcessL2 - "

    Returns: [(L1, L2, L3), (L1, L2, None), ...]
    """
    if not process_string:
        return []

    hierarchies = []
    # Split by pipe to get individual process paths
    processes = parse_pipe_separated(process_string)

    for process in processes:
        # Split by dash to get hierarchy levels
        parts = [p.strip() for p in process.split('-')]

        # Extract L1, L2, L3 (pad with None if not enough parts)
        l1 = parts[0] if len(parts) > 0 and parts[0] else None
        l2 = parts[1] if len(parts) > 1 and parts[1] else None
        l3 = parts[2] if len(parts) > 2 and parts[2] else None

        # Only add if at least L1 exists
        if l1:
            hierarchies.append((l1, l2, l3))

    return hierarchies


def load_json_to_graph(json_file: str, clear_graph: bool = False):
    """
    Load case data from JSON file into DataTransferGraph

    Args:
        json_file: Path to JSON file
        clear_graph: If True, clear existing graph before loading
    """
    # Validate file exists
    json_path = Path(json_file)
    if not json_path.exists():
        logger.error(f"❌ File not found: {json_file}")
        return False

    # Load JSON with UTF-8 encoding
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        logger.error(f"❌ Invalid JSON: {e}")
        return False
    except Exception as e:
        logger.error(f"❌ Error reading file: {e}")
        return False

    # Handle both array format and object with 'cases' key
    if isinstance(data, list):
        cases = data
    elif isinstance(data, dict) and 'cases' in data:
        cases = data['cases']
    else:
        logger.error("❌ JSON must be an array or have 'cases' array at root level")
        return False

    logger.info(f"📁 Loaded {len(cases)} cases from {json_file}")

    # Connect to FalkorDB
    try:
        db = FalkorDB(host='localhost', port=6379)
        graph = db.select_graph('DataTransferGraph')
    except Exception as e:
        logger.error(f"❌ Cannot connect to FalkorDB: {e}")
        logger.info("Make sure FalkorDB is running: docker run -p 6379:6379 falkordb/falkordb:latest")
        return False

    # Clear graph if requested
    if clear_graph:
        logger.info("🗑️  Clearing existing DataTransferGraph...")
        try:
            graph.query("MATCH (n) DETACH DELETE n")
            logger.info("✓ Graph cleared")
        except Exception as e:
            logger.warning(f"⚠️  Error clearing graph: {e}")

    # Create indexes for performance
    logger.info("📑 Creating indexes...")
    indexes = [
        "CREATE INDEX FOR (c:Case) ON (c.case_ref_id)",
        "CREATE INDEX FOR (ct:Country) ON (ct.name)",
        "CREATE INDEX FOR (j:Jurisdiction) ON (j.name)",
        "CREATE INDEX FOR (p:Purpose) ON (p.name)",
        "CREATE INDEX FOR (p1:ProcessL1) ON (p1.name)",
        "CREATE INDEX FOR (p2:ProcessL2) ON (p2.name)",
        "CREATE INDEX FOR (p3:ProcessL3) ON (p3.name)",
        "CREATE INDEX FOR (pd:PersonalData) ON (pd.name)",
        "CREATE INDEX FOR (pdc:PersonalDataCategory) ON (pdc.name)",
    ]

    for idx_query in indexes:
        try:
            graph.query(idx_query)
        except:
            pass  # Index may already exist

    # Load each case
    success_count = 0
    error_count = 0

    for i, case in enumerate(cases, 1):
        case_ref_id = case.get('caseRefId', case.get('case_ref_id', f'CASE-{i:05d}'))
        logger.info(f"⏳ [{i}/{len(cases)}] Loading {case_ref_id}...")

        try:
            # Create Case node
            case_query = """
            CREATE (c:Case {
                case_ref_id: $case_ref_id,
                app_id: $app_id,
                case_status: $case_status,
                pia_status: $pia_status,
                tia_status: $tia_status,
                hrpr_status: $hrpr_status
            })
            """

            graph.query(case_query, params={
                'case_ref_id': case_ref_id,
                'app_id': case.get('appId', case.get('app_id', '')),
                'case_status': case.get('caseStatus', case.get('case_status', 'Active')),
                'pia_status': case.get('piaStatus', case.get('pia_status', 'N/A')),
                'tia_status': case.get('tiaStatus', case.get('tia_status', 'N/A')),
                'hrpr_status': case.get('hrprStatus', case.get('hrpr_status', 'N/A'))
            })

            # Create origin country relationship(s)
            # Handle both single country and pipe-separated (defensive)
            origin_str = case.get('originatingCountry', case.get('origin_country', ''))
            if isinstance(origin_str, str):
                origin_countries = parse_pipe_separated(origin_str)
            elif isinstance(origin_str, list):
                origin_countries = origin_str
            else:
                origin_countries = []

            # Create relationship for each unique origin country
            for origin in origin_countries:
                origin_query = """
                MATCH (c:Case {case_ref_id: $case_ref_id})
                MERGE (origin:Country {name: $origin_country})
                MERGE (c)-[:ORIGINATES_FROM]->(origin)
                """
                graph.query(origin_query, params={
                    'case_ref_id': case_ref_id,
                    'origin_country': origin.strip()
                })

            # Create receiving jurisdictions (pipe-separated)
            receiving_str = case.get('receivingCountry', case.get('receiving_countries', ''))
            if isinstance(receiving_str, str):
                receiving_countries = parse_pipe_separated(receiving_str)
            elif isinstance(receiving_str, list):
                receiving_countries = receiving_str
            else:
                receiving_countries = []

            for receiving in receiving_countries:
                receiving_query = """
                MATCH (c:Case {case_ref_id: $case_ref_id})
                MERGE (j:Jurisdiction {name: $receiving})
                MERGE (c)-[:TRANSFERS_TO]->(j)
                """
                graph.query(receiving_query, params={
                    'case_ref_id': case_ref_id,
                    'receiving': receiving.strip()
                })

            # Create purposes (pipe-separated)
            purpose_str = case.get('purposeOfProcessing', case.get('purposes', ''))
            if isinstance(purpose_str, str):
                purposes = parse_pipe_separated(purpose_str)
            elif isinstance(purpose_str, list):
                purposes = purpose_str
            else:
                purposes = []

            for purpose in purposes:
                purpose_query = """
                MATCH (c:Case {case_ref_id: $case_ref_id})
                MERGE (p:Purpose {name: $purpose})
                MERGE (c)-[:HAS_PURPOSE]->(p)
                """
                graph.query(purpose_query, params={
                    'case_ref_id': case_ref_id,
                    'purpose': purpose.strip()
                })

            # Parse and create process hierarchies
            process_str = case.get('processess', case.get('processes', ''))
            if isinstance(process_str, str):
                process_hierarchies = parse_process_hierarchy(process_str)
            else:
                # Handle explicit L1, L2, L3 fields
                process_hierarchies = []
                l1 = case.get('process_l1')
                l2 = case.get('process_l2')
                l3 = case.get('process_l3')
                if l1:
                    process_hierarchies.append((l1, l2, l3))

            for l1, l2, l3 in process_hierarchies:
                if l1:
                    p1_query = """
                    MATCH (c:Case {case_ref_id: $case_ref_id})
                    MERGE (p:ProcessL1 {name: $process_l1})
                    MERGE (c)-[:HAS_PROCESS_L1]->(p)
                    """
                    graph.query(p1_query, params={
                        'case_ref_id': case_ref_id,
                        'process_l1': l1.strip()
                    })

                if l2:
                    p2_query = """
                    MATCH (c:Case {case_ref_id: $case_ref_id})
                    MERGE (p:ProcessL2 {name: $process_l2})
                    MERGE (c)-[:HAS_PROCESS_L2]->(p)
                    """
                    graph.query(p2_query, params={
                        'case_ref_id': case_ref_id,
                        'process_l2': l2.strip()
                    })

                if l3:
                    p3_query = """
                    MATCH (c:Case {case_ref_id: $case_ref_id})
                    MERGE (p:ProcessL3 {name: $process_l3})
                    MERGE (c)-[:HAS_PROCESS_L3]->(p)
                    """
                    graph.query(p3_query, params={
                        'case_ref_id': case_ref_id,
                        'process_l3': l3.strip()
                    })

            # Create personal data categories (pipe-separated)
            pdc_str = case.get('personalDataCategory', case.get('personal_data_categories', ''))
            if isinstance(pdc_str, str):
                pdc_list = parse_pipe_separated(pdc_str)
            elif isinstance(pdc_str, list):
                pdc_list = pdc_str
            else:
                pdc_list = []

            for pdc in pdc_list:
                pdc_query = """
                MATCH (c:Case {case_ref_id: $case_ref_id})
                MERGE (pdc:PersonalDataCategory {name: $pdc_name})
                MERGE (c)-[:HAS_PERSONAL_DATA_CATEGORY]->(pdc)
                """
                graph.query(pdc_query, params={
                    'case_ref_id': case_ref_id,
                    'pdc_name': pdc.strip()
                })

            # Handle personal_data field if present
            pd_str = case.get('personalData', case.get('personal_data', ''))
            if isinstance(pd_str, str):
                pd_list = parse_pipe_separated(pd_str)
            elif isinstance(pd_str, list):
                pd_list = pd_str
            else:
                pd_list = []

            for pd in pd_list:
                pd_query = """
                MATCH (c:Case {case_ref_id: $case_ref_id})
                MERGE (pd:PersonalData {name: $pd_name})
                MERGE (c)-[:HAS_PERSONAL_DATA]->(pd)
                """
                graph.query(pd_query, params={
                    'case_ref_id': case_ref_id,
                    'pd_name': pd.strip()
                })

            success_count += 1
            logger.info(f"   ✓ {case_ref_id} loaded successfully")

        except Exception as e:
            error_count += 1
            logger.error(f"   ❌ Error loading {case_ref_id}: {e}")
            import traceback
            logger.error(f"   Traceback: {traceback.format_exc()}")

    # Summary
    logger.info("")
    logger.info("=" * 70)
    logger.info(f"✅ UPLOAD COMPLETE")
    logger.info(f"   Success: {success_count}/{len(cases)} cases")
    if error_count > 0:
        logger.info(f"   Errors:  {error_count}/{len(cases)} cases")
    logger.info("=" * 70)

    # Verify counts
    try:
        count_query = "MATCH (c:Case) RETURN count(c) as count"
        result = graph.query(count_query)
        total_cases = result.result_set[0][0] if result.result_set else 0
        logger.info(f"📊 Total cases in DataTransferGraph: {total_cases}")
    except Exception as e:
        logger.warning(f"⚠️  Could not verify case count: {e}")

    return success_count == len(cases)


def main():
    """Main entry point"""
    # Parse arguments
    json_file = 'sample_data.json'
    clear_graph = False

    if len(sys.argv) > 1:
        if sys.argv[1] == '--clear':
            clear_graph = True
        elif sys.argv[1].startswith('--'):
            logger.error(f"Unknown option: {sys.argv[1]}")
            logger.info("Usage: python falkor_upload_json.py [json_file] [--clear]")
            sys.exit(1)
        else:
            json_file = sys.argv[1]

    if len(sys.argv) > 2 and sys.argv[2] == '--clear':
        clear_graph = True

    logger.info("=" * 70)
    logger.info("FALKORDB JSON DATA UPLOAD")
    logger.info("=" * 70)
    logger.info(f"📂 File: {json_file}")
    logger.info(f"🗑️  Clear graph: {clear_graph}")
    logger.info("")

    success = load_json_to_graph(json_file, clear_graph)

    if success:
        logger.info("")
        logger.info("🎉 All cases loaded successfully!")
        sys.exit(0)
    else:
        logger.info("")
        logger.info("⚠️  Some cases failed to load. Check errors above.")
        sys.exit(1)


if __name__ == '__main__':
    main()
