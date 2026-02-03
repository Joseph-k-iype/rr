"""
Query Optimization Patterns for Large Graphs (31k+ nodes, 1M+ edges)

Key optimizations:
1. Query timeouts to prevent hanging
2. Early filtering with WHERE clauses
3. Reduced COLLECT operations
4. Proper index usage
5. Efficient query patterns
"""

# ============================================================================
# CONFIGURATION
# ============================================================================

# Query timeout in milliseconds
# For large graphs: 30 seconds should be sufficient for most queries
QUERY_TIMEOUT_MS = 30000  # 30 seconds

# For very large result sets, limit to prevent memory issues
MAX_RESULTS = 5000

# ============================================================================
# OPTIMIZED QUERY PATTERNS
# ============================================================================

# Pattern 1: Stats Query (Optimized)
# BEFORE: Multiple OPTIONAL MATCH with COLLECT
# AFTER: Direct count with indexed lookup
OPTIMIZED_STATS_QUERIES = {
    'total_cases': """
        MATCH (c:Case)
        RETURN count(c) as count
    """,

    'total_countries': """
        MATCH (c:Country)
        RETURN count(c) as count
    """,

    'total_jurisdictions': """
        MATCH (j:Jurisdiction)
        RETURN count(j) as count
    """,

    'cases_with_pii': """
        MATCH (c:Case)-[:HAS_PERSONAL_DATA_CATEGORY]->(pdc:PersonalDataCategory)
        WHERE pdc.name <> 'N/A' AND pdc.name <> 'NA' AND pdc.name <> 'null'
        RETURN count(DISTINCT c) as count
    """
}

# Pattern 2: Search Query (Optimized for large graphs)
# Key optimizations:
# - Use indexed properties in WHERE clause
# - Filter early with WHERE before COLLECT
# - Limit COLLECT operations
# - Use timeout parameter

OPTIMIZED_SEARCH_TEMPLATE = """
    // Step 1: Filter cases by indexed country properties (FAST)
    MATCH (c:Case)-[:ORIGINATES_FROM]->(origin:Country)
    MATCH (c)-[:TRANSFERS_TO]->(receiving:Jurisdiction)
    WHERE {where_conditions}

    // Step 2: Additional filters (before expensive operations)
    {additional_filters}

    // Step 3: Collect minimal required data (limit collection size)
    WITH c, origin.name as origin_country LIMIT {max_results}

    // Step 4: Get related data only for filtered cases
    MATCH (c)-[:TRANSFERS_TO]->(recv:Jurisdiction)
    WITH c, origin_country, collect(DISTINCT recv.name) as receiving_countries

    OPTIONAL MATCH (c)-[:HAS_PURPOSE]->(purpose:Purpose)
    WITH c, origin_country, receiving_countries, collect(DISTINCT purpose.name) as purposes

    OPTIONAL MATCH (c)-[:HAS_PROCESS_L1]->(p1:ProcessL1)
    OPTIONAL MATCH (c)-[:HAS_PROCESS_L2]->(p2:ProcessL2)
    OPTIONAL MATCH (c)-[:HAS_PROCESS_L3]->(p3:ProcessL3)
    WITH c, origin_country, receiving_countries, purposes,
         p1.name as process_l1, p2.name as process_l2, p3.name as process_l3

    OPTIONAL MATCH (c)-[:HAS_PERSONAL_DATA_CATEGORY]->(pdc:PersonalDataCategory)
    WITH c, origin_country, receiving_countries, purposes,
         process_l1, process_l2, process_l3,
         collect(DISTINCT pdc.name) as pdc_items

    RETURN c.case_ref_id as case_id,
           c.eim_id as eim_id,
           c.app_id as app_id,
           origin_country,
           receiving_countries,
           purposes,
           process_l1,
           process_l2,
           process_l3,
           c.pia_status as pia_status,
           c.tia_status as tia_status,
           c.hrpr_status as hrpr_status,
           pdc_items,
           c.case_status as case_status
    ORDER BY case_id
"""

# Pattern 3: Precedent Search (Strict matching for compliance)
# Optimized for exact matches using indexes

