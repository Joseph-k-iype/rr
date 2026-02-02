# API Redesign - User-Friendly Interface with Dynamic Evaluation

**Date:** 2026-02-02
**Status:** ✅ Implemented and tested

---

## Overview

The API has been redesigned with a clean, user-friendly interface that supports:
- Simplified parameter names (no technical jargon)
- All parameters optional for flexible dynamic searching
- Automatic health data detection from metadata
- JSON-based metadata input
- Updated UI with metadata builder

---

## New API Parameters

### **For End Users - Simplified Structure**

```json
{
  "origin_country": "United States",       // Required
  "receiving_country": "China",            // Required
  "pii": true,                             // Optional boolean flag
  "purpose_of_processing": ["Analytics"],  // Optional list
  "process_l1": "Healthcare",              // Optional string
  "process_l2": "Patient Management",      // Optional string
  "process_l3": "Medical Records",         // Optional string
  "other_metadata": {                      // Optional JSON object
    "patient_id": "unique identifier",
    "diagnosis_codes": "ICD-10 codes"
  }
}
```

### **Key Features**

1. **No ODRL Terminology** - Users don't see `odrl_type`, `odrl_action`, etc.
2. **Simple Metadata** - Just column names and descriptions
3. **Automatic Detection** - Health data detected from metadata automatically
4. **Dynamic Evaluation** - Rules evaluated based on what's provided
5. **US Restrictions** - Logic like "US to China" handled automatically by rules engine

---

## API Endpoints

### **POST /api/evaluate-rules**

Evaluate compliance rules for a data transfer.

**Request Body:**
```json
{
  "origin_country": "United States",
  "receiving_country": "China",
  "pii": true,
  "purpose_of_processing": ["Healthcare Analytics", "Research"],
  "process_l1": "Healthcare",
  "process_l2": "Patient Management",
  "process_l3": "Medical Records",
  "other_metadata": {
    "patient_id": "unique identifier for patients",
    "diagnosis_codes": "ICD-10 medical diagnosis codes",
    "prescription_history": "medication and prescription records",
    "lab_results": "laboratory test results"
  }
}
```

**Response:**
```json
{
  "success": true,
  "triggered_rules": [
    {
      "rule_id": "RULE_10",
      "description": "Data owned, created, developed, or maintained in US cannot be stored or processed in China cloud storage",
      "priority": 1,
      "odrl_type": "Prohibition",
      "odrl_action": "store",
      "odrl_target": "Data",
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
      "rule_id": "RULE_11",
      "description": "Transfer of health-related data from US is PROHIBITED without approval",
      "priority": 3,
      "prohibition": {
        "name": "US Health Data Transfer",
        "description": "Prohibition on transferring health data from US without approval",
        "duties": [
          {
            "name": "Obtain US Legal Exception",
            "description": "Obtain legal exception from US legal team",
            "module": null,
            "value": null
          }
        ]
      },
      "is_blocked": true
    }
  ],
  "total_rules_triggered": 4,
  "has_prohibitions": true,
  "consolidated_duties": [...]
}
```

### **POST /api/search-cases**

Search for existing data transfer cases.

**Request Body:**
```json
{
  "origin_country": "Ireland",
  "receiving_country": "Poland",
  "pii": true,
  "purpose_of_processing": ["Marketing"],
  "process_l1": "Sales",
  "process_l2": null,
  "process_l3": null,
  "other_metadata": null
}
```

---

## Automatic Health Data Detection

The system automatically detects health data from the `other_metadata` field using word boundary matching on these keywords:

```python
health_keywords = [
    'health', 'medical', 'patient', 'diagnosis', 'treatment', 'prescription',
    'clinical', 'hospital', 'doctor', 'disease', 'illness', 'medication',
    'healthcare', 'wellness', 'fitness', 'biometric', 'genetic', 'vaccine',
    'surgery', 'therapy', 'pharmaceutical', 'radiology', 'lab', 'laboratory'
]
```

### **Examples**

**Health Data Detected:**
```json
{
  "other_metadata": {
    "patient_id": "unique identifier",
    "medical_history": "patient records",
    "diagnosis_codes": "ICD-10 codes"
  }
}
// Result: RULE_11 (US Health Data) triggers if origin is US
```

**No Health Data:**
```json
{
  "other_metadata": {
    "customer_email": "email addresses",
    "customer_name": "full names",
    "purchase_history": "transaction records"
  }
}
// Result: RULE_11 does NOT trigger
```

**False Positives Fixed:**
- "Medicaid Number" → NOT detected as "medical" ✓
- "Doctorate Degree" → NOT detected as "doctor" ✓
- "Healthy Lifestyle" → NOT detected as "health" ✓

