# Developer Guide

## Quick Start

### Adding a New Prohibition Rule

**Step 1**: Edit `prohibition_rules_config.json`

```json
{
  "prohibition_rules": {
    "MY_NEW_RULE": {
      "enabled": true,
      "rule_id": "RULE_CUSTOM_1",
      "priority": 5,
      "origin_countries": ["Germany", "France"],
      "receiving_countries": ["Russia"],
      "bidirectional": false,
      "requires_pii": false,
      "requires_health_data": false,
      "prohibition_name": "EU to Russia Block",
      "prohibition_description": "Blocks data transfers from EU to Russia",
      "action_name": "Transfer Data",
      "duties": [],
      "odrl_type": "Prohibition",
      "odrl_action": "transfer",
      "odrl_target": "Data"
    }
  }
}
```

**Step 2**: Rebuild the graph

```bash
python build_rules_graph_deontic.py
```

**Step 3**: Restart the API

```bash
python api_fastapi_deontic.py
```

**Done!** No Python code changes needed.

---

## Configuration Reference

### Prohibition Rule Fields

| Field | Type | Description | Required | Example |
|-------|------|-------------|----------|---------|
| `enabled` | boolean | Turn rule on/off | Yes | `true` |
| `rule_id` | string | Unique identifier | Yes | `"RULE_CUSTOM_1"` |
| `priority` | number | 1 = highest priority | Yes | `5` |
| `origin_countries` | array | List of origins | Yes | `["Germany", "France"]` |
| `receiving_countries` | array | List of destinations or `["ANY"]` | Yes | `["Russia"]` |
| `bidirectional` | boolean | Create reverse rule | No | `false` |
| `requires_pii` | boolean | Only trigger if PII present | No | `false` |
| `requires_health_data` | boolean | Only trigger if health data | No | `false` |
| `prohibition_name` | string | Display name | Yes | `"EU to Russia Block"` |
| `prohibition_description` | string | Full description | Yes | `"Blocks..."` |
| `action_name` | string | Action being prohibited | Yes | `"Transfer Data"` |
| `duties` | array | Required duties (can be empty) | Yes | `[]` |

### Special Keywords

- **`["ANY"]`** in `receiving_countries`: Matches any destination
- **`bidirectional: true`**: Creates rules for both A→B and B→A
- **Priority**: Lower number = higher priority (1 = absolute highest)

---

## Adding Metadata Detection

### Step 1: Edit `metadata_detection_config.json`

```json
{
  "detection_categories": {
    "financial_data": {
      "enabled": true,
      "description": "Detects financial data",
      "detection_type": "keyword_and_pattern",
      "keywords": [
        "credit card",
        "bank account",
        "swift",
        "iban"
      ],
      "patterns": [
        "\\d{4}[\\s-]?\\d{4}[\\s-]?\\d{4}[\\s-]?\\d{4}",
        "cvv[:\\s]?\\d{3,4}"
      ],
      "case_sensitive": false,
      "word_boundaries": true,
      "normalize_underscores": true,
      "normalize_hyphens": true
    }
  }
}
```

### Step 2: Restart API

```bash
python api_fastapi_deontic.py
```

**Note**: Metadata detection changes don't require graph rebuild!

---

## Examples

### Example 1: Block Specific Country Pair

```json
{
  "BLOCK_UK_TO_CHINA": {
    "enabled": true,
    "rule_id": "RULE_UK_CHINA",
    "priority": 4,
    "origin_countries": ["United Kingdom"],
    "receiving_countries": ["China"],
    "prohibition_name": "UK to China Block",
    ...
  }
}
```

### Example 2: PII-Only Prohibition

```json
{
  "BLOCK_PII_TO_NON_ADEQUACY": {
    "enabled": true,
    "requires_pii": true,
    "origin_countries": ["Germany"],
    "receiving_countries": ["India", "Brazil"],
    ...
  }
}
```

### Example 3: Bidirectional Rule

```json
{
  "MUTUAL_RESTRICTION": {
    "enabled": true,
    "bidirectional": true,
    "origin_countries": ["Country A"],
    "receiving_countries": ["Country B"],
    ...
  }
}
```

This creates TWO rules:
- Country A → Country B (prohibited)
- Country B → Country A (prohibited)

---

## Testing

### Via Swagger UI

1. Go to http://localhost:5001/docs
2. Try POST `/api/evaluate-rules`
3. Enter test data:

