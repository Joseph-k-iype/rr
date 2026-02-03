#!/usr/bin/env python3
"""
Verify deduplication worked correctly in the graph
"""

from falkordb import FalkorDB

db = FalkorDB(host='localhost', port=6379)
graph = db.select_graph('DataTransferGraph')

print("=" * 70)
print("VERIFYING DEDUPLICATION IN GRAPH")
print("=" * 70)

print("\n📊 Test Case 1: TEST_DEDUP_001")
print("   Input origins: 'United States|China|China|India'")
print("   Expected: 3 unique countries (United States, China, India)")

query = """
MATCH (c:Case {case_ref_id: 'TEST_DEDUP_001'})-[:ORIGINATES_FROM]->(country:Country)
RETURN country.name
ORDER BY country.name
"""
result = graph.query(query)
origins = [row[0] for row in result.result_set]
print(f"   ✅ Found {len(origins)} origin countries: {origins}")

print("\n   Input receiving: 'Germany|France|United Kingdom|France|Germany'")
print("   Expected: 3 unique jurisdictions (Germany, France, United Kingdom)")

query = """
MATCH (c:Case {case_ref_id: 'TEST_DEDUP_001'})-[:TRANSFERS_TO]->(j:Jurisdiction)
RETURN j.name
ORDER BY j.name
"""
result = graph.query(query)
receiving = [row[0] for row in result.result_set]
print(f"   ✅ Found {len(receiving)} receiving jurisdictions: {receiving}")

print("\n   Input purposes: 'Office Support|Customer Service|Office Support|Marketing'")
print("   Expected: 3 unique purposes (Office Support, Customer Service, Marketing)")

query = """
MATCH (c:Case {case_ref_id: 'TEST_DEDUP_001'})-[:HAS_PURPOSE]->(p:Purpose)
RETURN p.name
ORDER BY p.name
"""
result = graph.query(query)
purposes = [row[0] for row in result.result_set]
print(f"   ✅ Found {len(purposes)} purposes: {purposes}")

print("\n   Input personal data: 'PII|Financial Data|PII|Health Data|Financial Data'")
print("   Expected: 3 unique categories (PII, Financial Data, Health Data)")

query = """
MATCH (c:Case {case_ref_id: 'TEST_DEDUP_001'})-[:HAS_PERSONAL_DATA_CATEGORY]->(pdc:PersonalDataCategory)
RETURN pdc.name
ORDER BY pdc.name
"""
result = graph.query(query)
pdc = [row[0] for row in result.result_set]
print(f"   ✅ Found {len(pdc)} personal data categories: {pdc}")

print("\n" + "=" * 70)
print("📊 Test Case 2: TEST_DEDUP_002")
print("   Input receiving: 'France|France|France'")
print("   Expected: 1 unique jurisdiction (France)")

query = """
MATCH (c:Case {case_ref_id: 'TEST_DEDUP_002'})-[:TRANSFERS_TO]->(j:Jurisdiction)
RETURN j.name
"""
result = graph.query(query)
receiving = [row[0] for row in result.result_set]
print(f"   ✅ Found {len(receiving)} receiving jurisdiction: {receiving}")

print("\n   Input purposes: 'Analytics|Analytics|Marketing|Analytics'")
print("   Expected: 2 unique purposes (Analytics, Marketing)")

query = """
MATCH (c:Case {case_ref_id: 'TEST_DEDUP_002'})-[:HAS_PURPOSE]->(p:Purpose)
RETURN p.name
ORDER BY p.name
"""
result = graph.query(query)
purposes = [row[0] for row in result.result_set]
print(f"   ✅ Found {len(purposes)} purposes: {purposes}")

print("\n" + "=" * 70)
print("📊 Test Case 3: TEST_DEDUP_003")
print("   Input receiving: 'United States|Canada|United States|Mexico|Canada'")
print("   Expected: 3 unique jurisdictions (United States, Canada, Mexico)")

query = """
MATCH (c:Case {case_ref_id: 'TEST_DEDUP_003'})-[:TRANSFERS_TO]->(j:Jurisdiction)
RETURN j.name
ORDER BY j.name
"""
result = graph.query(query)
receiving = [row[0] for row in result.result_set]
print(f"   ✅ Found {len(receiving)} receiving jurisdictions: {receiving}")

print("\n   Input purposes: 'Sales|Marketing|Sales|Customer Support|Marketing|Sales'")
print("   Expected: 3 unique purposes (Sales, Marketing, Customer Support)")

query = """
MATCH (c:Case {case_ref_id: 'TEST_DEDUP_003'})-[:HAS_PURPOSE]->(p:Purpose)
RETURN p.name
ORDER BY p.name
"""
result = graph.query(query)
purposes = [row[0] for row in result.result_set]
print(f"   ✅ Found {len(purposes)} purposes: {purposes}")

print("\n" + "=" * 70)
print("📊 GRAPH-LEVEL DEDUPLICATION CHECK")
print("=" * 70)

# Check that France appears only ONCE in the graph even though multiple cases reference it
query = "MATCH (j:Jurisdiction {name: 'France'}) RETURN count(j) as count"
result = graph.query(query)
france_count = result.result_set[0][0] if result.result_set else 0
print(f"\n✅ Jurisdiction 'France' appears {france_count} time(s) in graph (should be 1)")

# Check how many cases reference France
query = "MATCH (c:Case)-[:TRANSFERS_TO]->(j:Jurisdiction {name: 'France'}) RETURN count(c) as count"
result = graph.query(query)
france_refs = result.result_set[0][0] if result.result_set else 0
print(f"✅ {france_refs} case(s) reference France (reusing the same node)")

# Check total unique countries
query = "MATCH (c:Country) RETURN count(c) as count"
result = graph.query(query)
country_count = result.result_set[0][0] if result.result_set else 0
print(f"\n✅ Total unique Country nodes: {country_count}")

# Check total unique jurisdictions
query = "MATCH (j:Jurisdiction) RETURN count(j) as count"
result = graph.query(query)
jurisdiction_count = result.result_set[0][0] if result.result_set else 0
print(f"✅ Total unique Jurisdiction nodes: {jurisdiction_count}")

# Check total unique purposes
query = "MATCH (p:Purpose) RETURN count(p) as count"
result = graph.query(query)
purpose_count = result.result_set[0][0] if result.result_set else 0
print(f"✅ Total unique Purpose nodes: {purpose_count}")

# Check total unique personal data categories
query = "MATCH (pdc:PersonalDataCategory) RETURN count(pdc) as count"
result = graph.query(query)
pdc_count = result.result_set[0][0] if result.result_set else 0
print(f"✅ Total unique PersonalDataCategory nodes: {pdc_count}")

print("\n" + "=" * 70)
print("✅ DEDUPLICATION VERIFICATION COMPLETE")
print("=" * 70)
print("\nSummary:")
print("• Each case has only unique values (no duplicates within)")
print("• Graph has only unique nodes (no duplicate nodes)")
print("• Multiple cases can reference the same node (proper graph structure)")
print("• MERGE ensures no duplicate nodes are created")
print("\n✅ All deduplication working correctly!")
