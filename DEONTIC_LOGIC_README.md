# Deontic Logic Implementation - Complete Guide

## Overview

The compliance system now uses a formal **Deontic Logic** framework with proper graph indexes and relationships:

```
Rule -[:HAS_ACTION]-> Action
Rule -[:HAS_PERMISSION]-> Permission
Permission -[:CAN_HAVE_DUTY]-> Duty
Rule -[:HAS_PROHIBITION]-> Prohibition
Prohibition -[:CAN_HAVE_DUTY]-> Duty
```

This structure aligns with formal policy languages like ODRL (Open Digital Rights Language) and provides clear separation between:
- **Actions**: What is being done
- **Permissions**: What is allowed (with duties/requirements)
- **Prohibitions**: What is blocked (with optional duties to get exceptions)
- **Duties**: Obligations that must be fulfilled

## Graph Structure

### Node Types

#### 1. Action Nodes
Represent the action being evaluated.

```cypher
(:Action {
  name: "Transfer Data",
  description: "Transfer data between jurisdictions"
})
```

**Available Actions:**
- **Transfer Data**: General data transfer between jurisdictions
- **Transfer PII**: Transfer personally identifiable information
- **Transfer Health Data**: Transfer health-related data
- **Store in Cloud**: Store or process data in cloud infrastructure

#### 2. Permission Nodes
Represent allowances with associated duties.

```cypher
(:Permission {
  name: "EU/EEA Internal Transfer",
  description: "Permission to transfer data within EU/EEA/UK/Crown/Switzerland"
})
```

**Available Permissions:**
- EU/EEA Internal Transfer
- EU to Adequacy Countries Transfer
- Crown Dependencies Transfer
- UK to Adequacy Transfer
- Switzerland Transfer
- EU/EEA to Rest of World Transfer
- BCR Countries Transfer
- PII Transfer

#### 3. Prohibition Nodes
Represent blocks/restrictions with optional exception duties.

```cypher
(:Prohibition {
  name: "US PII to Restricted Countries",
  description: "Prohibition on transferring PII from US to China, Hong Kong, Macao, Cuba, Iran, North Korea, Russia, Venezuela"
})
```

**Available Prohibitions:**
- **US PII to Restricted Countries**: Blocks PII transfers from US to sanctioned countries
- **US Data to China Cloud**: Blocks all US data from China cloud storage (absolute)
- **US Health Data Transfer**: Blocks health data transfers from US without approval

#### 4. Duty Nodes
Represent obligations that must be fulfilled.

```cypher
(:Duty {
  name: "Complete PIA Module (CM)",
  description: "Complete Privacy Impact Assessment with CM status",
  module: "pia_module",
  value: "CM"
})
```

**Available Duties:**
- **Complete PIA Module (CM)**: Privacy Impact Assessment
- **Complete TIA Module (CM)**: Transfer Impact Assessment
- **Complete HRPR Module (CM)**: Human Rights Privacy Review
- **Obtain US Legal Approval**: Get approval from US legal team
- **Obtain US Legal Exception**: Get legal exception for prohibited transfer

#### 5. Rule Nodes
Connect everything together.

```cypher
(:Rule {
  rule_id: "RULE_1",
  description: "EU/EEA/UK/Crown Dependencies/Switzerland internal transfer",
  priority: 1,
  origin_match_type: "ANY",
  receiving_match_type: "ANY",
  has_pii_required: false,
  health_data_required: false
})
```

### Relationships

```
Rule -[:HAS_ACTION]-> Action
  "RULE_1 performs Transfer Data"

Rule -[:HAS_PERMISSION]-> Permission
  "RULE_1 grants EU/EEA Internal Transfer permission"

Permission -[:CAN_HAVE_DUTY]-> Duty
  "EU/EEA Internal Transfer requires Complete PIA Module (CM)"

Rule -[:HAS_PROHIBITION]-> Prohibition
  "RULE_9 imposes US PII to Restricted Countries prohibition"

Prohibition -[:CAN_HAVE_DUTY]-> Duty
  "US PII to Restricted Countries requires Obtain US Legal Approval for exception"
```

