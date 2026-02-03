#!/bin/bash
# Verification script for dropdown functionality

echo "======================================================================"
echo "DROPDOWN VERIFICATION SCRIPT"
echo "======================================================================"
echo ""

# Check if API is running
echo "1️⃣  Checking if API is running..."
if curl -s http://localhost:5001/api/stats > /dev/null 2>&1; then
    echo "   ✅ API is running on port 5001"
else
    echo "   ❌ API is NOT running"
    echo "   Please start the API with: python3 api_fastapi_deontic.py"
    exit 1
fi

echo ""
echo "2️⃣  Checking graph data for pipe separators..."
python3 find_pipe_nodes.py

echo ""
echo "3️⃣  Testing API endpoint response..."
echo "   Fetching dropdown values from API..."

RESPONSE=$(curl -s http://localhost:5001/api/all-dropdown-values)

# Check if response is valid JSON
if ! echo "$RESPONSE" | python3 -m json.tool > /dev/null 2>&1; then
    echo "   ❌ API returned invalid JSON"
    exit 1
fi

# Check for success
if echo "$RESPONSE" | python3 -c "import sys, json; data = json.load(sys.stdin); sys.exit(0 if data.get('success') else 1)"; then
    echo "   ✅ API returned success: true"
else
    echo "   ❌ API returned success: false"
    exit 1
fi

# Count items
echo ""
echo "4️⃣  Counting dropdown items..."
echo "$RESPONSE" | python3 -c '
import sys
import json

data = json.load(sys.stdin)

print("   ✅ Countries:", len(data.get("countries", [])))
print("   ✅ Origin Countries:", len(data.get("origin_countries", [])))
print("   ✅ Receiving Countries:", len(data.get("receiving_countries", [])))
print("   ✅ Purposes:", len(data.get("purposes", [])))
print("   ✅ Process L1:", len(data.get("process_l1", [])))
print("   ✅ Process L2:", len(data.get("process_l2", [])))
print("   ✅ Process L3:", len(data.get("process_l3", [])))

if "personal_data_categories" in data:
    print("   ✅ Personal Data Categories:", len(data.get("personal_data_categories", [])))
else:
    print("   ⚠️  Personal Data Categories: NOT IN RESPONSE (need to restart API)")
'

# Check for pipe separators in response
echo ""
echo "5️⃣  Checking API response for pipe separators..."
if echo "$RESPONSE" | grep -q '|'; then
    echo "   ❌ FOUND PIPE SEPARATORS IN API RESPONSE"
    echo "   This should NOT happen. Showing examples:"
    echo "$RESPONSE" | python3 -c '
import sys
import json
import itertools

data = json.load(sys.stdin)
all_values = list(itertools.chain(*[v for k, v in data.items() if isinstance(v, list)]))
pipes = [v for v in all_values if "|" in str(v)]
for p in pipes[:10]:
    print(f"      • {p}")
'
else
    echo "   ✅ NO PIPE SEPARATORS FOUND IN API RESPONSE"
fi

echo ""
echo "======================================================================"
echo "6️⃣  NEXT STEPS:"
echo "======================================================================"
echo ""
echo "1. If 'Personal Data Categories: NOT IN RESPONSE' above:"
echo "   → Restart the API server to apply the fix"
echo "   → Run: python3 api_fastapi_deontic.py"
echo ""
echo "2. Open the test page to verify dropdowns:"
echo "   → open test_dropdowns.html"
echo "   → Or visit: file://$(pwd)/test_dropdowns.html"
echo ""
echo "3. Clear browser cache and reload the main dashboard:"
echo "   → http://localhost:5001/"
echo ""
echo "======================================================================"
echo "✅ Verification complete"
echo "======================================================================"
