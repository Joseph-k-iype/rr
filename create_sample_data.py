#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Create Sample Data in DataTransferGraph

This script loads sample data from sample_data.json into the DataTransferGraph
for testing precedent-based validation.

Usage:
    python create_sample_data.py
"""

from falkordb import FalkorDB
import json
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def load_sample_data():
    """Load sample data into DataTransferGraph"""

    # Connect to FalkorDB
    db = FalkorDB(host='localhost', port=6379)
    graph = db.select_graph('DataTransferGraph')

    # Load sample data file
    sample_data_path = Path(__file__).parent / "sample_data.json"

    if not sample_data_path.exists():
        logger.error(f"Sample data file not found: {sample_data_path}")
        logger.info("Please create sample_data.json with case data")
        return

    # Load JSON with UTF-8 encoding
    with open(sample_data_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    logger.info(f"Loaded {len(data.get('cases', []))} cases from {sample_data_path}")

    # Clear existing data
    logger.info("Clearing existing DataTransferGraph...")
    try:
        graph.query("MATCH (n) DETACH DELETE n")
    except:
        pass

    # Create indexes
    logger.info("Creating indexes...")
    indexes = [
        "CREATE INDEX FOR (c:Case) ON (c.case_ref_id)",
        "CREATE INDEX FOR (ct:Country) ON (ct.name)",
        "CREATE INDEX FOR (j:Jurisdiction) ON (j.name)",
        "CREATE INDEX FOR (p:Purpose) ON (p.name)",
    ]

    for idx_query in indexes:
        try:
            graph.query(idx_query)
        except:
            pass

    # Load each case
    for i, case in enumerate(data.get('cases', []), 1):
        logger.info(f"Loading case {i}/{len(data['cases'])}: {case.get('case_ref_id')}")

        # Create Case node
        case_query = """
        CREATE (c:Case {
            case_ref_id: $case_ref_id,
            case_status: $case_status,
            app_id: $app_id,
            pia_status: $pia_status,
            tia_status: $tia_status,
            hrpr_status: $hrpr_status
        })
        """

        graph.query(case_query, params={
            'case_ref_id': case.get('case_ref_id'),
            'case_status': case.get('case_status', 'Active'),
            'app_id': case.get('app_id', ''),
            'pia_status': case.get('pia_status', 'N/A'),
            'tia_status': case.get('tia_status', 'N/A'),
            'hrpr_status': case.get('hrpr_status', 'N/A')
        })

        # Create origin country
        origin_query = """
        MATCH (c:Case {case_ref_id: $case_ref_id})
        MERGE (origin:Country {name: $origin_country})
        MERGE (c)-[:ORIGINATES_FROM]->(origin)
        """

        graph.query(origin_query, params={
            'case_ref_id': case.get('case_ref_id'),
            'origin_country': case.get('origin_country')
        })

        # Create receiving jurisdictions
        for receiving in case.get('receiving_countries', []):
            receiving_query = """
            MATCH (c:Case {case_ref_id: $case_ref_id})
            MERGE (j:Jurisdiction {name: $receiving})
            MERGE (c)-[:TRANSFERS_TO]->(j)
            """

            graph.query(receiving_query, params={
                'case_ref_id': case.get('case_ref_id'),
                'receiving': receiving
            })

        # Create purposes
        for purpose in case.get('purposes', []):
            purpose_query = """
            MATCH (c:Case {case_ref_id: $case_ref_id})
            MERGE (p:Purpose {name: $purpose})
            MERGE (c)-[:HAS_PURPOSE]->(p)
            """

            graph.query(purpose_query, params={
                'case_ref_id': case.get('case_ref_id'),
                'purpose': purpose
            })

    logger.info(f"✓ Successfully loaded {len(data.get('cases', []))} cases into DataTransferGraph")


if __name__ == '__main__':
    print("=" * 70)
    print("LOADING SAMPLE DATA INTO DATATRANSFERGRAPH")
    print("=" * 70)
    print()

    load_sample_data()

    print()
    print("=" * 70)
    print("✓ Sample data loaded successfully!")
    print("=" * 70)
