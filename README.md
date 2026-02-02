# Data Transfer Compliance System

**Version:** 3.0.0
**Status:** ✅ Production Ready
**Last Updated:** 2026-02-02

---

## 📚 Documentation Index

| Document | Description | Audience |
|----------|-------------|----------|
| **[ARCHITECTURE.md](ARCHITECTURE.md)** | Complete system architecture with Mermaid diagrams, graph schemas, and logic flows | Technical/Architects |
| **[FIXES_SUMMARY.md](FIXES_SUMMARY.md)** | All logical errors fixed, ODRL alignment, test results | Technical/QA |
| **[API_REDESIGN_SUMMARY.md](API_REDESIGN_SUMMARY.md)** | User-friendly API redesign, parameter structure, examples | Developers/Integrators |
| **[HEALTH_DETECTION_SOLUTION.md](HEALTH_DETECTION_SOLUTION.md)** | Health data detection implementation, 244 keywords, configuration | Technical/Compliance |
| **[QUICK_START.md](QUICK_START.md)** | Getting started guide, quick tests, common scenarios | All Users |
| **[health_data_config.json](health_data_config.json)** | Comprehensive health data detection configuration | Configuration |

---

## 🎯 Quick Overview

### What is This System?

A **graph-based compliance engine** that evaluates data transfer regulations using:
- **Deontic Logic** (Permissions, Prohibitions, Duties)
- **ODRL** (Open Digital Rights Language) compliance
- **Graph Database** (FalkorDB) for flexible rule storage
- **Automatic Health Data Detection** (244 keywords)
- **Priority-Based Rule Evaluation** (deterministic results)

### Use Cases

1. **Compliance Checking**: Evaluate if a data transfer complies with regulations
2. **Rule Discovery**: Find which rules apply to specific transfers
3. **Duty Identification**: Determine required obligations (PIA, TIA, legal approval)
4. **Health Data Detection**: Automatically identify health-related transfers
5. **Historical Search**: Find similar past transfer cases

---

## 🚀 Quick Start

### Prerequisites
```bash
# Required
- Python 3.8+
- Redis (for FalkorDB)
- FalkorDB module installed

# Install dependencies
pip install fastapi uvicorn falkordb pydantic
```

### 1. Build the Graph
```bash
cd "/Users/josephkiype/Desktop/development/code/deterministic policy"
python build_rules_graph_deontic.py
```

### 2. Start the API
```bash
uvicorn api_fastapi_deontic:app --reload --port 8000
```

### 3. Open Dashboard
```
http://localhost:8000
```

### 4. Run Tests
```bash
# Basic API tests
python test_new_api.py

# Health detection tests
python test_health_detection.py
```

---

## 📊 System Statistics

### RulesGraph
- **Countries**: 87
- **Country Groups**: 14
- **Rules**: 11 (3 prohibitions, 8 permissions)
- **Actions**: 4
- **Duties**: 5
- **Keywords**: 244 health-related terms

### Rules Breakdown

| Priority | Rule ID | Type | Description |
|----------|---------|------|-------------|
| 1 | RULE_10 | 🔴 Prohibition | US Data to China Cloud |
| 1 | RULE_1 | ✅ Permission | EU/EEA Internal Transfer |
| 2 | RULE_9 | 🔴 Prohibition | US PII to Restricted Countries |
| 3 | RULE_11 | 🔴 Prohibition | US Health Data Transfer |
| 4 | RULE_2 | ✅ Permission | EU to Adequacy Countries |
| 5 | RULE_3 | ✅ Permission | Crown Dependencies |
| 6 | RULE_4 | ✅ Permission | UK to Adequacy |
| 7 | RULE_5 | ✅ Permission | Switzerland Transfer |
| 8 | RULE_6 | ✅ Permission | EU to Rest of World |
| 9 | RULE_7 | ✅ Permission | BCR Countries |
| 10 | RULE_8 | ✅ Permission | PII Transfer |

---

## 🏗️ Architecture at a Glance

