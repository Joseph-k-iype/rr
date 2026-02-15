# Compliance Engine v6.0 - Developer Guide

## Table of Contents
1. [Architecture Overview](#architecture-overview)
2. [Rule System](#rule-system)
3. [Creating New Rules](#creating-new-rules)
4. [Multi-Agent Workflow](#multi-agent-workflow)
5. [Google A2A SDK Integration](#google-a2a-sdk-integration)
6. [Agent-to-FalkorDB Communication](#agent-to-falkordb-communication)
7. [Graph Schemas](#graph-schemas)
8. [Frontend Architecture](#frontend-architecture)
9. [API Reference](#api-reference)
10. [Testing](#testing)
11. [Configuration](#configuration)
12. [Troubleshooting](#troubleshooting)

---

## Architecture Overview

The Compliance Engine is built on a two-graph architecture using FalkorDB, with a React+TypeScript frontend and a LangGraph-based multi-agent backend. Agent-to-agent communication uses the Google A2A SDK (`a2a-sdk>=0.3.22`) for standardized `AgentExecutor`, `EventQueue`, and `AgentCard` abstractions, running in-process within a single FastAPI application.

### System Components

```
+---------------------------------------------------------------------------+
|                     React + TypeScript Frontend                            |
|  +----------------+  +----------------+  +-----------------------------+  |
|  | Policy Overview|  | Policy         |  | Policy Generator            |  |
|  | (Data Table)   |  | Evaluator      |  | (6-Step Wizard + SSE)       |  |
|  +----------------+  +----------------+  +-----------------------------+  |
|  Login (admin/admin, user/user) | Role-Based Access | GSAP Animations     |
+-------------------------------------------+-------------------------------+
|                     FastAPI Server (Routers)                               |
|  evaluation | metadata | wizard | sandbox | agent_events | health         |
+-------------------------------------------+-------------------------------+
|  Services Layer            |  Multi-Agent Layer (LangGraph + A2A SDK)      |
|  - RulesEvaluator          |  - Supervisor -> Analyzer -> Dictionary       |
|  - SandboxService          |  - -> CypherGen -> Validator -> Complete      |
|  - SessionStore            |  - Google A2A SDK AgentExecutors              |
|  - CacheService            |  - Event-sourced audit trail                  |
+-------------------------------------------+-------------------------------+
|                      FalkorDB (Graph Database)                             |
|  +------------------------+    +----------------------------------+       |
|  |    RulesGraph           |    |     DataTransferGraph             |       |
|  |  (Rules, permissions,   |    |  (Historical cases, assessments,  |       |
|  |   duties, legal entities|    |   purposes, processes,            |       |
|  |   country groups)       |    |   personal data categories)       |       |
|  +------------------------+    +----------------------------------+       |
+---------------------------------------------------------------------------+
```

### Key Directories

```
compliance_engine/
├── api/routers/         # 8 FastAPI router modules
├── agents/
│   ├── executors/       # A2A SDK AgentExecutor implementations (business logic)
│   ├── nodes/           # Thin LangGraph node shims (wrap executors)
│   ├── prompts/         # 7 prompt files + builder
│   ├── workflows/       # LangGraph StateGraph
│   ├── protocol/        # A2A agent registry (AgentCard/AgentSkill)
│   ├── audit/           # Event store & event types
│   └── state/           # WizardAgentState TypedDict
├── services/            # Core business logic (evaluator, sandbox, SSE, cache, session store)
├── rules/
│   ├── dictionaries/    # Country groups & rule definitions
│   ├── data_dictionaries/ # JSON reference data (legal entities, purposes)
│   └── templates/       # Cypher query templates
├── models/              # Pydantic models (schemas, wizard, AgentEvent)
├── frontend/            # Vite + React + TypeScript
│   └── src/             # pages, components, stores, hooks, services
├── cli/                 # Rule generator CLI tool
└── tests/               # Test suite
```

---

## Rule System

The engine uses a **three-set rule system**. Health rules, TIA/PIA/HRPR assessments, and real-time case searching all remain intact.

### Key Evaluation Logic

- **Case-insensitive CONTAINS matching** on country names in Cypher queries
- **Rule expiration**: Rules with `valid_until` date in the past are excluded from evaluation
- **Prohibition override**: If ANY triggered rule is a prohibition, the overall transfer status is **PROHIBITED**
- **Prohibition-duty separation**: Prohibitions do NOT have duties; only permissions can have duties

### SET 1: Case Matching Rules

Rules that check for historical precedent in the DataTransferGraph. If a case with completed assessments is found, transfer is **ALLOWED**.

```python
@dataclass
class CaseMatchingRule:
    rule_id: str
    name: str
    description: str
    priority: int  # 1-100, lower = higher priority
    origin_countries: Optional[FrozenSet[str]] = None
    origin_group: Optional[str] = None
    receiving_countries: Optional[FrozenSet[str]] = None
    receiving_group: Optional[str] = None
    receiving_not_in: Optional[FrozenSet[str]] = None
    required_assessments: RequiredAssessments = RequiredAssessments()
    requires_pii: bool = False
    requires_personal_data: bool = False
    enabled: bool = True
    odrl_type: str = "Permission"
```

### SET 2A: Transfer Rules

Country-to-country transfer permissions/prohibitions with highest priority.

### SET 2B: Attribute Rules

Rules based on data attributes (health, financial, biometric, etc.).

### Evaluation Flow

The evaluation engine (`services/rules_evaluator.py`) processes rules in this order:

1. **Phase 1 - Case Matching** (SET 1): Execute case-matching rules via Cypher query against RulesGraph. Uses case-insensitive CONTAINS matching, checks `valid_until` expiration, and collects prohibition flags.
2. **Phase 2 - Prohibition Check**: If ANY triggered rule is a prohibition, return PROHIBITED immediately.
3. **Phase 3 - Precedent Search**: Search for historical precedent cases in DataTransferGraph with assessment compliance checking.

### Legal Entity Support

Rules and evaluations support legal entity targeting:
- `origin_legal_entity` - Specific legal entity in the origin country
- `receiving_legal_entity` - Specific legal entities in receiving countries
- Legal entities are linked to countries via `HAS_LEGAL_ENTITY` relationship in the graph
- Mappings defined in `rules/data_dictionaries/legal_entities.json`

### Precedent Evidence System

When evaluating transfers, the engine computes field-level match analysis:

| Field | Weight |
|-------|--------|
| origin_country | 25% |
| receiving_country | 25% |
| purposes | 15% |
| process_l1 | 10% |
| process_l2 | 8% |
| process_l3 | 7% |
| personal_data_names | 10% |

---

## Creating New Rules

### Method 1: Manual Addition

Edit `rules/dictionaries/rules_definitions.py`:

```python
TRANSFER_RULES["RULE_UK_CHINA_TECH"] = TransferRule(
    rule_id="RULE_UK_CHINA_TECH",
    name="UK to China Technology Transfer",
    description="Prohibit transfer of technology data from UK to China",
    priority=15,
    origin_countries=frozenset(["United Kingdom"]),
    receiving_countries=frozenset(["China"]),
    outcome=RuleOutcome.PROHIBITION,
    odrl_type="Prohibition",
    enabled=True,
)
```

Then rebuild: `python main.py --build-graph`

### Method 2: 6-Step Wizard (Frontend)

Access the wizard at http://localhost:5001/generator (requires admin login: `admin` / `admin`):

| Step | Action |
|------|--------|
| 1. Country | Select origin/receiving country and legal entities |
| 2. Metadata | Data categories (required), purpose of processing, processes L1/L2/L3, group data categories, valid until date |
| 3. Rule | Enter rule text in natural language; AI agents process it |
| 4. Review | Edit generated rule definition, actions, duties, data dictionaries |
| 5. Sandbox Test | Load rule into temporary graph and test with sample evaluations |
| 6. Approve | Confirm and promote rule to the main RulesGraph |

Sessions can be saved from Step 4 onwards and resumed later via the save/resume API.

### Method 3: CLI Tool

```bash
python -m cli.rule_generator_cli --interactive
python -m cli.rule_generator_cli --rule "Prohibit transfers from UK to China" --country "United Kingdom"
```

### Adding Country Groups

Edit `rules/dictionaries/country_groups.py`:

```python
MY_NEW_GROUP: FrozenSet[str] = frozenset({
    "Country1", "Country2", "Country3"
})

# Add to registry
COUNTRY_GROUPS["MY_NEW_GROUP"] = MY_NEW_GROUP
```

### Adding Legal Entities

Edit `rules/data_dictionaries/legal_entities.json`:

```json
{
  "Country Name": ["Legal Entity 1", "Legal Entity 2"]
}
```

Then rebuild the graph: `python main.py --build-graph`

---

## Multi-Agent Workflow

### LangGraph Architecture

```
Entry -> Supervisor -> {rule_analyzer | data_dictionary | cypher_generator |
                        validator | reference_data | human_review}
          ^              |
          +-- Supervisor <-- (retry on validation failure, max 3 iterations)
                             |
                     complete / fail -> END
```

### Executor Architecture (A2A SDK Bridge)

Each agent is implemented as a Google A2A SDK `AgentExecutor` in `agents/executors/`, bridged to LangGraph via `wrap_executor_as_node()`:

```
LangGraph calls:  node_fn(state) -> state       [agents/nodes/*.py - thin shims]
                       |
                  wrap_executor_as_node()         [agents/executors/base_executor.py]
                       |
                  InProcessRequestContext(state)  [wraps WizardAgentState]
                  EventQueue()                    [A2A SDK async event queue]
                       |
                  executor.execute(ctx, queue)    [agents/executors/*_executor.py]
                       |
                  _drain_event_queue_to_sse()     [A2A events -> SSE AgentEvent]
                       |
                  return state                    [mutated by executor]
```

### Agent Executors

| Agent | Executor | Technique | FalkorDB |
|-------|----------|-----------|----------|
| **Supervisor** | `SupervisorExecutor` | Dynamic prompt with state context | No |
| **Rule Analyzer** | `RuleAnalyzerExecutor` | Chain of Thought (CoT) | No |
| **Data Dictionary** | `DataDictionaryExecutor` | Category-specific prompts | No |
| **Cypher Generator** | `CypherGeneratorExecutor` | Mixture of Experts (MoE) | `EXPLAIN` syntax validation |
| **Validator** | `ValidatorExecutor` | Schema-aware checklist | Temp graph test queries |
| **Reference Data** | `ReferenceDataExecutor` | Gap analysis | Country group lookup |
| **Human Review** | _(inline in workflow)_ | `interrupt_before` | No |

### Adding a New Agent

1. Create `agents/executors/my_agent_executor.py`:
   ```python
   from agents.executors.base_executor import ComplianceAgentExecutor, InProcessRequestContext

   class MyAgentExecutor(ComplianceAgentExecutor):
       agent_name = "my_agent"

       async def execute(self, context, event_queue):
           ctx: InProcessRequestContext = context
           state = ctx.state
           await self.emit_working(event_queue, ctx)
           # ... your logic, mutate state ...
           await self.emit_completed(event_queue, ctx)
   ```

2. Create `agents/nodes/my_agent.py`:
   ```python
   from agents.executors.my_agent_executor import MyAgentExecutor
   from agents.executors.base_executor import wrap_executor_as_node

   _executor = MyAgentExecutor()
   my_agent_node = wrap_executor_as_node(_executor)
   ```

3. Register the agent card in `agents/protocol/__init__.py`.

4. Add the node to the workflow in `agents/workflows/rule_ingestion_workflow.py`.

---

## Agent-to-FalkorDB Communication

Three agents receive `DatabaseService` via constructor injection for direct FalkorDB interaction:

| Agent | FalkorDB Usage | Method |
|-------|---------------|--------|
| **Cypher Generator** | Syntax-validate generated Cypher with `EXPLAIN` | `db_service.execute_query("EXPLAIN ...")` |
| **Validator** | Run test queries in a temporary graph | `db_service.get_temp_graph()` -> insert -> validate |
| **Reference Data** | Query existing country groups from RulesGraph | `db_service.execute_rules_query("MATCH (g:CountryGroup) RETURN g.name")` |

---

## Graph Schemas

### RulesGraph Schema

Nodes: Country, CountryGroup, LegalEntity, Rule, Action, Permission, Prohibition, Duty, Process, Purpose, DataSubject, GDC, DataCategory

Key relationships:
```
Country -[:BELONGS_TO]-> CountryGroup
Country -[:HAS_LEGAL_ENTITY]-> LegalEntity
Rule -[:TRIGGERED_BY_ORIGIN]-> CountryGroup | Country | LegalEntity
Rule -[:TRIGGERED_BY_RECEIVING]-> CountryGroup | Country | LegalEntity
Rule -[:EXCLUDES_RECEIVING]-> CountryGroup
Rule -[:HAS_ACTION]-> Action
Rule -[:HAS_PERMISSION]-> Permission
Rule -[:HAS_PROHIBITION]-> Prohibition
Permission -[:CAN_HAVE_DUTY]-> Duty
```

**Important:** Prohibitions do NOT have the `CAN_HAVE_DUTY` relationship. Only permissions can have duties.

**Node Properties:**
- `Rule`: rule_id, priority, origin_match_type, receiving_match_type, odrl_type, has_pii_required, outcome, valid_until
- `LegalEntity`: name, country
- `Country`: name
- `CountryGroup`: name
- `Permission/Prohibition`: name
- `Duty`: name, module, value

### DataTransferGraph Schema

```
Case -[:ORIGINATES_FROM]-> Country
Case -[:TRANSFERS_TO]-> Jurisdiction
Case -[:HAS_PURPOSE]-> Purpose
Case -[:HAS_PROCESS_L1]-> ProcessL1
Case -[:HAS_PROCESS_L2]-> ProcessL2
Case -[:HAS_PROCESS_L3]-> ProcessL3
Case -[:HAS_PERSONAL_DATA]-> PersonalData
Case -[:HAS_PERSONAL_DATA_CATEGORY]-> PersonalDataCategory
```

**Case Properties:** case_ref_id, case_status, pia_status, tia_status, hrpr_status

---

## Frontend Architecture

### Tech Stack
- **Vite 7** + **React 19** + **TypeScript**
- **GSAP** for page and step transition animations
- **Zustand** for state management (wizard, evaluation, auth)
- **TanStack React Query** for API data caching
- **Tailwind CSS v4** for styling
- **React Router v7** for client-side routing

### Authentication

Two hardcoded accounts:
- `admin` / `admin` - Full access (all pages)
- `user` / `user` - Limited access (Policy Overview + Evaluator only)

Auth state is managed in `stores/authStore.ts` with localStorage persistence. Routes are protected by `ProtectedRoute` component using role-based checks.

### Pages

| Page | Route | Role | Description |
|------|-------|------|-------------|
| Login | `/login` | Public | Username/password form |
| Policy Overview | `/` | All | Data table with filters (country, risk, duty) and search |
| Policy Evaluator | `/evaluator` | All | Compliance evaluation with legal entity support |
| Policy Generator | `/generator` | Admin | 6-step wizard with AI agents |
| Policy Editor | `/editor` | Admin | Placeholder |

### Key Frontend Files

```
frontend/src/
├── pages/
│   ├── LoginPage.tsx              # Auth login form
│   ├── HomePage.tsx               # Policy Overview - data table
│   ├── EvaluatorPage.tsx          # Policy Evaluator - form + results
│   └── WizardPage.tsx             # Policy Generator - 6-step wizard
├── components/
│   ├── layout/
│   │   ├── AppLayout.tsx          # Main layout (GSAP fade-in)
│   │   └── Navbar.tsx             # Horizontal pill-style nav (role-based)
│   ├── evaluator/
│   │   ├── EvaluatorForm.tsx      # Dark form with legal entity fields
│   │   └── EvaluationResult.tsx   # Results with permission/prohibition badges
│   ├── wizard/
│   │   ├── WizardContainer.tsx    # 6-step orchestrator (GSAP transitions)
│   │   ├── WizardStepper.tsx      # Step indicator (pill-style)
│   │   ├── WizardNavigation.tsx   # Back/Next navigation
│   │   ├── shared/
│   │   │   └── AgentProgressPanel.tsx
│   │   └── steps/
│   │       ├── Step1Country.tsx      # Country + legal entity
│   │       ├── Step2Metadata.tsx     # Data categories, purposes, processes
│   │       ├── Step3RuleText.tsx     # Rule text + agent progress
│   │       ├── Step4Review.tsx       # Editable rule review
│   │       ├── Step5SandboxTest.tsx  # Sandbox evaluation
│   │       └── Step6Approve.tsx      # Approval + promotion
│   └── common/
│       ├── ProtectedRoute.tsx     # Auth + role route guard (Outlet pattern)
│       ├── ErrorBoundary.tsx
│       ├── LoadingSpinner.tsx
│       └── StatusBadge.tsx
├── stores/
│   ├── authStore.ts               # Login, logout, role (localStorage)
│   ├── wizardStore.ts             # 6-step wizard state + save/resume
│   └── evaluationStore.ts         # Evaluation results
├── hooks/
│   ├── useAgentEvents.ts          # SSE hook for agent progress
│   ├── useDropdownData.ts         # TanStack Query for dropdowns
│   └── useEvaluation.ts           # Evaluation mutation
└── services/
    ├── api.ts                     # Axios instance
    ├── rulesApi.ts                # Rules, dropdowns, legal entities
    ├── wizardApi.ts               # Wizard lifecycle + save/resume
    └── evaluatorApi.ts            # Evaluation API
```

### Wizard Data Flow

1. Steps 1-3: User input stored in Zustand -> submitted to backend via `submitWizardStep`
2. Step 3 submission triggers AI agents on backend
3. After step 3, frontend fetches session state via `getWizardSession` to populate:
   - `analysisResult`, `dictionaryResult`, `editedRuleDefinition`, `editedTermsDictionary`
4. Step 4: User can edit the rule definition and save changes via `editRule`/`editTerms`
5. Step 5: Load rule into sandbox graph and test with sample evaluations
6. Step 6: Approve and promote to main graph; redirects to Policy Overview

Sessions can be saved from Step 4 onwards via `saveWizardSession` API. Saved sessions persist both server-side (JSON files) and client-side (localStorage).

---

## API Reference

### Evaluation

```http
POST /api/evaluate-rules
Content-Type: application/json

{
    "origin_country": "United Kingdom",
    "receiving_country": ["India", "China"],
    "pii": true,
    "purposes": ["Marketing"],
    "origin_legal_entity": "HSBC Holdings plc",
    "receiving_legal_entity": ["Tata Consultancy Services"]
}
```

### Wizard Lifecycle (6-Step)

```http
POST /api/wizard/start-session           # Start session
POST /api/wizard/submit-step             # Submit step data (triggers AI at step 3)
GET  /api/wizard/session/{id}            # Get full session state
PUT  /api/wizard/session/{id}/edit-rule  # Edit rule definition
PUT  /api/wizard/session/{id}/edit-terms # Edit terms dictionary
POST /api/wizard/session/{id}/load-sandbox      # Load to temp graph
POST /api/wizard/session/{id}/sandbox-evaluate  # Test in sandbox
POST /api/wizard/session/{id}/approve           # Promote to main graph
DELETE /api/wizard/session/{id}                  # Cancel & cleanup
```

### Session Persistence

```http
POST /api/wizard/save-session?session_id={id}   # Save for later resume
GET  /api/wizard/saved-sessions                   # List saved sessions
GET  /api/wizard/resume-session/{id}              # Resume saved session
DELETE /api/wizard/saved-session/{id}             # Delete saved session
```

### Metadata & Legal Entities

```http
GET /api/countries
GET /api/purposes
GET /api/processes
GET /api/all-dropdown-values         # Includes legal entities, purpose of processing
GET /api/legal-entities              # Full country -> legal entities mapping
GET /api/legal-entities/{country}    # Legal entities for specific country
GET /api/purpose-of-processing       # Standard purposes list
GET /api/group-data-categories       # Group data categories from graph
GET /api/rules-overview-table        # Table data with filter params
```

### Agent Events (SSE)

```http
GET /api/agent-events/stream/{session_id}
Accept: text/event-stream
```

Events: `agent_started`, `agent_completed`, `agent_failed`, `phase_changed`, `analysis_progress`, `dictionary_progress`, `cypher_progress`, `validation_progress`, `workflow_complete`, `workflow_failed`

---

## Testing

### Running Tests

```bash
pytest tests/ -v
pytest tests/test_langgraph_workflow.py -v
pytest tests/ --cov=. --cov-report=html
```

### Test Files

| File | Coverage |
|------|----------|
| `test_langgraph_workflow.py` | Pydantic models, routing functions, workflow graph |
| `test_agentic_workflow.py` | Agent nodes (mocked), EventStore, API endpoints |
| `test_agent_audit.py` | AuditEventType, AuditEvent, EventStore thread safety |
| `test_rules_evaluation.py` | Country groups, rule structures, evaluator logic |
| `test_api.py` | Endpoint testing, request/response validation |
| `test_attribute_detection.py` | Health, financial, biometric data detection |

### Frontend Build Verification

```bash
cd frontend && npm run build
```

---

## Configuration

### Environment Variables

```bash
# Database
FALKORDB_HOST=localhost
FALKORDB_PORT=6379

# AI Service
ENABLE_AI_RULE_GENERATION=true
AI_TOKEN_API_URL=https://your-token-api/translate
AI_LLM_API_URL=https://your-llm-api/v1/chat/completions
AI_LLM_MODEL=o3-mini
AI_TOKEN_USERNAME=your_username
AI_TOKEN_PASSWORD=your_password

# Server
APP_PORT=5001
ENVIRONMENT=development
```

---

## Troubleshooting

### Common Issues

1. **"AI service is not enabled"**
   - Set `ENABLE_AI_RULE_GENERATION=true`
   - Check AI credentials are valid

2. **"Rule validation failed"**
   - Ensure `rule_id` starts with `RULE_`
   - Priority must be 1-100
   - `odrl_type` must match outcome (`Prohibition` <-> `prohibition`)

3. **Empty dropdowns in UI**
   - Ensure DataTransferGraph has data: `python main.py --upload-data sample_data.json`
   - Check database connection: `GET /health`

4. **Wizard stuck at step 3**
   - Check AI service credentials
   - View agent events SSE stream for errors
   - Check backend logs for AI request failures

5. **Sandbox evaluation returns errors**
   - Ensure sandbox was loaded (step 5) before testing
   - Check FalkorDB connection and temp graph creation

6. **Login not working**
   - Use `admin` / `admin` for full access or `user` / `user` for limited access
   - Auth state is stored in localStorage; clear browser storage if state is corrupted

7. **Admin pages not visible**
   - Policy Generator and Policy Editor require admin role
   - Log in with `admin` / `admin` credentials

---

## Contributing

1. Create a feature branch
2. Write tests for new functionality
3. Ensure all tests pass: `pytest tests/ -v`
4. Ensure frontend builds: `cd frontend && npm run build`
5. Submit a pull request

Follow existing code patterns and maintain Pydantic v2 compatibility.
