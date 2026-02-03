# Production-Grade Data Generation Guide

## Overview

This system provides production-grade tools for generating and uploading realistic sample data to FalkorDB's DataTransferGraph.

## Quick Start

```bash
# Step 1: Generate 100 random cases
python3 create_sample_data.py --count 100

# Step 2: Upload to FalkorDB
python3 falkor_upload_json.py sample_data.json --clear
```

---

## Data Generator: `create_sample_data.py`

### Features

✅ **Randomized Data Generation**
- Random country pairs from 60+ countries
- Random purposes (20 different types)
- Random process hierarchies (40+ combinations)
- Random assessment statuses with realistic distributions

✅ **Production-Grade Quality**
- Realistic country groupings (EU/EEA, BCR, Adequacy, etc.)
- Smart compliance rates based on routes (EU routes have higher completion rates)
- Proper pipe-separated (`|`) multi-value fields
- Proper dash-separated (`-`) process hierarchies

✅ **Configurable Options**
- Custom case count
- Custom output file
- Random seed for reproducibility

### Usage

#### Basic Usage
```bash
# Generate 100 cases (default)
python3 create_sample_data.py

# Generate custom number of cases
python3 create_sample_data.py --count 500

# Custom output file
python3 create_sample_data.py --output my_data.json

# Reproducible generation with seed
python3 create_sample_data.py --count 200 --seed 42
```

#### Advanced Usage
```bash
# Generate large dataset for production testing
python3 create_sample_data.py --count 1000 --output prod_test_data.json

# Generate small dataset for development
python3 create_sample_data.py --count 20 --output dev_data.json --seed 123
```

### Data Statistics

When you run the generator, it shows:
- **Compliant cases**: Cases with all required assessments "Completed"
- **Cases with PII**: Percentage containing personal data
- **Unique countries**: Number of unique origin/receiving countries
- **Multi-value cases**: Percentage with multiple purposes/processes/receiving countries

Example output:
```
📈 Data Statistics:
   Compliant cases: 38/100 (38%)
   Cases with PII: 52/100 (52%)
   Unique origin countries: 45
   Unique receiving countries: 48
   Multi-receiving cases: 34/100 (34%)
   Multi-purpose cases: 56/100 (56%)
   Multi-process cases: 30/100 (30%)
```

---

## Data Uploader: `falkor_upload_json.py`

### Features

✅ **Smart Parsing**
- Pipe-separated (`|`) values for multi-value fields
- Dash-separated (`-`) process hierarchies
- UTF-8 encoding support
- Field name mapping (camelCase → snake_case)

✅ **Relationship Creation**
- Country nodes and ORIGINATES_FROM relationships
- Jurisdiction nodes and TRANSFERS_TO relationships
- Purpose nodes and HAS_PURPOSE relationships
- ProcessL1/L2/L3 nodes and hierarchy relationships
- PersonalDataCategory nodes and relationships

✅ **Error Handling**
- Validates JSON format
- Reports success/failure per case
- Continues on errors
- Summary statistics

### Usage

#### Basic Upload
```bash
# Upload data (append to existing)
python3 falkor_upload_json.py sample_data.json

# Upload data (clear graph first)
python3 falkor_upload_json.py sample_data.json --clear
```

#### Custom File
```bash
# Upload custom JSON file
python3 falkor_upload_json.py my_custom_data.json --clear
```

---

## Data Format Specification

### JSON Structure
```json
[
    {
        "caseRefId": "CASE_00001",
        "caseStatus": "Completed",
        "appId": "APP_001",
        "originatingCountry": "United Kingdom",
        "receivingCountry": "India|Germany|France",
        "tiaStatus": "Completed",
        "piaStatus": "Completed",
        "hrprStatus": "N/A",
        "purposeOfProcessing": "Marketing|Analytics|Sales",
        "processess": "Sales - Customer Management - CRM|Marketing - Digital - SEO",
        "personalDataCategory": "Contact Information|PII|Customer Data"
    }
]
```

### Field Specifications

| Field | Type | Format | Example |
|-------|------|--------|---------|
| `caseRefId` | String | `CASE_XXXXX` | `CASE_00001` |
| `caseStatus` | String | Single value | `Active`, `Completed` |
| `appId` | String | `APP_XXX` | `APP_001` |
| `originatingCountry` | String | Single country | `United Kingdom` |
| `receivingCountry` | String | Pipe-separated | `Germany\|France\|Spain` |
| `tiaStatus` | String | Assessment status | `Completed`, `N/A` |
| `piaStatus` | String | Assessment status | `Completed`, `In Progress` |
| `hrprStatus` | String | Assessment status | `Completed`, `WITHDRAWN` |
| `purposeOfProcessing` | String | Pipe-separated | `Marketing\|Analytics` |
| `processess` | String | Hierarchy format | `Finance - Accounting - Payroll` |
| `personalDataCategory` | String | Pipe-separated | `PII\|Contact Information` |