OPTIMIZED_PRECEDENT_TEMPLATE = """
    // Step 1: Exact match on indexed properties (FAST)
    MATCH (c:Case)-[:ORIGINATES_FROM]->(origin:Country {{name: $origin}})
    MATCH (c)-[:TRANSFERS_TO]->(receiving:Jurisdiction {{name: $receiving}})

    // Step 2: Filter by case status early (indexed)
    WHERE c.case_status IS NOT NULL

    // Step 3: Apply additional strict filters
    {strict_filters}

    // Step 4: Collect minimal data for matched cases
    WITH c LIMIT {max_results}

    MATCH (c)-[:TRANSFERS_TO]->(recv:Jurisdiction)
    WITH c, collect(DISTINCT recv.name) as receiving_countries

    OPTIONAL MATCH (c)-[:HAS_PURPOSE]->(purpose:Purpose)
    WITH c, receiving_countries, collect(DISTINCT purpose.name) as purposes

    OPTIONAL MATCH (c)-[:HAS_PROCESS_L1]->(p1:ProcessL1)
    OPTIONAL MATCH (c)-[:HAS_PROCESS_L2]->(p2:ProcessL2)
    OPTIONAL MATCH (c)-[:HAS_PROCESS_L3]->(p3:ProcessL3)
    WITH c, receiving_countries, purposes,
         p1.name as process_l1, p2.name as process_l2, p3.name as process_l3

    OPTIONAL MATCH (c)-[:HAS_PERSONAL_DATA_CATEGORY]->(pdc:PersonalDataCategory)
    WITH c, receiving_countries, purposes,
         process_l1, process_l2, process_l3,
         collect(DISTINCT pdc.name) as pdc_items

    RETURN c.case_ref_id as case_id,
           c.origin_country as origin_country,
           receiving_countries,
           purposes,
           process_l1,
           process_l2,
           process_l3,
           c.pia_status as pia_status,
           c.tia_status as tia_status,
           c.hrpr_status as hrpr_status,
           pdc_items,
           c.case_status as case_status
    ORDER BY case_id
"""

# ============================================================================
# QUERY EXECUTION HELPER
# ============================================================================

def execute_with_timeout(graph, query, params=None, timeout_ms=QUERY_TIMEOUT_MS):
    """
    Execute query with timeout to prevent hanging on large graphs

    Args:
        graph: FalkorDB graph instance
        query: Cypher query string
        params: Query parameters dict
        timeout_ms: Timeout in milliseconds (default 30 seconds)

    Returns:
        Query result

    Raises:
        TimeoutError: If query exceeds timeout
        Exception: For other query errors
    """
    import logging
    logger = logging.getLogger(__name__)

    try:
        # Execute with timeout
        logger.info(f"Executing query with {timeout_ms}ms timeout")
        result = graph.query(query, params=params or {}, timeout=timeout_ms)
        return result

    except Exception as e:
        error_msg = str(e).lower()
        if 'timeout' in error_msg or 'timed out' in error_msg:
            logger.error(f"Query timeout after {timeout_ms}ms - graph may be too large")
            logger.error(f"Consider: 1) Adding more indexes, 2) Increasing timeout, 3) Optimizing query")
            raise TimeoutError(f"Query exceeded {timeout_ms}ms timeout") from e
        else:
            logger.error(f"Query error: {e}")
            raise

# ============================================================================
# OPTIMIZATION TIPS
# ============================================================================

OPTIMIZATION_TIPS = """
For graphs with 31k+ nodes and 1M+ edges:

1. INDEXES (Critical)
   - Create indexes on all frequently queried properties
   - Run: python3 optimize_graph_indexes.py

2. QUERY PATTERNS
   - Use exact match (=) instead of CONTAINS when possible
   - Filter early with WHERE clauses
   - Limit COLLECT operations
   - Use WITH clauses to reduce data before collections

3. TIMEOUTS
   - Default: 30 seconds (30000ms)
   - Adjust based on graph size and query complexity
   - Set in graph.query(timeout=ms)

4. RESULT LIMITS
   - Use LIMIT to cap result sizes
   - Implement pagination for large result sets
   - Default limit: 5000 results

5. MONITORING
   - Log query execution times
   - Identify slow queries
   - Optimize based on actual performance

6. AVOID
   - Collecting large arrays without filters
   - Multiple nested OPTIONAL MATCH without filtering
   - Full graph scans (MATCH (n) without WHERE)
   - Creating relationships in queries (use separate writes)

Example optimized query:
   MATCH (c:Case)-[:ORIGINATES_FROM]->(origin:Country {name: $origin})
   WHERE c.case_status = 'Completed'  // Filter early
   WITH c LIMIT 5000                  // Cap results
   MATCH (c)-[:TRANSFERS_TO]->(j:Jurisdiction)
   RETURN c, collect(j.name)          // Collect only needed data
"""

if __name__ == '__main__':
    print(OPTIMIZATION_TIPS)
