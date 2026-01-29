# Graph-Based Compliance Logic - Complete Guide

## Overview

The compliance system uses FalkorDB graphs for **all business logic** with:
1. **RulesGraph** - Stores compliance rules and triggers
2. **DataTransferGraph** - Stores cases with enhanced structure

## Key Changes from Original Design

### 1. Purposes: Nodes with Multiple Edges (Not Hierarchical Properties)

**OLD Design (Properties):**
```cypher
(:Case {
  case_id: "CASE00001",
  purpose_level1: "Provision of Banking",
  purpose_level2: "Payment Processing",
  purpose_level3: "Credit Scoring"
})
```

**NEW Design (Nodes with Edges):**
```cypher
(:Case {case_id: "CASE00001"})-[:HAS_PURPOSE]->(:Purpose {name: "Provision of Banking"})
(:Case {case_id: "CASE00001"})-[:HAS_PURPOSE]->(:Purpose {name: "Payment Processing"})
(:Case {case_id: "CASE00001"})-[:HAS_PURPOSE]->(:Purpose {name: "Credit Scoring"})
```

**Why:**
- A case can have ANY number of purposes (not limited to 3)
- Purposes are not hierarchical - they're independent attributes
- Better for multi-select in UI
- Easier to query: "Find all cases with purpose X"

### 2. Processes: New Hierarchical Structure (L1-L2-L3)

**NEW Column:** `Processes_L1_L2_L3`
**Format:** "L1-L2-L3" (hyphen-separated)
**Example:** "Back Office-HR-Payroll"

**Graph Structure:**
```cypher
// Process hierarchy
(:Case {case_id: "CASE00001"})-[:HAS_PROCESS_L1]->(:ProcessL1 {name: "Back Office"})
(:Case {case_id: "CASE00001"})-[:HAS_PROCESS_L2]->(:ProcessL2 {name: "HR"})
(:Case {case_id: "CASE00001"})-[:HAS_PROCESS_L3]->(:ProcessL3 {name: "Payroll"})
```

**Process Levels:**
- **L1:** Business area (e.g., "Back Office", "Front Office", "Operations")
- **L2:** Function (e.g., "HR", "Finance", "IT")
- **L3:** Sub-process (e.g., "Payroll", "AP", "Support")

## Status

✅ Enhanced structure loaded with 350 cases
✅ 35 Purpose nodes with 1,029 HAS_PURPOSE edges
✅ Process hierarchy: L1 (5), L2 (14), L3 (22) nodes
✅ Ready for API and UI updates

See full documentation in this file for complete details.
