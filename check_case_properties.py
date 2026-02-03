#!/usr/bin/env python3
"""
Check if Case nodes have any properties with pipe-separated values
"""

from falkordb import FalkorDB

db = FalkorDB(host='localhost', port=6379)
graph = db.select_graph('DataTransferGraph')

print("=" * 70)
print("CHECKING CASE NODE PROPERTIES")
print("=" * 70)

# Get a sample case with all its properties
query = """
MATCH (c:Case)
RETURN c
LIMIT 5
"""

result = graph.query(query)

print(f"\nFound {len(result.result_set)} sample cases")

for i, row in enumerate(result.result_set, 1):
    case_node = row[0]
    print(f"\n📦 Case {i}:")

    # The node is returned as a dict-like object
    if hasattr(case_node, 'properties'):
        props = case_node.properties
    else:
        props = case_node

    for key, value in props.items():
        has_pipe = '|' in str(value) if value else False
        marker = '❌' if has_pipe else '✓'
        print(f"   {marker} {key}: {value}")

print("\n" + "=" * 70)
