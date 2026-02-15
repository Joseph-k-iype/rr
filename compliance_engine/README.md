# Compliance Engine v6.0.0

A scalable, production-ready compliance engine for cross-border data transfer evaluation using graph-based rules, a React frontend, and AI-powered multi-agent rule generation. Agent-to-agent communication uses the [Google A2A SDK](https://github.com/google/a2a-python) (`a2a-sdk`) with LangGraph as the workflow backbone.

## Architecture Overview

```
compliance_engine/
├── api/                        # FastAPI application
│   ├── main.py                 # App entrypoint, router registration, static serving
│   └── routers/                # API router modules
│       ├── evaluation.py       # POST /api/evaluate-rules, /api/search-cases
│       ├── metadata.py         # GET /api/countries, purposes, legal-entities, dropdown values
│       ├── rules_overview.py   # GET /api/rules-overview, /api/rules-overview-table
│       ├── graph_data.py       # GET /api/graph/rules-network, /api/graph/country-groups
│       ├── wizard.py           # Wizard lifecycle (6-step flow) with save/resume
│       ├── sandbox.py          # Sandbox graph testing
│       ├── agent_events.py     # SSE streaming for agent progress
│       └── health.py           # GET /health, /api/stats, /api/cache/*
├── agents/                     # Multi-agent system
│   ├── ai_service.py           # Token auth & LLM calls (o3-mini)
│   ├── state/                  # LangGraph state
│   ├── executors/              # Google A2A SDK AgentExecutor implementations
│   ├── nodes/                  # Thin LangGraph node shims (wrap executors)
│   ├── prompts/                # All agent prompts
│   ├── workflows/              # LangGraph StateGraph
│   ├── protocol/               # A2A agent registry
│   └── audit/                  # Event-sourced audit trail
├── config/                     # Configuration (Pydantic v2 settings)
├── models/                     # Pydantic models (schemas, wizard, AgentEvent)
├── rules/                      # Rule definitions & data dictionaries
│   ├── dictionaries/           # Country groups & rule definitions
│   ├── data_dictionaries/      # JSON reference data (legal entities, purposes, etc.)
│   └── templates/              # Cypher query templates
├── services/                   # Core services
│   ├── database.py             # FalkorDB connection
│   ├── cache.py                # LRU cache with TTL
│   ├── rules_evaluator.py      # Main evaluation engine
│   ├── sandbox_service.py      # Sandbox graph lifecycle
│   ├── session_store.py        # Wizard session persistence (JSON file-based)
│   └── sse_manager.py          # SSE connection manager
├── utils/
│   ├── graph_builder.py        # Build RulesGraph (with LegalEntity nodes)
│   └── data_uploader.py        # Upload case data to DataTransferGraph
├── frontend/                   # React + TypeScript app (Vite)
│   └── src/
│       ├── pages/              # HomePage (table), EvaluatorPage, WizardPage, LoginPage
│       ├── components/         # evaluator/, wizard/ (6 steps), layout/, common/
│       ├── stores/             # Zustand stores (wizardStore, evaluationStore, authStore)
│       ├── services/           # API client layer
│       ├── hooks/              # Custom hooks (useAgentEvents, useDropdownData)
│       └── types/              # TypeScript interfaces
├── cli/                        # Interactive CLI for rule generation
├── data/saved_sessions/        # Server-side wizard session persistence
└── tests/                      # Test suite
```

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
cd frontend && npm install && cd ..
```

### 2. Configure Environment

```bash
cp .env.example .env
```

Key variables:
```env
FALKORDB_HOST=localhost
FALKORDB_PORT=6379
AI_TOKEN_API_URL=https://your-token-api/translate
AI_LLM_API_URL=https://your-llm-api/chat/completions
AI_LLM_MODEL=o3-mini
ENABLE_AI_RULE_GENERATION=true
```

### 3. Build Rules Graph

```bash
python main.py --build-graph
```

### 4. Build Frontend

```bash
cd frontend && npm run build && cd ..
```

### 5. Run the Server

```bash
python main.py
```

Access:
- Frontend: http://localhost:5001/
- API Docs: http://localhost:5001/docs

## Authentication

The UI requires login. Two built-in accounts are available:

| Username | Password | Role | Access |
|----------|----------|------|--------|
| `admin` | `admin` | Admin | Policy Overview, Policy Evaluator, Policy Generator, Policy Editor |
| `user` | `user` | User | Policy Overview, Policy Evaluator |

Admin-only pages (Policy Generator, Policy Editor) are hidden from the navigation for regular users and protected by route guards.

## UI Pages

| Page | Route | Role | Description |
|------|-------|------|-------------|
| Login | `/login` | All | Username/password authentication |
| Policy Overview | `/` | All | Data table with filters, search, and rule statistics |
| Policy Evaluator | `/evaluator` | All | Evaluate compliance with legal entity support |
| Policy Generator | `/generator` | Admin | 6-step wizard for AI-powered rule creation |
| Policy Editor | `/editor` | Admin | Rule editing (placeholder) |

## Three Rule Sets

### SET 1: Case-Matching Rules
Search for historical cases in the DataTransferGraph. Uses case-insensitive CONTAINS matching on country names. Rules with an expired `valid_until` date are skipped. If ANY triggered rule is a prohibition, the overall result is **PROHIBITED**.

**Defined in:** `rules/dictionaries/rules_definitions.py` -> `CASE_MATCHING_RULES`

### SET 2A: Transfer Rules
Country-to-country transfer permissions/prohibitions with highest priority.

**Defined in:** `rules/dictionaries/rules_definitions.py` -> `TRANSFER_RULES`

### SET 2B: Attribute Rules
Rules based on data attributes (health, financial, biometric data).

**Defined in:** `rules/dictionaries/rules_definitions.py` -> `ATTRIBUTE_RULES`

## Key Features

### Legal Entity Support
Rules and evaluations can target specific legal entities within countries. Legal entity mappings are defined in `rules/data_dictionaries/legal_entities.json`. The evaluator accepts `origin_legal_entity` and `receiving_legal_entity` parameters alongside country selections.

### Prohibition Logic
- Prohibitions do NOT have duties (only permissions can have duties)
- If ANY triggered rule is a prohibition, the overall transfer status is **PROHIBITED**
- This is enforced in both the graph schema and the evaluation engine

### Rule Expiration
Rules can have a `valid_until` date. Expired rules are automatically excluded from evaluation via the Cypher query: `WHERE r.valid_until IS NULL OR r.valid_until >= $today`.

### Session Save/Resume
Wizard sessions can be saved from Step 4 (Review) onwards and resumed later. Sessions are persisted both server-side (JSON files in `data/saved_sessions/`) and client-side (localStorage for auto-recovery).

## Adding New Rules

### Manual Addition

Edit `rules/dictionaries/rules_definitions.py`:

```python
TRANSFER_RULES["MY_NEW_RULE"] = TransferRule(
    rule_id="RULE_MY_01",
    name="My New Transfer Rule",
    description="Description of the rule",
    priority=5,
    origin_group="EU_EEA",
    receiving_countries=frozenset({"SomeCountry"}),
    outcome=RuleOutcome.PROHIBITION,
    odrl_type="Prohibition",
)
```

Then rebuild: `python main.py --build-graph`

### AI-Powered Generation (6-Step Wizard)

Access the wizard at http://localhost:5001/generator (admin login required):

| Step | Action |
|------|--------|
| 1. Country | Select origin/receiving country and legal entities |
| 2. Metadata | Data categories, purpose of processing, processes L1/L2/L3, group data categories, valid until date |
| 3. Rule | Enter rule text in natural language; AI agents analyze and generate a machine-readable definition |
| 4. Review | Edit generated rule: ID, title, description, permission/prohibition, actions, duties, data dictionaries |
| 5. Sandbox Test | Load rule into temporary graph and test with sample evaluations |
| 6. Approve | Confirm and promote rule to the main RulesGraph |

Sessions can be saved from Step 4 onwards and resumed later.

### CLI Tool

```bash
python -m cli.rule_generator_cli --interactive
python -m cli.rule_generator_cli --rule "Prohibit transfers from UK to China"
```

## API Endpoints

### Evaluation
- `POST /api/evaluate-rules` - Evaluate transfer compliance (supports legal entities, multi-select receiving countries)
- `POST /api/search-cases` - Search historical cases

### Rules & Metadata
- `GET /api/rules-overview` - Get all rules overview
- `GET /api/rules-overview-table` - Table-friendly rules data with filters (country, risk, duty, search)
- `GET /api/countries` - List countries
- `GET /api/purposes` - List purposes
- `GET /api/processes` - List processes
- `GET /api/all-dropdown-values` - All dropdown values (includes legal entities, purpose of processing)
- `GET /api/legal-entities` - Legal entity mappings by country
- `GET /api/legal-entities/{country}` - Legal entities for a specific country
- `GET /api/purpose-of-processing` - Standard purposes of processing
- `GET /api/group-data-categories` - Group data categories from graph

### Wizard (6-Step Flow)
- `POST /api/wizard/start-session` - Start wizard session
- `POST /api/wizard/submit-step` - Submit step data (triggers AI at step 3)
- `GET /api/wizard/session/{id}` - Get session state
- `PUT /api/wizard/session/{id}/edit-rule` - Edit rule definition
- `PUT /api/wizard/session/{id}/edit-terms` - Edit terms dictionary
- `POST /api/wizard/session/{id}/load-sandbox` - Load to sandbox graph
- `POST /api/wizard/session/{id}/sandbox-evaluate` - Test in sandbox
- `POST /api/wizard/session/{id}/approve` - Approve & load to main graph
- `DELETE /api/wizard/session/{id}` - Cancel session

### Wizard Session Persistence
- `POST /api/wizard/save-session` - Save session for later resume
- `GET /api/wizard/saved-sessions` - List saved sessions
- `GET /api/wizard/resume-session/{id}` - Resume a saved session
- `DELETE /api/wizard/saved-session/{id}` - Delete saved session

### Agent Events
- `GET /api/agent-events/stream/{session_id}` - SSE event stream

### Admin & Health
- `GET /health` - Health check
- `GET /api/stats` - System statistics
- `GET /api/cache/stats` - Cache statistics
- `POST /api/cache/clear` - Clear cache
- `GET /api/agent/sessions` - List audit sessions
- `GET /api/agent/sessions/{id}` - Session details

## Graph Schema

### RulesGraph

Nodes: Country, CountryGroup, LegalEntity, Rule, Action, Permission, Prohibition, Duty, Process, Purpose, DataSubject, GDC, DataCategory

Key relationships:
- `Country -[:BELONGS_TO]-> CountryGroup`
- `Country -[:HAS_LEGAL_ENTITY]-> LegalEntity`
- `Rule -[:TRIGGERED_BY_ORIGIN]-> CountryGroup | Country | LegalEntity`
- `Rule -[:TRIGGERED_BY_RECEIVING]-> CountryGroup | Country | LegalEntity`
- `Rule -[:HAS_PERMISSION]-> Permission`
- `Rule -[:HAS_PROHIBITION]-> Prohibition`
- `Permission -[:CAN_HAVE_DUTY]-> Duty` (Prohibitions do NOT have duties)

### DataTransferGraph

Nodes: Case, Country, Jurisdiction, Purpose, ProcessL1/L2/L3, PersonalData, PersonalDataCategory

Key relationships: ORIGINATES_FROM, TRANSFERS_TO, HAS_PURPOSE, HAS_PROCESS_L1/L2/L3

## Testing

```bash
pytest tests/ -v
```

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `FALKORDB_HOST` | localhost | FalkorDB host |
| `FALKORDB_PORT` | 6379 | FalkorDB port |
| `API_PORT` | 5001 | API server port |
| `AI_LLM_MODEL` | o3-mini | LLM model name |
| `ENABLE_AI_RULE_GENERATION` | true | Enable AI features |
| `ENABLE_CACHE` | true | Enable caching |
| `CACHE_TTL` | 300 | Cache TTL in seconds |

## License

Internal use only.