### Indexes

All node types have indexes for fast lookups:
```cypher
CREATE INDEX FOR (cg:CountryGroup) ON (cg.name)
CREATE INDEX FOR (c:Country) ON (c.name)
CREATE INDEX FOR (r:Rule) ON (r.rule_id)
CREATE INDEX FOR (a:Action) ON (a.name)
CREATE INDEX FOR (p:Permission) ON (p.name)
CREATE INDEX FOR (pr:Prohibition) ON (pr.name)
CREATE INDEX FOR (d:Duty) ON (d.name)
```

## Complete Rule Set

### Permission Rules (RULE_1 to RULE_8)

#### RULE_1: EU/EEA Internal Transfer
```
Action: Transfer Data
Permission: EU/EEA Internal Transfer
Duties: Complete PIA Module (CM)
Applies: Within EU/EEA/UK/Crown/Switzerland
```

#### RULE_2: EU to Adequacy Countries
```
Action: Transfer Data
Permission: EU to Adequacy Countries Transfer
Duties: Complete PIA Module (CM)
Applies: EU/EEA → Adequacy decision countries
```

#### RULE_3: Crown Dependencies Transfer
```
Action: Transfer Data
Permission: Crown Dependencies Transfer
Duties: Complete PIA Module (CM)
Applies: Crown Dependencies → Adequacy + EU/EEA
```

#### RULE_4: UK to Adequacy Transfer
```
Action: Transfer Data
Permission: UK to Adequacy Transfer
Duties: Complete PIA Module (CM)
Applies: UK → Adequacy countries + EU/EEA
```

#### RULE_5: Switzerland Transfer
```
Action: Transfer Data
Permission: Switzerland Transfer
Duties: Complete PIA Module (CM)
Applies: Switzerland → Approved jurisdictions
```

#### RULE_6: EU/EEA to Rest of World
```
Action: Transfer Data
Permission: EU/EEA to Rest of World Transfer
Duties: Complete PIA Module (CM), Complete TIA Module (CM)
Applies: EU/EEA/Adequacy → Non-adequacy countries
```

#### RULE_7: BCR Countries Transfer
```
Action: Transfer Data
Permission: BCR Countries Transfer
Duties: Complete PIA Module (CM), Complete HRPR Module (CM)
Applies: BCR countries → Any jurisdiction
```

#### RULE_8: PII Transfer
```
Action: Transfer PII
Permission: PII Transfer
Duties: Complete PIA Module (CM)
Applies: Any transfer containing PII
```

### Prohibition Rules (RULE_9 to RULE_11)

#### RULE_9: US PII to Restricted Countries
```
Action: Transfer PII
Prohibition: US PII to Restricted Countries
Duties (for exception): Obtain US Legal Approval
Blocked Countries: China, Hong Kong, Macao, Cuba, Iran, North Korea, Russia, Venezuela
Status: BLOCKED (unless exception obtained)
```

#### RULE_10: US Data to China Cloud
```
Action: Store in Cloud
Prohibition: US Data to China Cloud
Duties (for exception): NONE (absolute prohibition)
Blocked Locations: China, Hong Kong, Macao
Status: BLOCKED (no exceptions)
```

#### RULE_11: US Health Data Transfer
```
Action: Transfer Health Data
Prohibition: US Health Data Transfer
Duties (for exception): Obtain US Legal Exception
Blocked: US health data → ANY destination
Status: BLOCKED (unless exception obtained)
```

## API Response Structure

### Permission Example (Ireland → Poland)

