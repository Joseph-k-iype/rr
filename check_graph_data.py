#!/usr/bin/env python3
"""
Quick check of what's actually in the DataTransferGraph
"""

from falkordb import FalkorDB

db = FalkorDB(host='localhost', port=6379)
graph = db.select_graph('DataTransferGraph')

print("=" * 70)
print("CHECKING GRAPH DATA FOR PIPE-SEPARATED VALUES")
print("=" * 70)

# Check Country nodes
print("\n📍 COUNTRY NODES (first 10):")
result = graph.query("MATCH (c:Country) RETURN c.name LIMIT 10")
for row in result.result_set:
    name = row[0]
    has_pipe = '|' in name if name else False
    print(f"   {'❌' if has_pipe else '✓'} {name}")

# Check Jurisdiction nodes
print("\n🌍 JURISDICTION NODES (first 10):")
result = graph.query("MATCH (j:Jurisdiction) RETURN j.name LIMIT 10")
for row in result.result_set:
    name = row[0]
    has_pipe = '|' in name if name else False
    print(f"   {'❌' if has_pipe else '✓'} {name}")

# Check Purpose nodes
print("\n🎯 PURPOSE NODES (first 10):")
result = graph.query("MATCH (p:Purpose) RETURN p.name LIMIT 10")
for row in result.result_set:
    name = row[0]
    has_pipe = '|' in name if name else False
    print(f"   {'❌' if has_pipe else '✓'} {name}")

# Check ProcessL1 nodes
print("\n📊 PROCESS L1 NODES (first 10):")
result = graph.query("MATCH (p:ProcessL1) RETURN p.name LIMIT 10")
for row in result.result_set:
    name = row[0]
    has_pipe = '|' in name if name else False
    print(f"   {'❌' if has_pipe else '✓'} {name}")

# Check ProcessL2 nodes
print("\n📊 PROCESS L2 NODES (first 10):")
result = graph.query("MATCH (p:ProcessL2) RETURN p.name LIMIT 10")
for row in result.result_set:
    name = row[0]
    has_pipe = '|' in name if name else False
    print(f"   {'❌' if has_pipe else '✓'} {name}")

# Check ProcessL3 nodes
print("\n📊 PROCESS L3 NODES (first 10):")
result = graph.query("MATCH (p:ProcessL3) RETURN p.name LIMIT 10")
for row in result.result_set:
    name = row[0]
    has_pipe = '|' in name if name else False
    print(f"   {'❌' if has_pipe else '✓'} {name}")

# Check PersonalDataCategory nodes
print("\n🔒 PERSONAL DATA CATEGORY NODES (first 10):")
result = graph.query("MATCH (pdc:PersonalDataCategory) RETURN pdc.name LIMIT 10")
for row in result.result_set:
    name = row[0]
    has_pipe = '|' in name if name else False
    print(f"   {'❌' if has_pipe else '✓'} {name}")

# Count totals
print("\n📊 TOTAL COUNTS:")
counts = [
    ("Country", "MATCH (c:Country) RETURN count(c)"),
    ("Jurisdiction", "MATCH (j:Jurisdiction) RETURN count(j)"),
    ("Purpose", "MATCH (p:Purpose) RETURN count(p)"),
    ("ProcessL1", "MATCH (p:ProcessL1) RETURN count(p)"),
    ("ProcessL2", "MATCH (p:ProcessL2) RETURN count(p)"),
    ("ProcessL3", "MATCH (p:ProcessL3) RETURN count(p)"),
    ("PersonalDataCategory", "MATCH (pdc:PersonalDataCategory) RETURN count(pdc)")
]

for label, query in counts:
    result = graph.query(query)
    count = result.result_set[0][0] if result.result_set else 0
    print(f"   {label}: {count}")

print("\n" + "=" * 70)
print("❌ = Contains pipe separator |")
print("✓ = Clean single value")
print("=" * 70)