---

## UI Updates

### **New Metadata Builder**

The dashboard now includes a dynamic metadata builder:

```html
<!-- Other Metadata Section -->
<div class="form-group" style="grid-column: 1 / -1;">
    <label class="form-label" for="other-metadata">
        Other Metadata (Optional)
        <span>- Add data attributes as key-value pairs. Health data is auto-detected.</span>
    </label>
    <div id="metadata-container">
        <!-- Dynamic metadata inputs -->
    </div>
    <button type="button" id="add-metadata-btn">+ Add Metadata Field</button>
</div>
```

### **Features**

1. **Add/Remove Fields** - Dynamic field management
2. **Real-time Search** - Updates as you type
3. **Auto-Detection** - Health data highlighted automatically
4. **JSON Output** - Metadata sent as clean JSON object

### **User Experience**

```
[Add Metadata Field] button

[patient_id           ] [unique identifier for patients] [Remove]
[diagnosis_codes      ] [ICD-10 medical codes          ] [Remove]
[prescription_history ] [medication records            ] [Remove]

+ Add Metadata Field
```

---

## Test Results

All tests pass successfully:

### **TEST 1: Basic Rule Evaluation**
```
Input: US → Canada, PII=true
Result: ✅ RULE_8 (PII Transfer) triggered
```

### **TEST 2: Health Data Auto-Detection**
```
Input: US → China, PII=true, metadata with health keywords
Result: ✅ All 3 US prohibitions triggered:
  - RULE_10 (China Cloud) - priority 1
  - RULE_9 (PII to Restricted) - priority 2
  - RULE_11 (Health Data) - priority 3 ✅ AUTO-DETECTED
```

### **TEST 3: Non-Health Metadata**
```
Input: US → Canada, metadata with "customer_email", "purchase_history"
Result: ✅ RULE_11 NOT triggered (no health data detected)
```

### **TEST 4: Optional Parameters**
```
Input: Ireland → Poland (minimal params, no PII, no metadata)
Result: ✅ RULE_1 and RULE_7 triggered correctly
```

---

## Parameter Mapping

| Old Parameter | New Parameter | Type | Notes |
|---------------|---------------|------|-------|
| `origin_country` | `origin_country` | string | ✅ Same |
| `receiving_country` | `receiving_country` | string | ✅ Same |
| `has_pii` | `pii` | boolean | ✅ Simplified name |
| `purposes` | `purpose_of_processing` | list | ✅ Clarified |
| `process_l1` | `process_l1` | string | ✅ Same |
| `process_l2` | `process_l2` | string | ✅ Same |
| `process_l3` | `process_l3` | string | ✅ Same |
| `has_health_data` | **AUTO-DETECTED** | - | ✅ From `other_metadata` |
| *(new)* | `other_metadata` | object | ✅ **NEW** - JSON key-value pairs |

---

## Backend Changes

### **Files Modified**

1. **`api_fastapi_deontic.py`**
   - Updated `RulesEvaluationRequest` model
   - Updated `SearchCasesRequest` model
   - Added `detect_health_data_from_metadata()` function
   - Updated `/api/evaluate-rules` endpoint
   - Updated `/api/search-cases` endpoint

2. **`templates/dashboard.html`**
   - Added metadata builder UI
   - Added `addMetadataField()` JavaScript function
   - Added `removeMetadataField()` JavaScript function
   - Added `collectMetadata()` helper function
   - Updated `performSearch()` to handle metadata
   - Updated `resetForm()` to clear metadata fields

---

## How It Works

### **1. User Input (UI)**
```
Origin: United States
Receiving: China
PII: Yes
Metadata:
  - patient_id: unique identifier
  - diagnosis_codes: ICD-10 codes
```

### **2. API Call**
```javascript
fetch('/api/evaluate-rules', {
  method: 'POST',
  body: JSON.stringify({
    origin_country: "United States",
    receiving_country: "China",
    pii: true,
    other_metadata: {
      "patient_id": "unique identifier",
      "diagnosis_codes": "ICD-10 codes"
    }
  })
})
```

### **3. Backend Processing**
```python
# 1. Detect health data from metadata
has_health = detect_health_data_from_metadata(request.other_metadata)
# Result: True (contains "patient", "diagnosis")

# 2. Query rules with detected flags
result = query_triggered_rules_deontic(
    origin="United States",
    receiving="China",
    has_pii=True,
    has_health_data=True  # AUTO-DETECTED
)

# 3. Rules triggered:
# - RULE_10: US to China Cloud (priority 1)
# - RULE_9: US PII to Restricted (priority 2)
# - RULE_11: US Health Data (priority 3) ← AUTO-DETECTED
```

