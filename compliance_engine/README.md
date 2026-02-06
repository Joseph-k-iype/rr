# Compliance Engine v5.0.0

A scalable, production-ready compliance engine for cross-border data transfer evaluation using graph-based rules and AI-powered rule generation.

## Architecture Overview

```
compliance_engine/
├── api/                    # FastAPI application
│   └── main.py            # API endpoints
├── agents/                 # AI agents
│   ├── ai_service.py      # JWT authentication & LLM calls
│   └── rule_generator.py  # AI rule generation
├── config/                 # Configuration
│   ├── settings.py        # Global settings (env-based)
│   ├── health_data_config.json
│   └── metadata_detection_config.json
├── models/                 # Pydantic models
│   └── schemas.py         # Request/response schemas
├── rules/                  # Rule definitions
│   ├── dictionaries/      # Developer-editable rules
│   │   ├── country_groups.py
│   │   └── rules_definitions.py
│   └── templates/         # Cypher query templates
│       └── cypher_templates.py
├── services/              # Core services
│   ├── database.py        # FalkorDB connection
│   ├── cache.py           # LRU cache with TTL
│   ├── attribute_detector.py  # Metadata detection
│   └── rules_evaluator.py # Main evaluation engine
├── utils/                 # Utilities
│   ├── graph_builder.py   # Build RulesGraph
│   └── data_uploader.py   # Upload case data
├── tests/                 # Test suite
├── templates/             # HTML templates
├── static/                # Static assets
└── main.py               # Entry point
```

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Environment

Copy `.env.example` to `.env` and update:

```bash
cp .env.example .env
# Edit .env with your settings
```

### 3. Build Rules Graph

```bash
python main.py --build-graph
```

### 4. Upload Sample Data (optional)

```bash
python main.py --upload-data ../sample_data.json --clear-data
```

### 5. Run the Server

```bash
python main.py
```

Access:
- Dashboard: http://localhost:5001/
- API Docs: http://localhost:5001/docs
- Rules Overview: http://localhost:5001/rules

## Two Sets of Rules

### SET 1: Case-Matching Rules

These rules search for historical cases that match parameters. If at least one case matches with completed assessments, transfer is **ALLOWED**.

**How it works:**
1. User provides origin country, receiving country, PII flag, purposes, etc.
2. System finds applicable rules based on country groups
3. System searches for precedent cases matching the criteria
4. If a compliant case exists (with required assessments completed), transfer is allowed

**Defined in:** `rules/dictionaries/rules_definitions.py` → `CASE_MATCHING_RULES`

Example:
```python
"RULE_1_EU_INTERNAL": CaseMatchingRule(
    rule_id="RULE_1",
    name="EU/EEA/UK/Crown/Switzerland Internal Transfers",
    origin_group="EU_EEA_UK_CROWN_CH",
    receiving_group="EU_EEA_UK_CROWN_CH",
    required_assessments=RequiredAssessments(pia_required=True),
)
```

### SET 2A: Transfer Rules

Country-to-country transfer permissions/prohibitions that take **highest priority**.

**Defined in:** `rules/dictionaries/rules_definitions.py` → `TRANSFER_RULES`

Example:
```python
"RULE_9_US_RESTRICTED_PII": TransferRule(
    rule_id="RULE_9",
    name="US PII to Restricted Countries",
    transfer_pairs=[
        ("United States", "China"),
        ("United States", "Russia"),
        # ...
    ],
    outcome=RuleOutcome.PROHIBITION,
    requires_pii=True,
)
```

### SET 2B: Attribute Rules

Rules based on specific data attributes (health, financial, biometric, etc.).

**Defined in:** `rules/dictionaries/rules_definitions.py` → `ATTRIBUTE_RULES`

Example:
```python
"RULE_11_US_HEALTH": AttributeRule(
    rule_id="RULE_11",
    name="US Health Data Transfer",
    attribute_name="health_data",
    attribute_config_file="health_data_config.json",
    origin_countries=frozenset({"United States"}),
    outcome=RuleOutcome.PROHIBITION,
)
```

## Adding New Rules

### Adding a Country Group

Edit `rules/dictionaries/country_groups.py`:

```python
MY_NEW_GROUP: FrozenSet[str] = frozenset({
    "Country1", "Country2", "Country3"
})

# Add to registry
COUNTRY_GROUPS["MY_NEW_GROUP"] = MY_NEW_GROUP
```

