# US Blocking Rules - Implementation Guide

## Overview

Added 3 new compliance rules to the RulesGraph that automatically BLOCK certain data transfers from the United States. These rules are enforced at the highest priority and show clear blocking status in the UI.

## Rules Added

### RULE_9: US to Restricted Countries (PII Block)
**Description:** US transfers of PII to restricted countries are PROHIBITED

**Restricted Countries:**
- China
- Hong Kong
- Macao/Macau
- Cuba
- Iran
- North Korea
- Russia
- Venezuela

**Conditions:**
- Origin: United States
- Receiving: Any restricted country above
- Data: Must contain PII (Personal Identifiable Information)

**Status:** BLOCKED
**Action Required:** Only transfer with US legal approval
**Priority:** 1 (Highest)

**Example:**
```json
Request: US → China with PII
Response: BLOCKED - "Only transfer with US legal approval"
```

### RULE_10: US Data Sovereignty (China Cloud Block)
**Description:** Data owned, created, developed, or maintained in US cannot be stored or processed in China cloud storage

**Blocked Storage Locations:**
- China
- Hong Kong
- Macao/Macau

**Conditions:**
- Origin: United States
- Receiving: China or its territories
- Data: ALL data (not just PII)

**Status:** BLOCKED
**Action Required:** Prohibited - no exceptions
**Priority:** 1 (Highest)

**Example:**
```json
Request: US → China (any data)
Response: BLOCKED - "Prohibited - no exceptions"
```

### RULE_11: US Health Data Transfer Block
**Description:** Transfer of health-related data from US is PROHIBITED without US legal approval

**Health Data Detection:**
Automatically detects health data by checking for keywords in personal data categories:
- health, medical, patient, diagnosis, treatment, prescription
- clinical, hospital, doctor, disease, illness, medication
- healthcare, wellness, fitness, biometric, genetic

**Conditions:**
- Origin: United States
- Receiving: ANY country (worldwide)
- Data: Contains health-related information

**Status:** BLOCKED
**Action Required:** Obtain exception from US legal team
**Priority:** 1 (Highest)

**Example:**
```json
Request: US → Canada with health data
Response: BLOCKED - "Obtain exception from US legal team"
```

## How It Works

### 1. Automatic Detection
The system automatically detects:
- **PII:** Based on personal_data fields in cases
- **Health Data:** Scans personal_data and personal_data_categories for health-related keywords
- **Geographic Restrictions:** Checks origin and receiving countries against rule groups

### 2. Rule Evaluation Flow
```
1. User searches for cases (e.g., US → China)
2. System retrieves matching cases from DataTransferGraph
3. System detects if cases contain PII or health data
4. System queries RulesGraph with detected flags
5. Blocking rules are triggered if conditions match
6. UI displays BLOCKED status prominently in red
```

### 3. User Experience
**No changes to user input required:**
- Users search as normal (origin, receiving, filters)
- System automatically detects sensitive data
- Blocking rules trigger automatically
- Clear warnings shown in UI

## API Testing

### Test RULE_9 (US → China with PII)
```bash
curl -X POST 'http://localhost:5001/api/evaluate-rules' \
  -H 'Content-Type: application/json' \
  -d '{
    "origin_country": "United States",
    "receiving_country": "China",
    "has_pii": true
  }'
```

**Expected Result:**
- RULE_9: BLOCKED - "Only transfer with US legal approval"
- RULE_10: BLOCKED - "Prohibited - no exceptions"
- RULE_8: ALLOWED - General PII requirements

### Test RULE_10 (US → China without PII)
```bash
curl -X POST 'http://localhost:5001/api/evaluate-rules' \
  -H 'Content-Type: application/json' \
  -d '{
    "origin_country": "United States",
    "receiving_country": "China",
    "has_pii": false
  }'
```

**Expected Result:**
- RULE_10: BLOCKED - "Prohibited - no exceptions"

### Test RULE_11 (US → Any with Health Data)
```bash
curl -X POST 'http://localhost:5001/api/evaluate-rules' \
  -H 'Content-Type: application/json' \
  -d '{
    "origin_country": "United States",
    "receiving_country": "Canada",
    "has_health_data": true
  }'
```

**Expected Result:**
- RULE_11: BLOCKED - "Obtain exception from US legal team"

## UI Display

### Blocked Rules Section
When blocking rules are triggered, the UI shows:

1. **Warning Banner (Yellow/Orange):**
   ```
   ⚠️ TRANSFER BLOCKED: X rule(s) prohibit this transfer.
   See action required below.
   ```

2. **Rules Table:**
   - Rule ID in first column
   - **BLOCKED** badge in red
   - Full description
   - Action required (e.g., "Obtain US legal approval")
   - Requirements column (empty for blocking rules)

3. **Row Highlighting:**
   - Blocked rules have red background
   - Red left border for emphasis
   - Bold red text

### Cases with Health Data
When health data is detected in cases:

