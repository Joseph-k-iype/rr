#!/usr/bin/env python3
"""
Create comprehensive indexes for large graph performance optimization
Supports 31k+ nodes and 1M+ edges
"""

from falkordb import FalkorDB
import logging

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

def create_all_indexes():
    """Create all necessary indexes for optimal query performance"""

    db = FalkorDB(host='localhost', port=6379)
    graph = db.select_graph('DataTransferGraph')

    logger.info("=" * 70)
    logger.info("CREATING GRAPH INDEXES FOR OPTIMAL PERFORMANCE")
    logger.info("=" * 70)

    # Comprehensive index list
    indexes = [
        # Case node indexes
        ("Case", "case_ref_id", "Case reference ID lookup"),
        ("Case", "case_id", "Case ID lookup"),
        ("Case", "eim_id", "EIM ID lookup"),
        ("Case", "app_id", "Application ID lookup"),
        ("Case", "case_status", "Case status filtering"),
        ("Case", "pia_status", "PIA status filtering"),
        ("Case", "tia_status", "TIA status filtering"),
        ("Case", "hrpr_status", "HRPR status filtering"),

        # Country and Jurisdiction indexes
        ("Country", "name", "Origin country lookup"),
        ("Jurisdiction", "name", "Receiving country lookup"),

        # Purpose indexes
        ("Purpose", "name", "Purpose lookup"),

        # Process hierarchy indexes
        ("ProcessL1", "name", "Process L1 lookup"),
        ("ProcessL2", "name", "Process L2 lookup"),
        ("ProcessL3", "name", "Process L3 lookup"),

        # Personal data indexes
        ("PersonalData", "name", "Personal data lookup"),
        ("PersonalDataCategory", "name", "Personal data category lookup"),
    ]

    created = 0
    already_exists = 0
    failed = 0

    for label, property_name, description in indexes:
        index_query = f"CREATE INDEX FOR (n:{label}) ON (n.{property_name})"
        try:
            graph.query(index_query)
            logger.info(f"✅ Created: {label}.{property_name} - {description}")
            created += 1
        except Exception as e:
            if "already indexed" in str(e).lower() or "already exists" in str(e).lower():
                logger.info(f"⏭️  Exists: {label}.{property_name} - {description}")
                already_exists += 1
            else:
                logger.error(f"❌ Failed: {label}.{property_name} - {e}")
                failed += 1

    logger.info("")
    logger.info("=" * 70)
    logger.info(f"INDEX CREATION SUMMARY")
    logger.info("=" * 70)
    logger.info(f"Created: {created}")
    logger.info(f"Already exists: {already_exists}")
    logger.info(f"Failed: {failed}")
    logger.info(f"Total: {len(indexes)}")
    logger.info("")

    # Show all indexes
    logger.info("Listing all indexes in DataTransferGraph:")
    try:
        # FalkorDB syntax for showing indexes
        result = graph.query("CALL db.indexes()")
        if result.result_set:
            logger.info(f"Total indexes: {len(result.result_set)}")
            for row in result.result_set:
                logger.info(f"  - {row}")
        else:
            logger.info("  (Index listing not supported in this FalkorDB version)")
    except Exception as e:
        logger.info(f"  (Could not list indexes: {e})")

    logger.info("")
    logger.info("=" * 70)
    logger.info("✅ INDEX OPTIMIZATION COMPLETE")
    logger.info("=" * 70)
    logger.info("")
    logger.info("Next steps:")
    logger.info("1. Restart API server to use optimized queries")
    logger.info("2. Test query performance with: python3 test_query_performance.py")
    logger.info("3. Monitor query times in API logs")

    return created + already_exists


if __name__ == '__main__':
    try:
        total = create_all_indexes()
        print(f"\n✅ Success: {total} indexes ready")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
