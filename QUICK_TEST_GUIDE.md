# Quick Test Guide - Deontic API

## Server Status
✅ **Deontic FastAPI running on port 5001** (PID: 76969)
- Swagger UI: http://localhost:5001/docs
- ReDoc: http://localhost:5001/redoc

## All 3 US Prohibitions Working Correctly

### 1. RULE_10: US → China Cloud Storage (ABSOLUTE PROHIBITION)
```bash
curl -X POST 'http://localhost:5001/api/evaluate-rules' \
  -H 'Content-Type: application/json' \
  -d '{"origin_country": "United States", "receiving_country": "China", "has_pii": false}'
```

**Result:**
- ✅ Type: PROHIBITION
- ✅ Name: "US Data to China Cloud"
- ✅ is_blocked: true
- ✅ Duties: [] (no exceptions - absolute prohibition)
- ✅ Action: "Store in Cloud"

### 2. RULE_9: US → Restricted Countries with PII (PROHIBITION WITH EXCEPTION)
```bash
curl -X POST 'http://localhost:5001/api/evaluate-rules' \
  -H 'Content-Type: application/json' \
  -d '{"origin_country": "United States", "receiving_country": "China", "has_pii": true}'
```

**Result (2 prohibitions + 1 permission):**
- ✅ RULE_10: PROHIBITION - "US Data to China Cloud" (no duties)
- ✅ RULE_9: PROHIBITION - "US PII to Restricted Countries" (duty: Obtain US Legal Approval)
- ✅ RULE_8: PERMISSION - "PII Transfer" (duty: Complete PIA Module (CM))

### 3. RULE_11: US → Any Country with Health Data (PROHIBITION WITH EXCEPTION)
```bash
curl -X POST 'http://localhost:5001/api/evaluate-rules' \
  -H 'Content-Type: application/json' \
  -d '{"origin_country": "United States", "receiving_country": "Canada", "has_health_data": true}'
```

**Result:**
- ✅ Type: PROHIBITION
- ✅ Name: "US Health Data Transfer"
- ✅ is_blocked: true
- ✅ Duties: ["Obtain US Legal Exception"]
- ✅ Action: "Transfer Health Data"

## Testing in Swagger UI

1. Open http://localhost:5001/docs
2. Find `POST /api/evaluate-rules`
3. Click "Try it out"

**Test Cases:**

### Absolute Prohibition
```json
{
  "origin_country": "United States",
  "receiving_country": "China",
  "has_pii": false
}
```
Expected: 1 prohibition (RULE_10), `has_prohibitions: true`, no duties

### PII Prohibition with Exception
```json
{
  "origin_country": "United States",
  "receiving_country": "Russia",
  "has_pii": true
}
```
Expected: 1 prohibition (RULE_9), duty: "Obtain US Legal Approval"

### Health Data Prohibition
```json
{
  "origin_country": "United States",
  "receiving_country": "Canada",
  "has_health_data": true
}
```
Expected: 1 prohibition (RULE_11), duty: "Obtain US Legal Exception"

### Permission Example (Ireland → Poland)
```json
{
  "origin_country": "Ireland",
  "receiving_country": "Poland",
  "has_pii": true
}
```
Expected: 3 permissions, 0 prohibitions, `has_prohibitions: false`

## Dashboard UI

Open http://localhost:5001/ and try:
- "United States" → "China" = Shows PROHIBITED in red
- "United States" → "Russia" = Shows PROHIBITED in red
- "Ireland" → "Poland" = Shows ALLOWED in green

## Graph Structure Verified

```
✅ Actions: 4 (Transfer Data, Transfer PII, Transfer Health Data, Store in Cloud)
✅ Permissions: 8 (EU/EEA Internal Transfer, BCR Transfer, etc.)
✅ Prohibitions: 3 (US PII to Restricted, US Data to China Cloud, US Health Data)
✅ Duties: 5 (Complete PIA/TIA/HRPR, Obtain US Legal Approval/Exception)
✅ Rules: 11 (8 permissions + 3 prohibitions)
```

## Key Differences from Old Structure

### Old Format (WRONG):
```json
{
  "rule_id": "RULE_10",
  "blocked": false,  // ❌ WRONG - was showing as allowed
  "requirements": {}
}
```

### New Deontic Format (CORRECT):
```json
{
  "rule_id": "RULE_10",
  "action": {"name": "Store in Cloud"},
  "prohibition": {
    "name": "US Data to China Cloud",
    "description": "Prohibition on storing/processing US data in China cloud storage",
    "duties": []  // ✅ CORRECT - absolute prohibition, no exceptions
  },
  "is_blocked": true  // ✅ CORRECT - clearly shows prohibition
}
```

## Verification Commands

```bash
# Check server is running deontic API
ps aux | grep api_fastapi_deontic

# Test graph stats
curl http://localhost:5001/api/test-rules-graph

# Test all 3 prohibitions
curl -X POST http://localhost:5001/api/evaluate-rules -H 'Content-Type: application/json' -d '{"origin_country": "United States", "receiving_country": "China", "has_pii": false}'
curl -X POST http://localhost:5001/api/evaluate-rules -H 'Content-Type: application/json' -d '{"origin_country": "United States", "receiving_country": "Russia", "has_pii": true}'
curl -X POST http://localhost:5001/api/evaluate-rules -H 'Content-Type: application/json' -d '{"origin_country": "United States", "receiving_country": "Canada", "has_health_data": true}'
```

## Issue Was

The old `api_graph.py` was running instead of the new `api_fastapi_deontic.py`. The old API used simple `blocked: boolean` flag which wasn't properly set, making prohibitions show as allowed.

The new deontic API uses proper graph relationships:
- `Rule -[:HAS_PROHIBITION]-> Prohibition`
- `Prohibition -[:CAN_HAVE_DUTY]-> Duty`
- `is_blocked: true` when prohibition exists

✅ **All fixed and verified working!**