```json
{
  "origin_country": "Germany",
  "receiving_country": "Russia",
  "pia_status": "Completed"
}
```

4. Check response for your new prohibition rule

### Via cURL

```bash
curl -X POST http://localhost:5001/api/evaluate-rules \
  -H "Content-Type: application/json" \
  -d '{
    "origin_country": "Germany",
    "receiving_country": "Russia",
    "pia_status": "Completed"
  }'
```

---

## Troubleshooting

### Rule Not Loading

**Checklist**:
- [ ] Is `"enabled": true`?
- [ ] Did you rebuild the graph?
- [ ] Is the JSON valid? Run: `python -m json.tool < prohibition_rules_config.json`
- [ ] Check logs for errors

### Encoding Errors

All files use UTF-8. If you see encoding errors:

```python
# All Python files have:
# -*- coding: utf-8 -*-

# All file operations use:
with open('file.json', 'r', encoding='utf-8') as f:
    data = json.load(f)
```

### Graph Build Fails

Check logs:
```bash
python build_rules_graph_deontic.py 2>&1 | grep "ERROR"
```

Common issues:
- Invalid JSON syntax
- Missing required fields
- Duplicate `rule_id`

---

## Advanced Topics

### Custom Metadata Detection

To add custom detection logic:

1. Add category to `metadata_detection_config.json`
2. Create detection function in `api_fastapi_deontic.py`:

```python
def detect_your_data_type(metadata):
    # Your logic here
    return {'detected': True, ...}
```

3. Call from `/api/evaluate-rules` endpoint

### Custom Permission Rules

Edit `build_rules_graph_deontic.py` directly:

```python
{
    'rule_id': 'RULE_CUSTOM_PERM',
    'priority': 11,
    'origin_groups': ['YOUR_GROUP'],
    'receiving_groups': ['DEST_GROUP'],
    'permission': 'Your Permission Name',
    ...
}
```

Then rebuild the graph.

---

## Best Practices

### Naming Conventions

- **Rule IDs**: `RULE_DESCRIPTIVE_NAME` or `RULE_CUSTOM_1`
- **Groups**: Use UPPERCASE_WITH_UNDERSCORES
- **Priorities**: Reserve 1-3 for absolute prohibitions, 4-10 for others

### Testing Strategy

1. **Unit Test**: Test rule in isolation via API
2. **Integration Test**: Test with real historical data
3. **Precedent Check**: Ensure rule doesn't break existing cases

### Version Control

Always commit both:
- Configuration files (`*.json`)
- Graph rebuild confirmation (check-in logs or test results)

---

## FAQ

**Q: Can I have multiple prohibition rules for the same country pair?**

A: Yes! Use different priorities and conditions (`requires_pii`, `requires_health_data`)

**Q: How do I disable a rule temporarily?**

A: Set `"enabled": false` in config, then rebuild graph

**Q: What happens if two rules conflict?**

A: Lower priority number wins (priority 1 > priority 2)

**Q: Can I use Unicode country names?**

A: Yes! España, Türkiye, 中国, 日本, etc. all supported

---

---

## Graph Queries Explained

This section details the key Cypher queries used by the API to evaluate rules and search for precedents.

### 1. Rule Evaluation Query (`query_triggered_rules_deontic`)

This query determines which permissions or prohibitions apply to a given transfer.

**Logic:**
1. **Match Groups**: Identifies all country groups for the Origin and Receiving countries.
2. **Match Rules**: Finds all potentially relevant rules.
3. **Filter**: Checks if the rule applies based on:
   - **Origin Match**: Does the rule's origin group match the transfer's origin?
   - **Receiving Match**: Does the rule's receiving group match the transfer's destination?
   - **Conditions**: Check `pii` and `health_data` requirements.
4. **Collect**: Retrieves associated Actions, Permissions, Prohibitions, and Duties.

