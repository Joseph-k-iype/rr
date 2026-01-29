# FastAPI Compliance Dashboard - Quick Start Guide

## What's New

### 1. **FastAPI with Swagger UI & ReDoc**
- Full OpenAPI documentation at **http://localhost:5001/docs** (Swagger UI)
- Alternative docs at **http://localhost:5001/redoc** (ReDoc)
- Interactive API testing directly from the browser

### 2. **Dynamic Dashboard**
- Search updates **automatically** as you change any filter
- No need to click "Search Cases" button (but it's still there for manual trigger)
- 500ms debounce prevents too many API calls
- Results clear automatically when criteria are incomplete

## Server Status

✅ **FastAPI Server Running** on port 5001 (PID: 71220)
- Main Dashboard: http://localhost:5001/
- Swagger UI: http://localhost:5001/docs
- ReDoc: http://localhost:5001/redoc

## Testing the API

### Using Swagger UI (Recommended)

1. Open http://localhost:5001/docs in your browser
2. You'll see all endpoints organized by tags:
   - **Metadata**: Get purposes, processes, countries, stats
   - **Compliance**: Evaluate rules
   - **Cases**: Search cases
   - **Testing**: Test RulesGraph

3. Click on any endpoint to expand it
4. Click "Try it out" button
5. Fill in parameters
6. Click "Execute"
7. View the response

### Using curl

#### Get all purposes (35 total)
```bash
curl http://localhost:5001/api/purposes
```

#### Get all process levels
```bash
curl http://localhost:5001/api/processes
```

#### Get countries
```bash
curl http://localhost:5001/api/countries
```

#### Get dashboard stats
```bash
curl http://localhost:5001/api/stats
```

#### Evaluate compliance rules (Ireland → Poland)
```bash
curl -X POST 'http://localhost:5001/api/evaluate-rules' \
  -H 'Content-Type: application/json' \
  -d '{
    "origin_country": "Ireland",
    "receiving_country": "Poland",
    "has_pii": true
  }'
```

Expected response: 3 rules triggered with requirements for pia_module and hrpr_module

#### Search cases (Ireland → Poland)
```bash
curl -X POST 'http://localhost:5001/api/search-cases' \
  -H 'Content-Type: application/json' \
  -d '{
    "origin_country": "Ireland",
    "receiving_country": "Poland"
  }'
```

#### Search with filters
```bash
curl -X POST 'http://localhost:5001/api/search-cases' \
  -H 'Content-Type: application/json' \
  -d '{
    "origin_country": "Ireland",
    "receiving_country": "Poland",
    "purposes": ["Compliance with Laws and Regulations"],
    "process_l1": "Back Office",
    "has_pii": "yes"
  }'
```

## Dashboard Features

### Dynamic Filtering
1. **Open**: http://localhost:5001/
2. **Type** origin country (e.g., "Ireland")
3. **Type** receiving country (e.g., "Poland")
4. **Results appear automatically** after 500ms

### Filter Options
- **Origin/Receiving Country**: Text input with autocomplete
- **Legal Purposes**: Multi-select dropdown (35 options)
- **Process L1/L2/L3**: Single-select dropdowns
  - L1: 5 areas (Back Office, Front Office, etc.)
  - L2: 14 functions (HR, Finance, etc.)
  - L3: 22 details (Payroll, AP, etc.)
- **Has PII**: Yes/No/Any

### What You'll See
1. **Triggered Rules Section**: Shows all compliance rules that apply
   - Rule ID, Description, Priority, Requirements
2. **Matching Cases Section**: Shows all cases matching your filters
   - Case details, purposes, process hierarchy, module values

## API Endpoints

### GET Endpoints
- `GET /api/purposes` - Get all legal processing purposes
- `GET /api/processes` - Get process L1/L2/L3 options
- `GET /api/countries` - Get all countries
- `GET /api/stats` - Get dashboard statistics
- `GET /api/test-rules-graph` - Test RulesGraph connectivity

### POST Endpoints
- `POST /api/evaluate-rules` - Evaluate which rules are triggered
- `POST /api/search-cases` - Search for matching cases

## Example Workflow

### Using Swagger UI
1. Go to http://localhost:5001/docs
2. Find **POST /api/evaluate-rules**
3. Click "Try it out"
4. Enter:
   ```json
   {
     "origin_country": "Ireland",
     "receiving_country": "Poland",
     "has_pii": true
   }
   ```
5. Click "Execute"
6. You'll see: 3 rules triggered
7. Now try **POST /api/search-cases** with same countries
8. You'll see: 1 case matching (CASE00018)

### Using Dashboard
1. Go to http://localhost:5001/
2. Type "Ireland" in Origin Country
3. Type "Poland" in Receiving Country
4. **Wait 500ms** - results appear automatically!
5. See 3 triggered rules
6. See 1 matching case
7. Try adding filters (purposes, processes, PII)
8. Results update automatically

## Core Logic Preserved

All business logic remains **unchanged**:
- ✅ RulesGraph queries for rule evaluation
- ✅ DataTransferGraph queries for case search
- ✅ Purpose nodes with multiple edges
- ✅ Process hierarchy (L1-L2-L3)
- ✅ No requirements filtering on cases (all cases shown)
- ✅ Same Cypher queries, same graph structure

Only changes:
- Flask → FastAPI (for Swagger UI)
- Manual search → Dynamic search (with debounce)
- Better logging and error handling

## Stopping/Starting Server

### Stop
```bash
# Find the process
ps aux | grep api_fastapi.py

# Kill it
kill <PID>
```

### Start
```bash
cd "/Users/josephkiype/Desktop/development/code/deterministic policy"
python3 api_fastapi.py
```

Or run in background:
```bash
python3 api_fastapi.py > fastapi.log 2>&1 &
```

## Data Verification

Current data loaded:
- **Cases**: 350
- **Countries**: 24
- **Jurisdictions**: 29
- **Cases with PII**: 227
- **Purposes**: 35
- **Process L1**: 5
- **Process L2**: 14
- **Process L3**: 22
- **Rules**: 8 (in RulesGraph)

## Next Steps

1. **Test in Swagger UI**: http://localhost:5001/docs
2. **Test Dynamic Dashboard**: http://localhost:5001/
3. **Try Ireland → Poland** (should show 3 rules, 1 case)
4. **Add filters** and see results update automatically
5. **Explore all API endpoints** in Swagger UI

## Troubleshooting

### Dropdowns still empty?
1. Hard refresh: Cmd+Shift+R (Mac) or Ctrl+Shift+R (Windows)
2. Open console (F12) and check for errors
3. Verify API endpoints: http://localhost:5001/api/purposes

### Server not responding?
```bash
# Check if server is running
lsof -i :5001

# Check logs
tail -f fastapi.log
```

### Graph not found?
```bash
# Test RulesGraph
curl http://localhost:5001/api/test-rules-graph

# If empty, rebuild
python3 build_rules_graph.py
```
