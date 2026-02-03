#!/bin/bash

echo "======================================================================"
echo "PII STATISTICS VERIFICATION"
echo "======================================================================"

echo ""
echo "1️⃣  Checking graph data directly..."
python3 << 'EOF'
from falkordb import FalkorDB

db = FalkorDB(host='localhost', port=6379)
graph = db.select_graph('DataTransferGraph')

# Total cases
query = "MATCH (c:Case) RETURN count(c)"
result = graph.query(query)
total = result.result_set[0][0] if result.result_set else 0
print(f"   Total cases: {total}")

# Cases with PersonalDataCategory (any value)
query = """
MATCH (c:Case)-[:HAS_PERSONAL_DATA_CATEGORY]->(pdc:PersonalDataCategory)
RETURN count(DISTINCT c)
"""
result = graph.query(query)
with_pdc = result.result_set[0][0] if result.result_set else 0
print(f"   Cases with PersonalDataCategory: {with_pdc}")

# Cases with valid PII (excluding N/A, NA, null)
query = """
MATCH (c:Case)-[:HAS_PERSONAL_DATA_CATEGORY]->(pdc:PersonalDataCategory)
WHERE pdc.name <> 'N/A' AND pdc.name <> 'NA' AND pdc.name <> 'null'
RETURN count(DISTINCT c)
"""
result = graph.query(query)
with_pii = result.result_set[0][0] if result.result_set else 0
print(f"   Cases with valid PII: {with_pii}")
EOF

echo ""
echo "2️⃣  Checking API stats endpoint..."
API_RESPONSE=$(curl -s http://localhost:5001/api/stats)
echo "$API_RESPONSE" | python3 -c "import sys, json; data = json.load(sys.stdin); print(f\"   Total cases: {data['stats']['total_cases']}\"); print(f\"   Cases with PII: {data['stats']['cases_with_pii']}\")"

echo ""
echo "3️⃣  Expected vs Actual:"
echo "   ✅ Expected: 74 cases with PII"
ACTUAL=$(echo "$API_RESPONSE" | python3 -c "import sys, json; data = json.load(sys.stdin); print(data['stats']['cases_with_pii'])")
echo "   📊 Actual from API: $ACTUAL"

if [ "$ACTUAL" -eq "74" ]; then
    echo ""
    echo "======================================================================"
    echo "✅ SUCCESS: PII statistics are correct!"
    echo "======================================================================"
else
    echo ""
    echo "======================================================================"
    echo "⚠️  MISMATCH: API needs to be restarted"
    echo "======================================================================"
    echo ""
    echo "To fix:"
    echo "  1. Stop the API server (Ctrl+C if running in foreground)"
    echo "  2. Run: python3 api_fastapi_deontic.py"
    echo "  3. Rerun this script to verify"
fi