1. **Warning Banner:**
   ```
   ⚠️ Health Data Detected: One or more cases contain health-related data.
   Check compliance rules above for restrictions.
   ```

2. **Cases Table:**
   - New "Health" column
   - ⚕️ icon for cases with health data
   - Red "Yes" text for health data cases

## Technical Implementation

### Graph Structure
```cypher
// Rule node properties
(:Rule {
  rule_id: "RULE_9",
  description: "...",
  priority: 1,
  blocked: true,                    // NEW: Indicates blocking rule
  status: "BLOCKED",                // NEW: BLOCKED or ALLOWED_WITH_REQUIREMENTS
  action: "Only transfer with...",  // NEW: Action required
  health_data_required: false,      // NEW: For health data rules
  origin_match_type: "ANY",
  receiving_match_type: "ANY",
  has_pii_required: true
})

// Country groups
(:CountryGroup {name: "US"})
(:CountryGroup {name: "US_RESTRICTED_COUNTRIES"})
(:CountryGroup {name: "CHINA_CLOUD"})

// Relationships
(:Rule)-[:TRIGGERED_BY_ORIGIN]->(:CountryGroup {name: "US"})
(:Rule)-[:TRIGGERED_BY_RECEIVING]->(:CountryGroup {name: "US_RESTRICTED_COUNTRIES"})
```

### API Response Structure
```json
{
  "success": true,
  "triggered_rules": [
    {
      "rule_id": "RULE_9",
      "description": "US transfers of PII to restricted countries...",
      "priority": 1,
      "blocked": true,
      "status": "BLOCKED",
      "action": "Only transfer with US legal approval",
      "requirements": {}
    }
  ],
  "requirements": {},
  "total_rules_triggered": 1
}
```

### Health Data Detection Function
```python
def contains_health_data(personal_data: List[str],
                        personal_data_categories: List[str]) -> bool:
    health_keywords = [
        'health', 'medical', 'patient', 'diagnosis', 'treatment',
        'prescription', 'clinical', 'hospital', 'doctor', 'disease',
        'illness', 'medication', 'healthcare', 'wellness', 'fitness',
        'biometric', 'genetic'
    ]

    all_data = personal_data + personal_data_categories
    all_data_lower = [item.lower() for item in all_data if item]

    return any(keyword in data_item
               for keyword in health_keywords
               for data_item in all_data_lower)
```

## Database Status

✅ **RulesGraph Updated:**
- Total Rules: 11 (was 8)
- Country Groups: 14 (added 3 US-related groups)
- Countries: 88 (added US and variants)

✅ **New Country Groups:**
- `US`: United States, United States of America, USA
- `US_RESTRICTED_COUNTRIES`: China, Hong Kong, Macao, Cuba, Iran, North Korea, Russia, Venezuela
- `CHINA_CLOUD`: China, Hong Kong, Macao

## Verification

### All Rules Working
```bash
# Existing rules (Ireland → Poland)
curl -X POST 'http://localhost:5001/api/evaluate-rules' \
  -H 'Content-Type: application/json' \
  -d '{"origin_country": "Ireland", "receiving_country": "Poland", "has_pii": true}'

# Result: 3 rules triggered (RULE_1, RULE_7, RULE_8) - ALL ALLOWED
```

### New Rules Working
```bash
# US → China with PII
# Result: RULE_9 and RULE_10 BLOCKED, RULE_8 ALLOWED

# US → China without PII
# Result: RULE_10 BLOCKED

# US → Canada with health data
# Result: RULE_11 BLOCKED
```

## Dashboard Access

- **Main Dashboard:** http://localhost:5001/
- **Swagger UI:** http://localhost:5001/docs
- **ReDoc:** http://localhost:5001/redoc

## Key Features

✅ **No User Input Changes:** System detects sensitive data automatically
✅ **Automatic Detection:** PII and health data detected from cases
✅ **Clear UI Warnings:** Red badges and banners for blocked transfers
✅ **Action Guidance:** Each blocked rule shows required action
✅ **Priority Enforcement:** Blocking rules have highest priority (1)
✅ **Complete API Documentation:** Test all rules in Swagger UI
✅ **Backward Compatible:** All existing rules continue to work

## Next Steps

1. **Test in Swagger UI:** http://localhost:5001/docs
2. **Try Dynamic Dashboard:** http://localhost:5001/
3. **Test US Blocking Scenarios:**
   - US → China (any data)
   - US → Russia (with PII)
   - US → Canada (with health data)
4. **Verify Existing Rules:** Ireland → Poland still works
5. **Check Health Data Detection:** Add health-related data to test cases

## Notes

- Blocking rules have **no technical requirements** (requirements: {})
- They are **policy-level blocks** that cannot be bypassed without legal approval
- Health data detection uses **keyword matching** in personal data fields
- User input remains the same - all detection is automatic
- Rules can be tested independently via Swagger UI
