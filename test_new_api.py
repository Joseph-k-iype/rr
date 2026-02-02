#!/usr/bin/env python3
"""
Test script for new API structure with simplified parameters
"""

import requests
import json

API_BASE = "http://localhost:8000"

def test_evaluate_rules_basic():
    """Test basic rule evaluation without metadata"""
    print("\n" + "="*70)
    print("TEST 1: Basic Rule Evaluation (US → Canada)")
    print("="*70)

    payload = {
        "origin_country": "United States",
        "receiving_country": "Canada",
        "pii": True
    }

    response = requests.post(f"{API_BASE}/api/evaluate-rules", json=payload)
    data = response.json()

    print(f"Status Code: {response.status_code}")
    print(f"Rules Triggered: {data['total_rules_triggered']}")
    print(f"Has Prohibitions: {data['has_prohibitions']}")

    for rule in data['triggered_rules']:
        print(f"\n  Rule: {rule['rule_id']} - {rule['description']}")
        print(f"  Priority: {rule['priority']}")
        if rule.get('odrl_type'):
            print(f"  ODRL Type: {rule['odrl_type']}")
            print(f"  ODRL Action: {rule['odrl_action']}")
            print(f"  ODRL Target: {rule['odrl_target']}")


def test_evaluate_rules_with_health_metadata():
    """Test rule evaluation with health data in metadata"""
    print("\n" + "="*70)
    print("TEST 2: Rule Evaluation with Health Metadata (US → China)")
    print("="*70)

    payload = {
        "origin_country": "United States",
        "receiving_country": "China",
        "pii": True,
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

    response = requests.post(f"{API_BASE}/api/evaluate-rules", json=payload)
    data = response.json()

    print(f"Status Code: {response.status_code}")
    print(f"Rules Triggered: {data['total_rules_triggered']}")
    print(f"Has Prohibitions: {data['has_prohibitions']}")

    print(f"\nMetadata provided:")
    for key, value in payload['other_metadata'].items():
        print(f"  - {key}: {value}")

    print(f"\nTriggered Rules:")
    for rule in data['triggered_rules']:
        rule_type = "🔴 PROHIBITION" if rule['is_blocked'] else "✅ PERMISSION"
        print(f"\n  {rule_type}: {rule['rule_id']} - {rule['description']}")
        print(f"  Priority: {rule['priority']}")

        if rule.get('prohibition'):
            print(f"  ⚠️  Prohibition: {rule['prohibition']['name']}")
            if rule['prohibition'].get('duties'):
                print(f"  📋 Required duties to get exception:")
                for duty in rule['prohibition']['duties']:
                    print(f"     - {duty['name']}: {duty['description']}")


def test_evaluate_rules_non_health_metadata():
    """Test that non-health metadata doesn't trigger health rules"""
    print("\n" + "="*70)
    print("TEST 3: Rule Evaluation with Non-Health Metadata (US → Canada)")
    print("="*70)

    payload = {
        "origin_country": "United States",
        "receiving_country": "Canada",
        "pii": True,
        "other_metadata": {
            "customer_email": "email addresses for marketing",
            "customer_name": "full names of customers",
            "purchase_history": "transaction records",
            "loyalty_points": "rewards program data"
        }
    }

    response = requests.post(f"{API_BASE}/api/evaluate-rules", json=payload)
    data = response.json()

    print(f"Status Code: {response.status_code}")
    print(f"Rules Triggered: {data['total_rules_triggered']}")

    print(f"\nMetadata provided (NO health data):")
    for key, value in payload['other_metadata'].items():
        print(f"  - {key}: {value}")

    print(f"\nTriggered Rules:")
    for rule in data['triggered_rules']:
        print(f"  {rule['rule_id']}: {rule['description']}")

    # Verify RULE_11 (health data) is NOT triggered
    rule_ids = [r['rule_id'] for r in data['triggered_rules']]
    if 'RULE_11' in rule_ids:
        print("\n❌ ERROR: RULE_11 (health data) should NOT be triggered!")
    else:
        print("\n✅ PASS: RULE_11 (health data) correctly NOT triggered")


def test_optional_parameters():
    """Test that all parameters are truly optional"""
    print("\n" + "="*70)
    print("TEST 4: Optional Parameters (Ireland → Poland, minimal params)")
    print("="*70)

    payload = {
        "origin_country": "Ireland",
        "receiving_country": "Poland"
        # No pii, no metadata, no process info
    }

    response = requests.post(f"{API_BASE}/api/evaluate-rules", json=payload)
    data = response.json()

    print(f"Status Code: {response.status_code}")
    print(f"Rules Triggered: {data['total_rules_triggered']}")

    for rule in data['triggered_rules']:
        print(f"  {rule['rule_id']}: {rule['description']}")


if __name__ == '__main__':
    print("\n" + "="*70)
    print("TESTING NEW API STRUCTURE")
    print("Simplified parameters with automatic health data detection")
    print("="*70)

    try:
        test_evaluate_rules_basic()
        test_evaluate_rules_with_health_metadata()
        test_evaluate_rules_non_health_metadata()
        test_optional_parameters()

        print("\n" + "="*70)
        print("✅ ALL TESTS COMPLETED")
        print("="*70)

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