### **4. Response**
```json
{
  "triggered_rules": [
    {"rule_id": "RULE_10", "is_blocked": true, ...},
    {"rule_id": "RULE_9", "is_blocked": true, ...},
    {"rule_id": "RULE_11", "is_blocked": true, ...}
  ],
  "has_prohibitions": true
}
```

---

## Key Advantages

### **For End Users**

1. ✅ **No Technical Jargon** - Simple, clear parameter names
2. ✅ **Flexible Input** - All parameters optional
3. ✅ **Auto-Detection** - Health data detected automatically
4. ✅ **Easy Metadata** - Just column names and descriptions
5. ✅ **Clear Output** - Prohibitions clearly marked with duties

### **For Developers**

1. ✅ **Clean API** - RESTful, intuitive endpoints
2. ✅ **Type Safety** - Pydantic models with validation
3. ✅ **Extensible** - Easy to add new metadata fields
4. ✅ **Testable** - Comprehensive test suite included
5. ✅ **ODRL Compliant** - Backend maintains ODRL structure

### **For Compliance**

1. ✅ **Accurate Detection** - Word boundary matching prevents false positives
2. ✅ **Priority Ordering** - Rules execute in correct priority order
3. ✅ **Complete Duties** - All required duties returned
4. ✅ **Audit Trail** - Full rule evaluation history
5. ✅ **US Regulations** - Automatic US restriction enforcement

---

## Migration Guide

### **Old API Call**
```javascript
{
  "origin_country": "United States",
  "receiving_country": "China",
  "has_pii": true,
  "has_health_data": true  // Manual flag
}
```

### **New API Call**
```javascript
{
  "origin_country": "United States",
  "receiving_country": "China",
  "pii": true,  // Renamed
  "other_metadata": {  // NEW - auto-detects health
    "patient_id": "identifier",
    "diagnosis_codes": "ICD-10"
  }
}
```

### **Breaking Changes**

**None!** The API is backward compatible:
- Old parameter names still work
- New `other_metadata` is optional
- Health detection works with or without metadata

---

## Example Usage

### **Scenario 1: Marketing Data Transfer**
```json
POST /api/evaluate-rules
{
  "origin_country": "Germany",
  "receiving_country": "United States",
  "pii": true,
  "purpose_of_processing": ["Marketing", "Analytics"],
  "other_metadata": {
    "customer_email": "email addresses",
    "customer_name": "full names",
    "marketing_consent": "opt-in status"
  }
}

Response: ✅ RULE_2 (EU to Adequacy) + RULE_8 (PII)
          No health data detected ✓
```

### **Scenario 2: Healthcare Data Transfer**
```json
POST /api/evaluate-rules
{
  "origin_country": "United States",
  "receiving_country": "India",
  "pii": true,
  "purpose_of_processing": ["Healthcare", "Research"],
  "process_l1": "Healthcare",
  "other_metadata": {
    "patient_records": "medical history",
    "lab_results": "test results",
    "prescription_data": "medications"
  }
}

Response: 🔴 RULE_11 (Health Data Prohibition)
          📋 Duty: Obtain US Legal Exception
          Health data auto-detected ✓
```

### **Scenario 3: Financial Data Transfer**
```json
POST /api/evaluate-rules
{
  "origin_country": "Ireland",
  "receiving_country": "Poland",
  "pii": true,
  "process_l1": "Finance",
  "process_l2": "Payroll",
  "other_metadata": {
    "employee_id": "staff identifier",
    "salary_data": "compensation info",
    "tax_records": "tax filings"
  }
}

Response: ✅ RULE_1 (EU Internal) + RULE_8 (PII)
          No health data detected ✓
```

---

## Testing Instructions

1. **Start the API server:**
   ```bash
   uvicorn api_fastapi_deontic:app --reload --port 8000
   ```

2. **Run test suite:**
   ```bash
   python test_new_api.py
   ```

3. **Access UI:**
   ```
   http://localhost:8000
   ```

4. **API Documentation:**
   ```
   http://localhost:8000/docs
   ```

---

## Summary

✅ **User-Friendly API** - Simplified parameters, no jargon
✅ **Dynamic Evaluation** - All parameters optional
✅ **Auto Health Detection** - From metadata automatically
✅ **Updated UI** - Metadata builder with add/remove fields
✅ **Fully Tested** - All test cases pass
✅ **ODRL Compliant** - Backend maintains full compliance
✅ **Backward Compatible** - No breaking changes

**The system is now production-ready with a clean, intuitive interface for end users!** 🎉

---

**End of Summary**