### Process Hierarchy Format

**Single Hierarchy**:
```
"Finance - Accounting - Payroll"
```
Creates: ProcessL1=Finance, ProcessL2=Accounting, ProcessL3=Payroll

**Multiple Hierarchies** (pipe-separated):
```
"Marketing - Digital - SEO|Sales - B2B - Account Management"
```
Creates:
- ProcessL1=Marketing, ProcessL2=Digital, ProcessL3=SEO
- ProcessL1=Sales, ProcessL2=B2B, ProcessL3=Account Management

**Partial Hierarchy** (empty L3):
```
"IT Support - Infrastructure - "
```
Creates: ProcessL1=IT Support, ProcessL2=Infrastructure, ProcessL3=(none)

---

## Assessment Status Values

### Compliant
- ✅ `"Completed"` - Only this status = COMPLIANT

### Non-Compliant
- ❌ `"In Progress"` - Assessment in progress
- ❌ `"Not Started"` - Assessment not begun
- ❌ `"N/A"` - Assessment not applicable
- ❌ `"WITHDRAWN"` - Assessment withdrawn

---

## Production Use Cases

### 1. Development Testing
```bash
# Generate small dataset
python3 create_sample_data.py --count 20 --output dev_data.json --seed 123
python3 falkor_upload_json.py dev_data.json --clear
```

### 2. Load Testing
```bash
# Generate large dataset
python3 create_sample_data.py --count 5000 --output load_test.json
python3 falkor_upload_json.py load_test.json --clear
```

### 3. Reproducible Testing
```bash
# Same data every time
python3 create_sample_data.py --count 100 --seed 42 --output test_data.json
python3 falkor_upload_json.py test_data.json --clear
```

### 4. Custom Data
Create your own JSON file following the format above, then:
```bash
python3 falkor_upload_json.py your_custom_data.json --clear
```

---

## Data Distribution

The generator creates realistic distributions:

### Country Selection
- 40% EU/EEA countries
- 20% UK/Crown Dependencies
- 15% Adequacy countries
- 15% BCR countries
- 10% Other countries

### Assessment Status Distribution
- 40% Completed (compliant)
- 20% In Progress
- 15% Not Started
- 20% N/A
- 5% WITHDRAWN

### EU Routes Get Compliance Boost
- EU → EU routes: +30% completion probability
- BCR routes: +15% completion probability
- This creates realistic compliance patterns

### Multi-Value Fields
- 60% single receiving country, 40% multiple
- 40% single purpose, 60% multiple
- 70% single process, 30% multiple

---

## Troubleshooting

### Generator Issues

**Problem**: Script fails with import error
```bash
# Solution: Ensure Python 3.7+ is installed
python3 --version
```

**Problem**: Need more diverse data
```bash
# Solution: Increase case count
python3 create_sample_data.py --count 500
```

### Upload Issues

**Problem**: Connection refused
```bash
# Solution: Start FalkorDB
docker run -p 6379:6379 falkordb/falkordb:latest
```

**Problem**: Some cases fail to load
```bash
# Solution: Check JSON format and error messages
python3 -m json.tool sample_data.json
```

---

## File Structure

```
deterministic policy/
├── create_sample_data.py          # Data generator
├── falkor_upload_json.py          # Data uploader
├── sample_data.json               # Generated data
└── DATA_GENERATION_GUIDE.md       # This guide
```

---

## Best Practices

1. **Always use `--clear` for testing**
   - Ensures clean state
   - Prevents duplicate data

2. **Use `--seed` for reproducibility**
   - Same seed = same data
   - Useful for automated testing

3. **Generate realistic volumes**
   - Dev: 20-50 cases
   - Test: 100-500 cases
   - Load test: 1000+ cases

4. **Validate before uploading**
   ```bash
   # Check JSON is valid
   python3 -m json.tool sample_data.json > /dev/null && echo "Valid JSON"
   ```

5. **Monitor upload progress**
   - Script shows progress every 20 cases
   - Final summary shows success/failure counts

---

## Support

For issues or questions:
1. Check this guide
2. Verify FalkorDB is running: `docker ps`
3. Check JSON format: `python3 -m json.tool sample_data.json`
4. Review error messages in upload output

---

**Happy data generation!** 🎉
