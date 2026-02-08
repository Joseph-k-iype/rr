# Compliance Engine v6.0.0

A scalable, production-ready compliance engine for cross-border data transfer evaluation using graph-based rules, a React frontend, and AI-powered multi-agent rule generation. Agent-to-agent communication uses the [Google A2A SDK](https://github.com/google/a2a-python) (`a2a-sdk`) with LangGraph as the workflow backbone.

## Architecture Overview

```
compliance_engine/
├── api/                        # FastAPI application
│   ├── main.py                 # App entrypoint, router registration, static serving
│   └── routers/                # API router modules
│       ├── evaluation.py       # POST /api/evaluate-rules, /api/search-cases
│       ├── metadata.py         # GET /api/countries, purposes, processes, all-dropdown-values
│       ├── rules_overview.py   # GET /api/rules-overview, /api/cypher-templates
│       ├── graph_data.py       # GET /api/graph/rules-network, /api/graph/country-groups
│       ├── wizard.py           # Wizard lifecycle (10-step flow)
│       ├── sandbox.py          # Sandbox graph testing
│       ├── agent_events.py     # SSE streaming for agent progress
│       └── health.py           # GET /health, /api/stats, /api/cache/*
├── agents/                     # Multi-agent system
│   ├── ai_service.py           # Token auth & LLM calls (o3-mini)
│   ├── state/                  # LangGraph state
│   │   └── wizard_state.py     # WizardAgentState TypedDict
│   ├── executors/              # Google A2A SDK AgentExecutor implementations
│   │   ├── base_executor.py    # Core bridge: ComplianceAgentExecutor, wrap_executor_as_node()
│   │   ├── utils.py            # Shared parse_json_response()
│   │   ├── supervisor_executor.py
│   │   ├── rule_analyzer_executor.py
│   │   ├── cypher_generator_executor.py  # + FalkorDB EXPLAIN validation
│   │   ├── validator_executor.py         # + FalkorDB temp graph testing
│   │   ├── data_dictionary_executor.py
│   │   └── reference_data_executor.py    # + FalkorDB group lookup
│   ├── nodes/                  # Thin LangGraph node shims (wrap executors)
│   │   ├── supervisor.py
│   │   ├── rule_analyzer.py
│   │   ├── cypher_generator.py
│   │   ├── validator.py
│   │   ├── data_dictionary.py
│   │   ├── reference_data.py
│   │   └── validation_models.py # Pydantic validation models
│   ├── prompts/                # All agent prompts
│   │   ├── supervisor_prompts.py
│   │   ├── analyzer_prompts.py
│   │   ├── cypher_prompts.py
│   │   ├── validator_prompts.py
│   │   ├── dictionary_prompts.py
│   │   ├── reference_prompts.py
│   │   └── prompt_builder.py   # Dynamic prompt assembly
│   ├── workflows/
│   │   └── rule_ingestion_workflow.py  # LangGraph StateGraph
│   ├── protocol/               # A2A agent registry (Google A2A SDK AgentCard/AgentSkill)
│   └── audit/                  # Event-sourced audit trail
│       ├── event_store.py
│       └── event_types.py
├── config/                     # Configuration
│   └── settings.py             # Pydantic v2 settings (env-based)
├── models/                     # Pydantic models
│   ├── schemas.py              # Request/response schemas
│   ├── wizard_models.py        # Wizard session models
│   └── agent_models.py         # AgentEventType & AgentEvent for SSE
├── rules/                      # Rule definitions
│   ├── dictionaries/
│   │   ├── country_groups.py   # Country groups (EU_EEA, BCR, etc.)
│   │   └── rules_definitions.py # All 3 rule sets
│   └── templates/
│       └── cypher_templates.py # Cypher query templates
├── services/                   # Core services
│   ├── database.py             # FalkorDB connection
│   ├── cache.py                # LRU cache with TTL
│   ├── attribute_detector.py   # Metadata detection
│   ├── rules_evaluator.py      # Main evaluation engine
│   ├── sandbox_service.py      # Sandbox graph lifecycle
│   └── sse_manager.py          # SSE connection manager
├── utils/
│   ├── graph_builder.py        # Build RulesGraph from definitions
│   └── data_uploader.py        # Upload case data to DataTransferGraph
├── frontend/                   # React + TypeScript app (Vite)
│   ├── src/
│   │   ├── pages/              # HomePage (graph), EvaluatorPage, WizardPage
│   │   ├── components/         # graph/, evaluator/, wizard/ (10 steps)
│   │   ├── stores/             # Zustand stores (wizardStore, evaluationStore)
│   │   ├── services/           # API client layer
│   │   ├── hooks/              # Custom hooks (useRulesNetwork, useAgentEvents)
│   │   └── types/              # TypeScript interfaces
│   └── package.json
├── cli/
│   └── rule_generator_cli.py   # Interactive CLI for rule generation
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

## Three Rule Sets

### SET 1: Case-Matching Rules
Search for historical cases in the DataTransferGraph. If a precedent case with completed assessments (PIA, TIA, HRPR) is found, transfer is **ALLOWED**.

**Defined in:** `rules/dictionaries/rules_definitions.py` → `CASE_MATCHING_RULES`

### SET 2A: Transfer Rules
Country-to-country transfer permissions/prohibitions with highest priority.

**Defined in:** `rules/dictionaries/rules_definitions.py` → `TRANSFER_RULES`

### SET 2B: Attribute Rules
Rules based on data attributes (health, financial, biometric data).

**Defined in:** `rules/dictionaries/rules_definitions.py` → `ATTRIBUTE_RULES`

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

### AI-Powered Generation (10-Step Wizard)

Use the React frontend wizard at http://localhost:5001/wizard:

1. Select origin country and receiving countries
2. Choose scenario type (transfer/attribute)
3. Enter rule text in natural language
4. AI analyzes rule (Chain of Thought)
5. AI generates keyword dictionary
6. Review generated outputs
7. Edit rule definition and terms
8. Load into sandbox graph
9. Test in sandbox with sample evaluations
10. Approve and load to main graph

### CLI Tool

```bash
python -m cli.rule_generator_cli --interactive
python -m cli.rule_generator_cli --rule "Prohibit transfers from UK to China"
```

## API Endpoints

### Evaluation
- `POST /api/evaluate-rules` - Evaluate transfer compliance
- `POST /api/search-cases` - Search historical cases

### Rules & Graph
- `GET /api/rules-overview` - Get all rules overview
- `GET /api/cypher-templates` - Get available Cypher templates
- `GET /api/graph/rules-network` - Rules network graph data
- `GET /api/graph/country-groups` - Country group data

### Wizard (10-Step Flow)
- `POST /api/wizard/start-session` - Start wizard session
- `POST /api/wizard/submit-step` - Submit step data
- `GET /api/wizard/session/{id}` - Get session state
- `PUT /api/wizard/session/{id}/edit-rule` - Edit rule definition
- `PUT /api/wizard/session/{id}/edit-terms` - Edit terms dictionary
- `POST /api/wizard/session/{id}/load-sandbox` - Load to sandbox
- `POST /api/wizard/session/{id}/sandbox-evaluate` - Test in sandbox
- `POST /api/wizard/session/{id}/approve` - Approve & load to main
- `DELETE /api/wizard/session/{id}` - Cancel session

### Agent Events
- `GET /api/agent-events/stream/{session_id}` - SSE event stream

### Metadata
- `GET /api/countries` - List countries
- `GET /api/purposes` - List purposes
- `GET /api/processes` - List processes
- `GET /api/all-dropdown-values` - All dropdown values

### Admin
- `GET /health` - Health check
- `GET /api/stats` - System statistics
- `GET /api/cache/stats` - Cache statistics
- `POST /api/cache/clear` - Clear cache

### Agent Audit
- `GET /api/agent/sessions` - List audit sessions
- `GET /api/agent/sessions/{id}` - Session details
- `GET /api/agent/stats` - Agent statistics

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
