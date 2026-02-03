#!/usr/bin/env python3
"""
Find any nodes with pipe separators in their names
"""

from falkordb import FalkorDB

db = FalkorDB(host='localhost', port=6379)
graph = db.select_graph('DataTransferGraph')

print("=" * 70)
print("SEARCHING FOR NODES WITH PIPE SEPARATORS (|)")
print("=" * 70)

node_types = [
    'Country',
    'Jurisdiction',
    'Purpose',
    'ProcessL1',
    'ProcessL2',
    'ProcessL3',
    'PersonalDataCategory',
    'PersonalData'
]

found_any = False

for node_type in node_types:
    query = f"MATCH (n:{node_type}) WHERE n.name CONTAINS '|' RETURN n.name"
    result = graph.query(query)

    if result.result_set and len(result.result_set) > 0:
        found_any = True
        print(f"\n❌ FOUND {len(result.result_set)} {node_type} nodes with pipes:")
        for row in result.result_set:
            print(f"   → {row[0]}")

if not found_any:
    print("\n✅ NO NODES WITH PIPE SEPARATORS FOUND")
    print("   All nodes have clean, individual values")

print("\n" + "=" * 70)