```cypher
MATCH (origin:Country {name: $origin_country})-[:BELONGS_TO]->(origin_group:CountryGroup)
WITH collect(DISTINCT origin_group.name) as origin_groups

MATCH (receiving:Country {name: $receiving_country})-[:BELONGS_TO]->(receiving_group:CountryGroup)
WITH origin_groups, collect(DISTINCT receiving_group.name) as receiving_groups

MATCH (r:Rule)
OPTIONAL MATCH (r)-[:TRIGGERED_BY_ORIGIN]->(r_origin:CountryGroup)
WITH r, origin_groups, receiving_groups, collect(DISTINCT r_origin.name) as rule_origin_groups

OPTIONAL MATCH (r)-[:TRIGGERED_BY_RECEIVING]->(r_receiving:CountryGroup)
WITH r, origin_groups, receiving_groups, rule_origin_groups,
     collect(DISTINCT r_receiving.name) as rule_receiving_groups

// Dynamic matching logic using CASE statement
WITH r, origin_groups, receiving_groups, rule_origin_groups, rule_receiving_groups,
     CASE
         WHEN r.origin_match_type = 'ALL' THEN true
         WHEN r.origin_match_type = 'ANY' THEN any(g IN origin_groups WHERE g IN rule_origin_groups)
         ELSE false
     END as origin_matches,
     CASE
         WHEN r.receiving_match_type = 'ALL' THEN true
         WHEN r.receiving_match_type = 'ANY' THEN any(g IN receiving_groups WHERE g IN rule_receiving_groups)
         WHEN r.receiving_match_type = 'NOT_IN' THEN NOT any(g IN receiving_groups WHERE g IN rule_receiving_groups)
         ELSE false
     END as receiving_matches

WHERE origin_matches AND receiving_matches
      AND (NOT r.has_pii_required OR $has_pii = true)
      AND (NOT r.health_data_required OR $has_health_data = true)

// Retrieve graph Deontic structure
OPTIONAL MATCH (r)-[:HAS_ACTION]->(action:Action)
OPTIONAL MATCH (r)-[:HAS_PERMISSION]->(perm:Permission)
OPTIONAL MATCH (perm)-[:CAN_HAVE_DUTY]->(perm_duty:Duty)
OPTIONAL MATCH (r)-[:HAS_PROHIBITION]->(prohib:Prohibition)
OPTIONAL MATCH (prohib)-[:CAN_HAVE_DUTY]->(prohib_duty:Duty)

RETURN r, action, perm, collect(perm_duty), prohib, collect(prohib_duty)
ORDER BY r.priority
```

### 2. Strict Precedent Search (`search_data_graph_strict`)

Matches the current transfer request against historical cases to find exact matches.

**Logic:**
- **Exact Match**: Origin, Receiving, Process Levels (L1-L3), and Purposes must ALL match.
- **Valid Status**: Only searches `Completed`, `Complete`, `Active`, or `Published` cases.
- **PII Check**: If PII is present, ensures the historical case also involved PII.

```cypher
MATCH (c:Case)-[:ORIGINATES_FROM]->(origin:Country)
MATCH (c)-[:TRANSFERS_TO]->(receiving:Jurisdiction)
WHERE origin.name = $origin 
  AND receiving.name = $receiving
  AND c.case_status IN ['Completed', 'Complete', 'Active', 'Published']

// Purpose Filtering
WITH c
MATCH (c)-[:HAS_PURPOSE]->(purpose:Purpose)
WITH c, collect(DISTINCT purpose.name) as case_purposes
WHERE ALL(p IN $purposes WHERE p IN case_purposes)

// Process Filtering (Dynamic)
MATCH (c)-[:HAS_PROCESS_L1]->(p1:ProcessL1 {name: $process_l1})
// ... (matches L2 and L3 similarly)

RETURN c
```

### 3. UI Case Search (`search_data_graph`)

Used by the "Search Cases" page. Supports partial string matching and optional filters.

**Logic:**
- **Partial Match**: Uses `CONTAINS` for country names.
- **Optional Filters**: Only applies filters (Purpose, Process) if they are selected in the UI.

```cypher
MATCH (c:Case)-[:ORIGINATES_FROM]->(origin:Country)
MATCH (c)-[:TRANSFERS_TO]->(receiving:Jurisdiction)
WHERE toLower(origin.name) CONTAINS toLower($origin)
  AND toLower(receiving.name) CONTAINS toLower($receiving)
  AND c.case_status IN ['Completed', 'Complete', 'Active', 'Published']
RETURN c
```

### 4. Metadata Queries

These queries populate dropdowns and filter lists.

- **Countries**: `MATCH (c:Country) RETURN DISTINCT c.name` (and `Jurisdiction` for receiving)
- **Purposes**: `MATCH (p:Purpose) RETURN DISTINCT p.name`
- **Processes**: `MATCH (p:ProcessL1) RETURN DISTINCT p.name`

---

## Support

- **Architecture**: See README.md
- **API Documentation**: http://localhost:5001/docs
- **Graph Query Examples**: See `build_rules_graph_deontic.py`

---

**Happy coding!** 🚀
