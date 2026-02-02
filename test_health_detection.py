#!/usr/bin/env python3
"""
Comprehensive test for health data detection
Tests various scenarios to ensure RULE_11 triggers correctly
"""

import requests
import json

API_BASE = "http://localhost:8000"

def print_header(title):
    print("\n" + "="*80)
    print(f"  {title}")
    print("="*80)

def test_case(name, origin, receiving, metadata, should_trigger_rule11=True):
    """Test a single case and verify RULE_11 behavior"""
    print(f"\n📋 Test: {name}")
    print(f"   Route: {origin} → {receiving}")

    if metadata:
        print(f"   Metadata:")
        for key, value in metadata.items():
            print(f"      • {key}: {value}")
    else:
        print(f"   Metadata: None")

    payload = {
        "origin_country": origin,
        "receiving_country": receiving,
        "pii": True,
        "other_metadata": metadata
    }

    try:
        response = requests.post(f"{API_BASE}/api/evaluate-rules", json=payload)
        data = response.json()

        rule_ids = [r['rule_id'] for r in data['triggered_rules']]
        has_rule_11 = 'RULE_11' in rule_ids

        print(f"\n   Result:")
        print(f"   • Rules triggered: {len(rule_ids)} - {', '.join(rule_ids)}")
        print(f"   • Has prohibitions: {data['has_prohibitions']}")
        print(f"   • RULE_11 (Health): {'✅ TRIGGERED' if has_rule_11 else '❌ NOT TRIGGERED'}")

        if has_rule_11 and should_trigger_rule11:
            print(f"   ✅ PASS - RULE_11 correctly triggered")
            # Show the prohibition details
            for rule in data['triggered_rules']:
                if rule['rule_id'] == 'RULE_11' and rule.get('prohibition'):
                    print(f"   📛 Prohibition: {rule['prohibition']['name']}")
                    if rule['prohibition'].get('duties'):
                        print(f"   📋 Required duties:")
                        for duty in rule['prohibition']['duties']:
                            print(f"      • {duty['name']}")
            return True
        elif not has_rule_11 and not should_trigger_rule11:
            print(f"   ✅ PASS - RULE_11 correctly NOT triggered")
            return True
        elif has_rule_11 and not should_trigger_rule11:
            print(f"   ❌ FAIL - RULE_11 should NOT trigger but did")
            return False
        else:
            print(f"   ❌ FAIL - RULE_11 should trigger but did not")
            return False

    except Exception as e:
        print(f"   ❌ ERROR: {e}")
        return False


def main():
    print_header("COMPREHENSIVE HEALTH DATA DETECTION TESTS")
    print("Testing RULE_11: US Health Data Transfer Prohibition")
    print("Expected behavior: RULE_11 triggers for ANY US health data transfer to ANY country")

    results = []

    # ========================================================================
    print_header("TEST GROUP 1: Basic Health Keywords")
    # ========================================================================

    results.append(test_case(
        "Simple 'patient' keyword",
        "United States", "India",
        {"patient": "patient information"},
        should_trigger_rule11=True
    ))

    results.append(test_case(
        "'patient_id' column name",
        "United States", "Canada",
        {"patient_id": "unique identifier"},
        should_trigger_rule11=True
    ))

    results.append(test_case(
        "'medical' keyword",
        "United States", "United Kingdom",
        {"medical_records": "patient medical history"},
        should_trigger_rule11=True
    ))

    results.append(test_case(
        "'diagnosis' keyword",
        "United States", "Germany",
        {"diagnosis_codes": "ICD-10 codes"},
        should_trigger_rule11=True
    ))

    # ========================================================================
    print_header("TEST GROUP 2: Various Health Terms")
    # ========================================================================

    results.append(test_case(
        "Prescription data",
        "United States", "France",
        {"prescription": "medication orders", "pharmacy_data": "dispensing records"},
        should_trigger_rule11=True
    ))

    results.append(test_case(
        "Laboratory results",
        "United States", "Japan",
        {"lab_results": "blood tests", "test_specimen": "samples"},
        should_trigger_rule11=True
    ))

    results.append(test_case(
        "Hospital data",
        "United States", "Australia",
        {"hospital_admission": "inpatient data", "ward": "location"},
        should_trigger_rule11=True
    ))

    results.append(test_case(
        "Doctor/physician info",
        "United States", "Singapore",
        {"doctor_name": "attending physician", "clinical_notes": "progress notes"},
        should_trigger_rule11=True
    ))

    # ========================================================================
    print_header("TEST GROUP 3: Advanced Health Terms")
    # ========================================================================

    results.append(test_case(
        "Genetic/biometric data",
        "United States", "Brazil",
        {"genetic_data": "DNA sequences", "biometric": "fingerprints"},
        should_trigger_rule11=True
    ))

    results.append(test_case(
        "Mental health data",
        "United States", "Mexico",
        {"psychiatry": "mental health records", "therapy_notes": "counseling sessions"},
        should_trigger_rule11=True
    ))

    results.append(test_case(
        "Surgery/procedure data",
        "United States", "South Korea",
        {"surgery_type": "operative procedures", "anesthesia": "sedation records"},
        should_trigger_rule11=True
    ))

    # ========================================================================
    print_header("TEST GROUP 4: Non-Health Data (Should NOT Trigger)")
    # ========================================================================

    results.append(test_case(
        "Marketing data",
        "United States", "Canada",
        {"customer_email": "email addresses", "marketing_consent": "opt-in status"},
        should_trigger_rule11=False
    ))

    results.append(test_case(
        "Financial data",
        "United States", "India",
        {"transaction_amount": "purchase value", "payment_method": "credit card"},
        should_trigger_rule11=False
    ))

    results.append(test_case(
        "HR data (non-health)",
        "United States", "Poland",
        {"employee_id": "staff number", "salary": "compensation"},
        should_trigger_rule11=False
    ))

    # ========================================================================
    print_header("TEST GROUP 5: Edge Cases")
    # ========================================================================

    results.append(test_case(
        "Health-like but not health",
        "United States", "Netherlands",
        {"healthcare_plan": "insurance provider", "wellness_program": "gym membership"},
        should_trigger_rule11=True  # These ARE health-related!
    ))

    results.append(test_case(
        "No metadata at all",
        "United States", "China",
        None,
        should_trigger_rule11=False
    ))

    results.append(test_case(
        "Empty metadata",
        "United States", "Russia",
        {},
        should_trigger_rule11=False
    ))

    # ========================================================================
    print_header("TEST GROUP 6: Destination Countries (Should Prohibit ALL)")
    # ========================================================================

    destinations = ["China", "India", "Canada", "United Kingdom", "Germany", "Japan", "Australia"]

    for dest in destinations:
        results.append(test_case(
            f"US → {dest} with health data",
            "United States", dest,
            {"patient_records": "medical data"},
            should_trigger_rule11=True
        ))

    # ========================================================================
    print_header("FINAL RESULTS")
    # ========================================================================

    total = len(results)
    passed = sum(results)
    failed = total - passed

    print(f"\n📊 Test Summary:")
    print(f"   Total tests: {total}")
    print(f"   Passed: {passed} ✅")
    print(f"   Failed: {failed} ❌")
    print(f"   Success rate: {(passed/total*100):.1f}%")

    if failed == 0:
        print("\n🎉 ALL TESTS PASSED! Health detection is working correctly.")
    else:
        print(f"\n⚠️  {failed} tests failed. Please review the output above.")

    print("\n" + "="*80)

if __name__ == '__main__':
    main()