```json
{
  "success": true,
  "total_rules_triggered": 3,
  "has_prohibitions": false,
  "triggered_rules": [
    {
      "rule_id": "RULE_1",
      "description": "EU/EEA/UK/Crown Dependencies/Switzerland internal transfer",
      "priority": 1,
      "action": {
        "name": "Transfer Data",
        "description": "Transfer data between jurisdictions"
      },
      "permission": {
        "name": "EU/EEA Internal Transfer",
        "description": "Permission to transfer data within EU/EEA/UK/Crown/Switzerland",
        "duties": [
          {
            "name": "Complete PIA Module (CM)",
            "description": "Complete Privacy Impact Assessment with CM status",
            "module": "pia_module",
            "value": "CM"
          }
        ]
      },
      "prohibition": null,
      "is_blocked": false
    }
  ],
  "consolidated_duties": [
    {
      "name": "Complete PIA Module (CM)",
      "description": "Complete Privacy Impact Assessment with CM status",
      "module": "pia_module",
      "value": "CM"
    },
    {
      "name": "Complete HRPR Module (CM)",
      "description": "Complete Human Rights Privacy Review with CM status",
      "module": "hrpr_module",
      "value": "CM"
    }
  ]
}
```

### Prohibition Example (US → China with PII)

```json
{
  "success": true,
  "total_rules_triggered": 3,
  "has_prohibitions": true,
  "triggered_rules": [
    {
      "rule_id": "RULE_10",
      "description": "Data owned, created, developed, or maintained in US cannot be stored or processed in China cloud storage",
      "priority": 1,
      "action": {
        "name": "Store in Cloud",
        "description": "Store or process data in cloud infrastructure"
      },
      "permission": null,
      "prohibition": {
        "name": "US Data to China Cloud",
        "description": "Prohibition on storing/processing US data in China cloud storage",
        "duties": []
      },
      "is_blocked": true
    },
    {
      "rule_id": "RULE_9",
      "description": "US transfers of PII to restricted countries are PROHIBITED",
      "priority": 1,
      "action": {
        "name": "Transfer PII",
        "description": "Transfer personally identifiable information"
      },
      "permission": null,
      "prohibition": {
        "name": "US PII to Restricted Countries",
        "description": "Prohibition on transferring PII from US to China, Hong Kong, Macao, Cuba, Iran, North Korea, Russia, Venezuela",
        "duties": [
          {
            "name": "Obtain US Legal Approval",
            "description": "Obtain approval from US legal team before transfer",
            "module": null,
            "value": null
          }
        ]
      },
      "is_blocked": true
    },
    {
      "rule_id": "RULE_8",
      "description": "Transfer contains Personal Data (PII)",
      "priority": 8,
      "action": {
        "name": "Transfer PII",
        "description": "Transfer personally identifiable information"
      },
      "permission": {
        "name": "PII Transfer",
        "description": "Permission to transfer personal data (PII)",
        "duties": [
          {
            "name": "Complete PIA Module (CM)",
            "description": "Complete Privacy Impact Assessment with CM status",
            "module": "pia_module",
            "value": "CM"
          }
        ]
      },
      "prohibition": null,
      "is_blocked": false
    }
  ],
  "consolidated_duties": [
    {
      "name": "Obtain US Legal Approval",
      "description": "Obtain approval from US legal team before transfer",
      "module": null,
      "value": null
    },
    {
      "name": "Complete PIA Module (CM)",
      "description": "Complete Privacy Impact Assessment with CM status",
      "module": "pia_module",
      "value": "CM"
    }
  ]
}
```

## Database Statistics

```
Country Groups: 14
Countries: 88
Rules: 11
Actions: 4
Permissions: 8
Prohibitions: 3
Duties: 5
```

## Testing

### Test via Swagger UI
1. Open http://localhost:5001/docs
2. Navigate to "POST /api/evaluate-rules"
3. Click "Try it out"

**Test Cases:**

**Permission Test (Ireland → Poland):**
```json
{
  "origin_country": "Ireland",
  "receiving_country": "Poland",
  "has_pii": true
}
```
Expected: 3 permissions, 0 prohibitions

**Prohibition Test (US → China with PII):**
```json
{
  "origin_country": "United States",
  "receiving_country": "China",
  "has_pii": true
}
```
Expected: 1 permission, 2 prohibitions, `has_prohibitions: true`