```
┌─────────────────────────────────────────────────────────────┐
│                     Web Dashboard (UI)                      │
│  • Search Form  • Metadata Builder  • Results Display      │
└───────────────────────────┬─────────────────────────────────┘
                            │ HTTP POST
┌───────────────────────────▼─────────────────────────────────┐
│                    FastAPI Server (API)                      │
│  • /api/evaluate-rules  • /api/search-cases  • /docs       │
└───────────┬─────────────────────┬───────────────────────────┘
            │                     │
            │                     │
┌───────────▼───────────┐  ┌──────▼──────────────────────────┐
│   Health Detector     │  │   Rules Evaluation Engine       │
│  • 244 keywords       │  │  • Match type logic             │
│  • Pattern matching   │  │  • Priority sorting             │
│  • Word boundaries    │  │  • Deontic operators            │
└───────────┬───────────┘  └──────┬──────────────────────────┘
            │                     │
            │                     │
┌───────────▼─────────────────────▼───────────────────────────┐
│              FalkorDB (Graph Database)                       │
│                                                              │
│  ┌──────────────────┐         ┌──────────────────────────┐ │
│  │   RulesGraph     │         │  DataTransferGraph       │ │
│  │  • 11 Rules      │         │  • Historical Cases      │ │
│  │  • 87 Countries  │         │  • Personal Data         │ │
│  │  • 14 Groups     │         │  • Purposes              │ │
│  └──────────────────┘         └──────────────────────────┘ │
└──────────────────────────────────────────────────────────────┘
```

---

## 🎯 Key Features

### 1. **Automatic Health Data Detection**
```json
{
  "other_metadata": {
    "patient_id": "unique identifier",
    "diagnosis_codes": "ICD-10 codes"
  }
}
```
→ System automatically detects health data and triggers RULE_11

### 2. **Priority-Based Evaluation**
Rules execute in priority order (1 = highest):
- Priority 1: Absolute prohibitions (RULE_10)
- Priority 2-3: Conditional prohibitions (RULE_9, RULE_11)
- Priority 4-10: Permissions

### 3. **ODRL Compliance**
Every rule includes ODRL metadata:
- `odrl_type`: Permission or Prohibition
- `odrl_action`: transfer, store, process
- `odrl_target`: Data, PII, HealthData

### 4. **Comprehensive Testing**
- ✅ 23/24 tests passing (95.8%)
- Health detection verified
- Priority ordering confirmed
- False positive prevention validated

---

## 📋 API Examples

### Example 1: Basic Transfer Evaluation
```bash
curl -X POST http://localhost:8000/api/evaluate-rules \
  -H "Content-Type: application/json" \
  -d '{
    "origin_country": "Ireland",
    "receiving_country": "Poland",
    "pii": true
  }'
```

**Response:**
```json
{
  "success": true,
  "triggered_rules": [
    {
      "rule_id": "RULE_1",
      "description": "EU/EEA internal transfer",
      "is_blocked": false,
      "permission": {
        "name": "EU/EEA Internal Transfer",
        "duties": [
          {"name": "Complete PIA Module (CM)"}
        ]
      }
    }
  ],
  "has_prohibitions": false
}
```

### Example 2: Health Data Transfer (Auto-Detection)
```bash
curl -X POST http://localhost:8000/api/evaluate-rules \
  -H "Content-Type: application/json" \
  -d '{
    "origin_country": "United States",
    "receiving_country": "India",
    "pii": true,
    "other_metadata": {
      "patient_id": "unique identifier",
      "diagnosis_codes": "ICD-10 codes"
    }
  }'
```

**Response:**
```json
{
  "success": true,
  "triggered_rules": [
    {
      "rule_id": "RULE_11",
      "description": "US Health Data Transfer",
      "is_blocked": true,
      "prohibition": {
        "name": "US Health Data Transfer",
        "duties": [
          {"name": "Obtain US Legal Exception"}
        ]
      }
    }
  ],
  "has_prohibitions": true
}
```

---

## 🔍 Graph Schema Overview

### RulesGraph Structure

```
Rule
├── HAS_ACTION → Action
├── HAS_PERMISSION → Permission → CAN_HAVE_DUTY → Duty
├── HAS_PROHIBITION → Prohibition → CAN_HAVE_DUTY → Duty
├── TRIGGERED_BY_ORIGIN → CountryGroup
└── TRIGGERED_BY_RECEIVING → CountryGroup

Country → BELONGS_TO → CountryGroup
```