### Adding a Transfer Rule

Edit `rules/dictionaries/rules_definitions.py`:

```python
TRANSFER_RULES["MY_NEW_RULE"] = TransferRule(
    rule_id="RULE_MY_01",
    name="My New Transfer Rule",
    description="Description of the rule",
    priority=5,  # Lower = higher priority
    origin_group="EU_EEA",
    receiving_countries=frozenset({"SomeCountry"}),
    outcome=RuleOutcome.PROHIBITION,
    requires_pii=True,
    required_actions=["Get Legal Approval"],
)
```

### Adding an Attribute Rule

Edit `rules/dictionaries/rules_definitions.py`:

```python
ATTRIBUTE_RULES["MY_ATTRIBUTE_RULE"] = AttributeRule(
    rule_id="RULE_ATTR_01",
    name="My Attribute Rule",
    attribute_name="my_data_type",
    attribute_keywords=["keyword1", "keyword2"],
    origin_countries=frozenset({"Country1"}),
    outcome=RuleOutcome.PROHIBITION,
)
```

Then add detection config in `config/metadata_detection_config.json`.

### Rebuilding After Changes

```bash
python main.py --build-graph
```

## AI Rule Generation

### Configuration

Set up AI credentials in `.env`:

```env
AI_TOKEN_API_URL=https://your-token-api/translate
AI_TOKEN_USERNAME=your_username
AI_TOKEN_PASSWORD=your_password
AI_LLM_API_URL=https://your-llm-api/chat/completions
AI_LLM_MODEL=gpt-4.1
ENABLE_AI_RULE_GENERATION=true
```

### Using AI to Generate Rules

Via API:
```bash
curl -X POST http://localhost:5001/api/ai/generate-rule \
  -H "Content-Type: application/json" \
  -d '{
    "rule_text": "Personal health data from the United States should not be transferred to China",
    "rule_country": "United States",
    "rule_type": "attribute",
    "test_in_temp_graph": true
  }'
```

Via Dashboard:
1. Go to http://localhost:5001/
2. Enter rule text in the AI Rule Generation section
3. Click "Generate Rule"
4. Review generated dictionary and Cypher query
5. Add to `rules_definitions.py` if approved

## API Endpoints

### Evaluation
- `POST /api/evaluate-rules` - Evaluate transfer compliance
- `POST /api/search-cases` - Search historical cases

### Rules
- `GET /api/rules-overview` - Get all rules overview
- `GET /api/cypher-templates` - Get available Cypher templates

### AI
- `POST /api/ai/generate-rule` - Generate rule from text
- `GET /api/ai/status` - Check AI service status

### Metadata
- `GET /api/countries` - List countries
- `GET /api/purposes` - List purposes
- `GET /api/processes` - List processes
- `GET /api/all-dropdown-values` - All dropdown values

### Admin
- `GET /health` - Health check
- `GET /api/stats` - Dashboard statistics
- `GET /api/cache/clear` - Clear cache
- `GET /api/cache/stats` - Cache statistics

## Testing

Run tests:
```bash
python main.py --test
```

Or directly:
```bash
pytest tests/ -v
```

## Configuration Reference

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `FALKORDB_HOST` | localhost | FalkorDB host |
| `FALKORDB_PORT` | 6379 | FalkorDB port |
| `API_PORT` | 5001 | API server port |
| `LOG_LEVEL` | INFO | Logging level |
| `ENABLE_CACHE` | true | Enable caching |
| `CACHE_TTL` | 300 | Cache TTL in seconds |
| `ENABLE_AI_RULE_GENERATION` | true | Enable AI features |

See `.env.example` for complete list.

## Production Deployment

1. Set `ENVIRONMENT=production` in `.env`
2. Configure `API_WORKERS` for your server (default: 4)
3. Set up a reverse proxy (nginx, Traefik, etc.)
4. Use a process manager (systemd, supervisord)
5. Enable HTTPS

Example systemd service:
```ini
[Unit]
Description=Compliance Engine
After=network.target

[Service]
User=app
WorkingDirectory=/path/to/compliance_engine
ExecStart=/path/to/venv/bin/python main.py
Restart=always

[Install]
WantedBy=multi-user.target
```

## License

Internal use only.
