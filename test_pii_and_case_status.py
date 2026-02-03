#!/usr/bin/env python3
"""
Test PII identification and case status compliance logic
"""

from falkordb import FalkorDB
import sys
sys.path.insert(0, '/Users/josephkiype/Desktop/development/code/deterministic policy')
from api_fastapi_deontic import has_pii_data, evaluate_assessment_compliance

print("=" * 70)
print("TESTING PII IDENTIFICATION AND CASE STATUS LOGIC")
print("=" * 70)

# Test 1: PII Identification Logic
print("\n📊 Test 1: PII Identification from personalDataCategory")
print("=" * 70)

pii_test_cases = [
    {
        'input': ['PII', 'Financial Data', 'Health Data'],
        'expected': True,
        'description': 'Has valid PII categories'
    },
    {
        'input': ['Contact Information'],
        'expected': True,
        'description': 'Has one valid category'
    },
    {
        'input': ['N/A'],
        'expected': False,
        'description': 'Only N/A - no PII'
    },
    {
        'input': ['NA'],
        'expected': False,
        'description': 'Only NA - no PII'
    },
    {
        'input': ['null'],
        'expected': False,
        'description': 'Only null - no PII'
    },
    {
        'input': [],
        'expected': False,
        'description': 'Empty list - no PII'
    },
    {
        'input': [''],
        'expected': False,
        'description': 'Empty string - no PII'
    },
    {
        'input': ['  N/A  ', '  NA  '],
        'expected': False,
        'description': 'Only N/A with whitespace - no PII'
    },
    {
        'input': ['PII', 'N/A', 'Financial Data'],
        'expected': True,
        'description': 'Mix of valid and N/A - has PII'
    },
    {
        'input': ['Customer Data', 'Employee Data'],
        'expected': True,
        'description': 'Multiple valid categories - has PII'
    }
]

passed = 0
failed = 0

for i, test in enumerate(pii_test_cases, 1):
    result = has_pii_data(test['input'])
    expected = test['expected']

    if result == expected:
        print(f"✅ Test {i}: {test['description']}")
        print(f"   Input: {test['input']}")
        print(f"   Result: has_pii = {result}")
        passed += 1
    else:
        print(f"❌ Test {i}: {test['description']}")
        print(f"   Input: {test['input']}")
        print(f"   Result: {result}, Expected: {expected}")
        failed += 1

print(f"\nPII Tests: {passed} passed, {failed} failed")

# Test 2: Case Status Compliance Logic
print("\n" + "=" * 70)
print("📊 Test 2: Case Status Must Be 'Completed' for Compliance")
print("=" * 70)

case_status_tests = [
    {
        'case_status': 'Completed',
        'required_assessments': ['PIA', 'TIA'],
        'pia_status': 'Completed',
        'tia_status': 'Completed',
        'expected_compliant': True,
        'description': 'Case=Completed, PIA=Completed, TIA=Completed → COMPLIANT'
    },
    {
        'case_status': 'Active',
        'required_assessments': ['PIA', 'TIA'],
        'pia_status': 'Completed',
        'tia_status': 'Completed',
        'expected_compliant': False,
        'description': 'Case=Active (not Completed) → NON-COMPLIANT'
    },
    {
        'case_status': 'Pending',
        'required_assessments': ['PIA'],
        'pia_status': 'Completed',
        'expected_compliant': False,
        'description': 'Case=Pending (not Completed) → NON-COMPLIANT'
    },
    {
        'case_status': 'Under Review',
        'required_assessments': [],
        'expected_compliant': False,
        'description': 'Case=Under Review (not Completed) → NON-COMPLIANT'
    },
    {
        'case_status': 'Completed',
        'required_assessments': ['PIA'],
        'pia_status': 'N/A',
        'expected_compliant': False,
        'description': 'Case=Completed but PIA=N/A → NON-COMPLIANT'
    },
    {
        'case_status': 'Completed',
        'required_assessments': ['PIA'],
        'pia_status': 'In Progress',
        'expected_compliant': False,
        'description': 'Case=Completed but PIA=In Progress → NON-COMPLIANT'
    },
    {
        'case_status': 'Completed',
        'required_assessments': [],
        'expected_compliant': True,
        'description': 'Case=Completed, no assessments required → COMPLIANT'
    }
]

case_passed = 0
case_failed = 0

for i, test in enumerate(case_status_tests, 1):
    result = evaluate_assessment_compliance(
        required_assessments=test['required_assessments'],
        pia_status=test.get('pia_status'),
        tia_status=test.get('tia_status'),
        hrpr_status=test.get('hrpr_status'),
        case_status=test['case_status']
    )

    if result['compliant'] == test['expected_compliant']:
        print(f"✅ Test {i}: {test['description']}")
        print(f"   Result: {result['message']}")
        case_passed += 1
    else:
        print(f"❌ Test {i}: {test['description']}")
        print(f"   Expected: {'COMPLIANT' if test['expected_compliant'] else 'NON-COMPLIANT'}")
        print(f"   Got: {'COMPLIANT' if result['compliant'] else 'NON-COMPLIANT'}")
        print(f"   Message: {result['message']}")
        case_failed += 1

print(f"\nCase Status Tests: {case_passed} passed, {case_failed} failed")

# Test 3: Check Graph Data
print("\n" + "=" * 70)
print("📊 Test 3: Verify Graph Data Has case_status Field")
print("=" * 70)

try:
    db = FalkorDB(host='localhost', port=6379)
    graph = db.select_graph('DataTransferGraph')

    query = """
    MATCH (c:Case)
    RETURN c.case_ref_id, c.case_status, c.pia_status, c.tia_status
    LIMIT 5
    """

    result = graph.query(query)

    if result.result_set:
        print(f"\nSample cases in graph:")
        for row in result.result_set:
            case_id = row[0]
            case_status = row[1]
            pia_status = row[2]
            tia_status = row[3]
            print(f"   {case_id}: case_status={case_status}, PIA={pia_status}, TIA={tia_status}")

        print("\n✅ Graph contains case_status field")
    else:
        print("⚠️  No cases in graph")

except Exception as e:
    print(f"❌ Error querying graph: {e}")

# Summary
print("\n" + "=" * 70)
print("SUMMARY")
print("=" * 70)

print("\n✅ PII Identification Logic:")
print("   • If personalDataCategory has any value (except N/A, NA, null, blank) → PII exists")
print("   • If personalDataCategory is N/A, NA, null, or blank → No PII")
print(f"   Tests: {passed}/{len(pii_test_cases)} passed")

print("\n✅ Case Status Compliance Logic:")
print("   • Case status MUST be 'Completed' for case to be compliant")
print("   • Even if PIA, TIA, HRPR are all 'Completed'")
print("   • If case status is Active, Pending, Under Review, etc. → NON-COMPLIANT")
print(f"   Tests: {case_passed}/{len(case_status_tests)} passed")

if failed == 0 and case_failed == 0:
    print("\n🎉 All tests passed!")
    sys.exit(0)
else:
    print(f"\n⚠️  {failed + case_failed} test(s) failed")
    sys.exit(1)