**Health Data Test (US → Canada with health data):**
```json
{
  "origin_country": "United States",
  "receiving_country": "Canada",
  "has_health_data": true
}
```
Expected: 0 permissions, 1 prohibition (US Health Data Transfer)

### Test via curl

```bash
# Permission example
curl -X POST 'http://localhost:5001/api/evaluate-rules' \
  -H 'Content-Type: application/json' \
  -d '{
    "origin_country": "Ireland",
    "receiving_country": "Poland",
    "has_pii": true
  }'

# Prohibition example
curl -X POST 'http://localhost:5001/api/evaluate-rules' \
  -H 'Content-Type: application/json' \
  -d '{
    "origin_country": "United States",
    "receiving_country": "China",
    "has_pii": true
  }'

# Graph stats
curl http://localhost:5001/api/test-rules-graph
```

## Benefits of Deontic Logic Structure

### 1. Formal Policy Framework
- Aligns with standards like ODRL
- Clear separation of concerns
- Mathematically sound

### 2. Flexibility
- Easy to add new actions
- Permissions and prohibitions are independent
- Duties can be shared across rules

### 3. Queryability
- Fast indexed lookups
- Traverse from rule to duties in one query
- Clear relationships

### 4. Maintainability
- Each concept is a separate node type
- Changes to duties don't affect rules
- Reusable duty nodes

### 5. Extensibility
- Add new node types (Obligations, Dispensations)
- Support temporal constraints
- Add conditions and exceptions

## Cypher Query Examples

### Find all prohibitions
```cypher
MATCH (r:Rule)-[:HAS_PROHIBITION]->(pr:Prohibition)
RETURN r.rule_id, pr.name, pr.description
```

### Find all duties for a permission
```cypher
MATCH (p:Permission {name: "EU/EEA Internal Transfer"})-[:CAN_HAVE_DUTY]->(d:Duty)
RETURN d.name, d.description, d.module, d.value
```

### Find rules that block transfers
```cypher
MATCH (r:Rule)-[:HAS_PROHIBITION]->(pr:Prohibition)
RETURN r.rule_id, r.description, pr.name
ORDER BY r.priority
```

### Find all actions with their rules
```cypher
MATCH (r:Rule)-[:HAS_ACTION]->(a:Action)
RETURN a.name, collect(r.rule_id) as rules
```

## Migration from Previous Structure

**Old Structure:**
```python
{
  'rule_id': 'RULE_9',
  'blocked': True,
  'status': 'BLOCKED',
  'action': 'Only transfer with US legal approval',
  'requirements': {}
}
```

**New Structure:**
```python
{
  'rule_id': 'RULE_9',
  'action': {'name': 'Transfer PII', 'description': '...'},
  'prohibition': {
    'name': 'US PII to Restricted Countries',
    'description': '...',
    'duties': [{'name': 'Obtain US Legal Approval', ...}]
  },
  'is_blocked': True
}
```

## Server Access

- **Main Dashboard:** http://localhost:5001/
- **Swagger UI:** http://localhost:5001/docs
- **ReDoc:** http://localhost:5001/redoc
- **Test Endpoint:** http://localhost:5001/api/test-rules-graph

## Files

- **build_rules_graph_deontic.py**: Builds deontic graph structure
- **api_fastapi_deontic.py**: FastAPI server with deontic logic
- **DEONTIC_LOGIC_README.md**: This file

## Future Enhancements

1. **Temporal Duties**: Time-based obligations
2. **Conditional Permissions**: Permissions that depend on runtime conditions
3. **Delegations**: Transfer of permissions/duties
4. **Dispensations**: Temporary exemptions from prohibitions
5. **Obligations vs Duties**: Separate proactive vs reactive requirements
6. **Sanctions**: Consequences of duty non-fulfillment

## Conclusion

The deontic logic structure provides a formal, flexible, and maintainable framework for expressing complex compliance rules. The indexed graph structure ensures fast queries while maintaining clear semantics for policy reasoning.
