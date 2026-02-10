# Data Transfer Compliance System

A **graph-driven, self-serviceable, and scalable** compliance engine for evaluating cross-border data transfers using formal deontic logic (Permissions, Prohibitions, Duties) with FalkorDB.

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FalkorDB](https://img.shields.io/badge/database-FalkorDB-red.svg)](https://www.falkordb.com/)
[![FastAPI](https://img.shields.io/badge/API-FastAPI-009688.svg)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/frontend-React-61dafb.svg)](https://react.dev/)

---

## Overview

This system evaluates data transfer compliance by:
- **Graph-based rules**: All logic stored in FalkorDB as nodes and relationships
- **Case-matching evaluation**: 8 rules covering all transfer corridors (EU, UK, BCR, etc.)
- **Precedent-based validation**: Checks historical cases for compliance patterns
- **Data dictionaries**: 200+ industry-standard entries for processes, purposes, data subjects, and global data categories
- **Admin panel**: React Flow visualization with CRUD operations on all graph entities
- **Wizard**: Step-by-step rule creation with optional dictionary selectors

---

## Architecture

### System Components

```
                  +------------------+
                  |  React Frontend  |
                  |  (Vite + React)  |
                  +--------+---------+
                           |
                  +--------v---------+
                  |   FastAPI Backend |
                  |   /api/evaluate   |
                  |   /api/admin      |
                  +--+-----+------+--+
                     |     |      |
              +------+  +--+--+  +------+
              |         |     |         |
     +--------v--+  +---v---+ +--------v--------+
     | RulesGraph|  | Data  | | Data Dictionaries|
     | (FalkorDB)|  | Graph | | (JSON files)     |
     +-----------+  +-------+ +-----------------+
```

### Data Flow

```
User Request
  -> FastAPI receives evaluation request (origin, receiving, pii, purposes, etc.)
  -> Phase 1: Query RulesGraph for applicable case-matching rules
  -> Phase 2: Search DataTransferGraph for precedent cases
  -> Phase 3: Determine final status (ALLOWED / PROHIBITED / REQUIRES_REVIEW)
  -> Return response with triggered rules, precedent evidence, assessment compliance
```

---

## Rules

The system uses **8 case-matching rules** that cover all transfer corridors. Transfer rules and attribute rules have been removed in favor of a simpler, case-matching-only architecture.

### Case-Matching Rules

| Rule | Description | Origin | Receiving | Assessments |
|------|-------------|--------|-----------|-------------|
| RULE_1 | EU/EEA/UK/Crown/CH Internal | EU_EEA_UK_CROWN_CH | EU_EEA_UK_CROWN_CH | PIA |
| RULE_2 | EU/EEA to Adequacy Countries | EU_EEA | ADEQUACY_COUNTRIES | PIA |
| RULE_3 | Crown to Adequacy + EU/EEA | CROWN_DEPENDENCIES | ADEQUACY_PLUS_EU | PIA |
| RULE_4 | UK to Adequacy + EU/EEA | United Kingdom | ADEQUACY_PLUS_EU | PIA |
| RULE_5 | Switzerland to Approved | Switzerland | SWITZERLAND_APPROVED | PIA |
| RULE_6 | EU/Adequacy to Rest of World | EU_EEA_ADEQUACY_UK | NOT in EU_EEA_ADEQUACY_UK | PIA + TIA |
| RULE_7 | BCR Countries to Any | BCR_COUNTRIES | Any | PIA + HRPR |
| RULE_8 | Any with Personal Data | Any (with personal data) | Any | PIA |

### Assessment Types

- **PIA** (Privacy Impact Assessment) — Required for all transfer rules
- **TIA** (Transfer Impact Assessment) — Required for rest-of-world transfers (RULE_6)
- **HRPR** (High Risk Processing Review) — Required for BCR country transfers (RULE_7)

### Country Groups (10 groups)

| Group | Description | Count |
|-------|-------------|-------|
| EU_EEA | EU 27 + Norway, Iceland, Liechtenstein | 30 |
| UK_CROWN_DEPENDENCIES | UK + Jersey, Guernsey, Isle of Man | 4 |
| CROWN_DEPENDENCIES | Jersey, Guernsey, Isle of Man | 3 |
| SWITZERLAND | Switzerland | 1 |
| ADEQUACY_COUNTRIES | EU adequacy decisions (incl. US DPF) | 16 |
| SWITZERLAND_APPROVED | Swiss-approved jurisdictions | ~40 |
| BCR_COUNTRIES | Binding Corporate Rules countries | ~55 |
| EU_EEA_UK_CROWN_CH | Combined: EU + UK + Crown + CH | ~35 |
| EU_EEA_ADEQUACY_UK | Combined: EU + Adequacy | ~40 |
| ADEQUACY_PLUS_EU | Combined: Adequacy + EU | ~40 |

---

## Data Dictionaries

Four JSON-based data dictionaries provide industry-standard taxonomies ingested into the graph as nodes:

| Dictionary | Node Type | Entries | Ontology References |
|------------|-----------|---------|---------------------|
| `processes.json` | Process | 52 | APQC PCF, BIAN, COBIT |
| `purposes.json` | Purpose | 51 | GDPR Art.6, ISO 27701, NIST |
| `data_subjects.json` | DataSubject | 51 | GDPR Art.4, ISO 27701 |
| `gdc.json` | GDC | 70 | FIBO, HL7 FHIR, BIAN, ISO 22745 |

**Total: 224 dictionary entries** across financial operations, HR, customer management, technology, compliance, and more.

---

## Graph Schema

### RulesGraph

```
Country -[:BELONGS_TO]-> CountryGroup
Rule -[:TRIGGERED_BY_ORIGIN]-> CountryGroup | Country
Rule -[:TRIGGERED_BY_RECEIVING]-> CountryGroup | Country
Rule -[:EXCLUDES_RECEIVING]-> CountryGroup
Rule -[:HAS_ACTION]-> Action
Rule -[:HAS_PERMISSION]-> Permission
Rule -[:HAS_PROHIBITION]-> Prohibition
Permission -[:CAN_HAVE_DUTY]-> Duty
Prohibition -[:CAN_HAVE_DUTY]-> Duty

# Dictionary nodes (standalone, for admin/wizard use)
Process {name, category}
Purpose {name, category}
DataSubject {name, category}
GDC {name, category}
```

### DataTransferGraph

```
Case -[:ORIGINATES_FROM]-> Country
Case -[:TRANSFERS_TO]-> Jurisdiction
Case -[:HAS_PURPOSE]-> Purpose
Case -[:HAS_PROCESS_L1]-> ProcessL1
Case -[:HAS_PERSONAL_DATA]-> PersonalData
```

---

## Quick Start

### Prerequisites

```bash
# Python 3.11+
python --version

# FalkorDB (via Docker)
docker run -p 6379:6379 falkordb/falkordb:latest

# Node.js 18+ (for frontend)
node --version
```

### Backend

```bash
cd compliance_engine

# Install dependencies
pip install -r requirements_fastapi.txt

# Build the rules graph (creates 8 rules + 224 dictionary entries)
python -c "from utils.graph_builder import build_rules_graph; build_rules_graph()"

# Start the API
uvicorn api.main:app --host 0.0.0.0 --port 5001 --reload
```

### Frontend

```bash
cd compliance_engine/frontend

# Install dependencies
npm install

# Start dev server
npm run dev
```

### Access

- **API Docs**: http://localhost:5001/docs
- **Frontend**: http://localhost:5173
- **Admin Panel**: http://localhost:5173/admin

---

## API Endpoints

### Evaluation

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/evaluate-rules` | Evaluate compliance for a data transfer |
| POST | `/api/search-cases` | Search historical precedent cases |

### Metadata

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/countries` | List all countries |
| GET | `/api/purposes` | List processing purposes |
| GET | `/api/all-dropdown-values` | All dropdown values (incl. dictionaries) |

### Admin CRUD

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/admin/rules` | List all rules |
| POST | `/api/admin/rules` | Create a new rule |
| PUT | `/api/admin/rules/{id}` | Update rule properties |
| DELETE | `/api/admin/rules/{id}` | Delete a rule |
| GET | `/api/admin/country-groups` | List country groups |
| POST | `/api/admin/country-groups` | Create country group |
| PUT | `/api/admin/country-groups/{name}` | Update group (add/remove countries) |
| DELETE | `/api/admin/country-groups/{name}` | Delete group |
| GET | `/api/admin/dictionaries/{type}` | List dictionary entries |
| POST | `/api/admin/dictionaries/{type}` | Add dictionary entry |
| DELETE | `/api/admin/dictionaries/{type}/{name}` | Delete dictionary entry |
| POST | `/api/admin/rebuild-graph` | Rebuild entire graph |
| GET | `/api/admin/graph-stats` | Graph statistics |

Dictionary types: `processes`, `purposes`, `data_subjects`, `gdc`

### Example Request

```json
POST /api/evaluate-rules
{
  "origin_country": "United Kingdom",
  "receiving_country": "India",
  "pii": true,
  "purposes": ["Marketing", "Analytics"]
}
```

### Example Response

```json
{
  "transfer_status": "ALLOWED",
  "triggered_rules": [
    {
      "rule_id": "RULE_7",
      "rule_name": "BCR Countries Transfer",
      "required_assessments": ["PIA", "HRPR"],
      "outcome": "permission"
    }
  ],
  "precedent_validation": {
    "total_matches": 2,
    "compliant_matches": 1,
    "has_valid_precedent": true
  },
  "assessment_compliance": {
    "pia_required": true,
    "hrpr_required": true,
    "all_compliant": true
  }
}
```

---

## Frontend Pages

| Page | Path | Description |
|------|------|-------------|
| Network | `/` | Graph visualization of transfer network |
| Evaluator | `/evaluator` | Interactive rule evaluation |
| Wizard | `/wizard` | Step-by-step rule creation with dictionary selectors |
| Admin | `/admin` | React Flow admin panel with 5-column swimlane layout |

### Admin Panel

The admin panel displays all graph entities in a 5-column React Flow layout:

| Column | Content | Features |
|--------|---------|----------|
| Country Groups | CountryGroup nodes | Right-click to delete |
| Rules | Rule nodes | Right-click to edit/delete |
| Processes | Process dictionary entries | Right-click to delete |
| Purposes | Purpose dictionary entries | Right-click to delete |
| Subjects / GDC | DataSubject + GDC entries | Right-click to delete |

Columns are collapsible. All mutations go through the admin API.

---

## Decision Logic

```
Evaluate Transfer Request
  |
  +-- Phase 1: Query case-matching rules
  |     No rules match? -> REQUIRES_REVIEW (raise governance ticket)
  |
  +-- Phase 2: Search precedent cases
  |     No matching cases? -> PROHIBITED (raise governance ticket)
  |
  +-- Phase 3: Check assessment compliance
        Precedent with completed assessments? -> ALLOWED
        Missing required assessments? -> PROHIBITED
```

Key rules:
1. **No applicable rules** = REQUIRES_REVIEW
2. **No precedent cases** = PROHIBITED (raise governance ticket)
3. **Assessments must be "Completed"** — "In Progress", "N/A", null = non-compliant
4. **At least one compliant case** = ALLOWED

---

## File Structure

```
compliance_engine/
├── api/
│   ├── main.py                    # FastAPI app + router registration
│   └── routers/
│       ├── evaluation.py          # /evaluate-rules, /search-cases
│       ├── metadata.py            # /countries, /purposes, /all-dropdown-values
│       └── admin.py               # Full CRUD for rules, groups, dictionaries
├── config/
│   └── settings.py                # Pydantic v2 settings (DB, AI, cache, etc.)
├── models/
│   └── schemas.py                 # Request/response Pydantic models
├── rules/
│   ├── dictionaries/
│   │   ├── country_groups.py      # 10 country groups (frozensets)
│   │   └── rules_definitions.py   # 8 case-matching rules (dataclasses)
│   ├── data_dictionaries/
│   │   ├── processes.json         # 52 process entries
│   │   ├── purposes.json          # 51 purpose entries
│   │   ├── data_subjects.json     # 51 data subject entries
│   │   └── gdc.json               # 70 global data category entries
│   └── templates/
│       └── cypher_templates.py    # Reusable Cypher query templates
├── services/
│   ├── database.py                # FalkorDB connection management
│   ├── rules_evaluator.py         # Core evaluation engine (case-matching only)
│   ├── sandbox_service.py         # Sandbox graph lifecycle management
│   ├── attribute_detector.py      # Metadata attribute detection
│   └── cache.py                   # Query result caching
├── utils/
│   └── graph_builder.py           # Builds RulesGraph + ingests dictionaries
├── frontend/
│   ├── src/
│   │   ├── App.tsx                # Routes: /, /evaluator, /wizard, /admin
│   │   ├── pages/
│   │   │   └── AdminPage.tsx      # Admin panel page
│   │   ├── components/
│   │   │   ├── admin/
│   │   │   │   ├── AdminGraph.tsx     # 5-column React Flow swimlane
│   │   │   │   ├── AdminSwimlane.tsx  # Dictionary entry node type
│   │   │   │   ├── ContextMenu.tsx    # Right-click CRUD menu
│   │   │   │   └── EditModal.tsx      # Edit/create modal
│   │   │   └── wizard/
│   │   │       └── steps/
│   │   │           └── Step2Scenario.tsx  # Dictionary selectors
│   │   ├── services/
│   │   │   └── adminApi.ts        # Admin API client
│   │   └── stores/
│   │       └── wizardStore.ts     # Zustand store with dictionary fields
│   └── package.json
└── tests/
    ├── test_rules_evaluation.py       # 43 tests: rules, groups, dictionaries
    └── test_comprehensive_rules.py    # 60 tests: permutations, mocked evaluator
```

---

## Testing

```bash
cd compliance_engine

# Run all compliance tests (103 tests)
python -m pytest tests/test_rules_evaluation.py tests/test_comprehensive_rules.py -v

# Run specific test class
python -m pytest tests/test_comprehensive_rules.py::TestRuleMatchingPermutations -v

# Run with coverage
python -m pytest tests/test_rules_evaluation.py tests/test_comprehensive_rules.py --cov=rules --cov=services -v
```

### Test Coverage

| Test Class | Tests | What it covers |
|------------|-------|----------------|
| TestCountryGroups | 8 | Group membership, lookups |
| TestCaseMatchingRules | 9 | Rule structure, assessments |
| TestCypherTemplates | 7 | Query template building |
| TestDataDictionaries | 8 | Dictionary file validation |
| TestRuleMatchingPermutations | 20 | All origin/receiving combinations |
| TestMultipleRuleFiring | 7 | Multi-rule scenarios |
| TestAssessmentRequirements | 5 | PIA/TIA/HRPR correctness |
| TestRandomRulePermutations | 5 | Random country combinations (seeded) |
| TestMockedEvaluator | 6 | Full evaluation pipeline |
| TestGraphBuilderDictionaries | 2 | Dictionary ingestion, rule creation |
| TestEdgeCases | 7 | Boundary conditions |

---

## License

MIT License

---

## Acknowledgments

Built with:
- [FalkorDB](https://www.falkordb.com/) - Graph database
- [FastAPI](https://fastapi.tiangolo.com/) - Python web framework
- [React](https://react.dev/) - Frontend framework
- [React Flow](https://reactflow.dev/) - Graph visualization
- [Pydantic](https://docs.pydantic.dev/) - Data validation
- [ODRL](https://www.w3.org/TR/odrl-model/) - Open Digital Rights Language
