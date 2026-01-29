# Correct FalkorDB/Redis Queries

## Issue Found
You were using `'CASE 00001'` (with space) but the correct format is `'CASE00001'` (no space).

## Correct Queries for Redis CLI

### 1. Query CASE00001 with all relationships
```cypher
GRAPH.QUERY DataTransferGraph "MATCH (c:Case {case_id: 'CASE00001'})-[r]-(neighbor) RETURN c, r, neighbor"
```

### 2. Query CASE00001 basic info
```cypher
GRAPH.QUERY DataTransferGraph "MATCH (c:Case {case_id: 'CASE00001'}) RETURN c"
```

### 3. Query CASE00001 with origin and receiving countries
```cypher
GRAPH.QUERY DataTransferGraph "MATCH (c:Case {case_id: 'CASE00001'})-[:ORIGINATES_FROM]->(origin:Country) MATCH (c)-[:TRANSFERS_TO]->(receiving:Jurisdiction) RETURN c.case_id, origin.name, collect(receiving.name) as receiving_countries"
```

### 4. Find all cases from Ireland to Poland
```cypher
GRAPH.QUERY DataTransferGraph "MATCH (c:Case)-[:ORIGINATES_FROM]->(origin:Country {name: 'Ireland'}) MATCH (c)-[:TRANSFERS_TO]->(receiving:Jurisdiction {name: 'Poland'}) RETURN c.case_id, origin.name, receiving.name"
```

### 5. Count cases by origin country
```cypher
GRAPH.QUERY DataTransferGraph "MATCH (c:Case)-[:ORIGINATES_FROM]->(origin:Country) RETURN origin.name, count(c) as total ORDER BY total DESC LIMIT 10"
```

### 6. List all case IDs
```cypher
GRAPH.QUERY DataTransferGraph "MATCH (c:Case) RETURN c.case_id ORDER BY c.case_id LIMIT 20"
```

### 7. Get full details of CASE00001
```cypher
GRAPH.QUERY DataTransferGraph "MATCH (c:Case {case_id: 'CASE00001'})-[:ORIGINATES_FROM]->(origin:Country) MATCH (c)-[:TRANSFERS_TO]->(receiving:Jurisdiction) OPTIONAL MATCH (c)-[:HAS_PERSONAL_DATA]->(pd:PersonalData) OPTIONAL MATCH (c)-[:HAS_PERSONAL_DATA_CATEGORY]->(pdc:PersonalDataCategory) OPTIONAL MATCH (c)-[:HAS_CATEGORY]->(cat:Category) RETURN c.case_id, c.eim_id, c.business_app_id, origin.name, collect(DISTINCT receiving.name) as receiving, c.purpose_level1, c.purpose_level2, c.purpose_level3, c.pia_module, collect(DISTINCT pd.name) as personal_data, collect(DISTINCT pdc.name) as pd_categories, collect(DISTINCT cat.name) as categories"
```

## Common Mistakes to Avoid

❌ **Wrong:** `'CASE 00001'` (with space)
✅ **Correct:** `'CASE00001'` (no space)

❌ **Wrong:** Missing quotes around case_id
✅ **Correct:** Always use quotes: `{case_id: 'CASE00001'}`

❌ **Wrong:** Wrong capitalization: `'case00001'`
✅ **Correct:** Use exact case: `'CASE00001'`

## Testing in Redis CLI

```bash
# Connect to Redis
redis-cli

# Switch to FalkorDB
# (already connected if you see 127.0.0.1:6379>)

# Run query (all on one line)
GRAPH.QUERY DataTransferGraph "MATCH (c:Case {case_id: 'CASE00001'})-[:ORIGINATES_FROM]->(origin:Country) MATCH (c)-[:TRANSFERS_TO]->(receiving:Jurisdiction) RETURN c.case_id, origin.name, receiving.name"
```

## Expected Output for CASE00001

```
1) 1) "c.case_id"
   2) "origin.name"
   3) "receiving.name"
2) 1) 1) "CASE00001"
      2) "Ireland"
      3) "Poland"
3) 1) "Cached execution: 0"
   2) "Query internal execution time: X.XXX milliseconds"
```

## Ireland → Poland Search

This should return 3 cases:

```bash
GRAPH.QUERY DataTransferGraph "MATCH (c:Case)-[:ORIGINATES_FROM]->(origin:Country {name: 'Ireland'}) MATCH (c)-[:TRANSFERS_TO]->(receiving:Jurisdiction {name: 'Poland'}) RETURN c.case_id, origin.name, receiving.name"
```

Expected result: CASE00001, CASE00044, CASE00046