### DataTransferGraph Structure

```
Case
├── ORIGINATES_FROM → Country
├── TRANSFERS_TO → Jurisdiction
├── HAS_PURPOSE → Purpose
├── HAS_PROCESS_L1 → ProcessL1
├── HAS_PROCESS_L2 → ProcessL2
├── HAS_PROCESS_L3 → ProcessL3
├── HAS_PERSONAL_DATA → PersonalData
├── HAS_PERSONAL_DATA_CATEGORY → PersonalDataCategory
└── HAS_CATEGORY → Category
```

**See [ARCHITECTURE.md](ARCHITECTURE.md) for detailed Mermaid diagrams**

---

## 🛠️ Configuration

### Health Data Keywords
Stored in `health_data_config.json`:
- **244 keywords**: patient, medical, diagnosis, prescription, etc.
- **27 patterns**: ICD codes, CPT codes, medical record patterns
- **16 categories**: Patient Demographics, Clinical Data, etc.

### Rule Configuration
Rules defined in `build_rules_graph_deontic.py`:
- Geographic scope (origin/receiving countries)
- Match type logic (ANY, ALL, NOT_IN)
- Priority ordering
- Data type filters (PII, health data)
- ODRL metadata

---

## 🧪 Testing

### Test Suites

1. **Basic API Tests** (`test_new_api.py`)
   - 4 test scenarios
   - Validates basic functionality
   - Tests ODRL metadata

2. **Health Detection Tests** (`test_health_detection.py`)
   - 24 comprehensive test cases
   - Various health keywords
   - Edge cases and false positives
   - 95.8% pass rate

### Run All Tests
```bash
# Install test server
uvicorn api_fastapi_deontic:app --reload --port 8000 &

# Run basic tests
python test_new_api.py

# Run health detection tests
python test_health_detection.py

# Stop server
pkill -f uvicorn
```

---

## 🚨 Common Issues & Solutions

### Issue 1: Health data not detected
**Problem:** `patient_id` not matching `patient`
**Solution:** Fixed with underscore normalization (v3.0)
**Verify:** `python test_health_detection.py`

### Issue 2: Wrong rule priority
**Problem:** Multiple rules with same priority
**Solution:** US rules adjusted to priorities 1, 2, 3
**Verify:** Check logs for rule order

### Issue 3: RULE_11 not triggering
**Problem:** Missing health metadata
**Solution:** Provide `other_metadata` with health terms
**Verify:** See [HEALTH_DETECTION_SOLUTION.md](HEALTH_DETECTION_SOLUTION.md)

---

## 📈 Roadmap

### Completed ✅
- [x] Deontic logic implementation
- [x] ODRL compliance
- [x] Health data auto-detection (244 keywords)
- [x] Priority-based evaluation
- [x] User-friendly API
- [x] Comprehensive documentation
- [x] Test suites (95.8% pass rate)

### Future Enhancements
- [ ] Temporal constraints (valid_from, valid_until)
- [ ] Assignee/Assigner tracking
- [ ] Asset nodes (formalize data types)
- [ ] Audit logging
- [ ] Rule versioning
- [ ] Multi-language support

---

## 📝 Change Log

### Version 3.0.0 (2026-02-02)
- ✅ Implemented comprehensive health data detection (244 keywords)
- ✅ Fixed underscore/hyphen handling in keyword matching
- ✅ Added ODRL metadata to all rules
- ✅ Improved rule priority ordering
- ✅ Created extensive documentation with Mermaid diagrams
- ✅ Added comprehensive test suites (95.8% pass rate)
- ✅ User-friendly API redesign
- ✅ Dynamic metadata builder in UI

### Version 2.0.0 (Previous)
- Deontic logic implementation
- RulesGraph and DataTransferGraph
- Basic health detection

### Version 1.0.0 (Initial)
- Basic rule evaluation
- Country group matching

---

**System Status: 🟢 Production Ready**

For detailed technical information, see [ARCHITECTURE.md](ARCHITECTURE.md)
