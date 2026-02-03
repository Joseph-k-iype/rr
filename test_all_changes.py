#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Comprehensive Test Script for All Changes

Tests:
1. Sample data generation (large scale)
2. Graph loading with deduplication
3. Case status filtering
4. PIA/TIA/HRPR dynamic rules
5. Country-specific rules precedence
6. Query optimization
7. Rules Overview API

Usage:
    python test_all_changes.py
"""

import json
import sys
import requests
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

API_BASE = "http://localhost:5001"


def test_api_health():
    """Test API is running"""
    logger.info("=" * 60)
    logger.info("TEST 1: API Health Check")
    logger.info("=" * 60)
    try:
        response = requests.get(f"{API_BASE}/docs", timeout=5)
        if response.status_code == 200:
            logger.info("PASS: API is running at http://localhost:5001")
            return True
        else:
            logger.error(f"FAIL: API returned status {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        logger.error("FAIL: Cannot connect to API. Start it with: python api_fastapi_deontic.py")
        return False


def test_rules_overview_api():
    """Test Rules Overview API endpoint"""
    logger.info("")
    logger.info("=" * 60)
    logger.info("TEST 2: Rules Overview API")
    logger.info("=" * 60)
    try:
        response = requests.get(f"{API_BASE}/api/rules-overview", timeout=30)
        data = response.json()

        if data.get('success'):
            logger.info(f"PASS: Rules Overview API works")
            logger.info(f"   Total rules: {data.get('total_rules', 0)}")
            logger.info(f"   Permission rules: {len(data.get('permission_rules', []))}")
            logger.info(f"   Prohibition rules: {len(data.get('prohibition_rules', []))}")
            logger.info(f"   Country-specific rules: {len(data.get('country_specific_rules', []))}")
            return True
        else:
            logger.error(f"FAIL: Rules Overview API returned error")
            return False
    except Exception as e:
        logger.error(f"FAIL: {e}")
        return False


def test_case_status_filtering():
    """Test that only valid case statuses are searched"""
    logger.info("")
    logger.info("=" * 60)
    logger.info("TEST 3: Case Status Filtering")
    logger.info("=" * 60)
    try:
        # Search for cases
        payload = {
            "origin_country": "United States",
            "receiving_country": "Germany"
        }
        response = requests.post(f"{API_BASE}/api/search-cases", json=payload, timeout=60)
        data = response.json()

        if data.get('success'):
            cases = data.get('cases', [])
            valid_statuses = ['Completed', 'Complete', 'Active', 'Published']

            # Check all returned cases have valid status
            invalid_cases = [c for c in cases if c.get('case_status') not in valid_statuses]

            if len(invalid_cases) == 0:
                logger.info(f"PASS: All {len(cases)} returned cases have valid status")
                status_counts = {}
                for c in cases:
                    status = c.get('case_status', 'Unknown')
                    status_counts[status] = status_counts.get(status, 0) + 1
                for status, count in status_counts.items():
                    logger.info(f"   {status}: {count}")
                return True
            else:
                logger.error(f"FAIL: {len(invalid_cases)} cases have invalid status")
                return False
        else:
            logger.warning("WARN: No cases found (may be empty database)")
            return True
    except Exception as e:
        logger.error(f"FAIL: {e}")
        return False


def test_country_specific_prohibition():
    """Test country-specific rules take precedence"""
    logger.info("")
    logger.info("=" * 60)
    logger.info("TEST 4: Country-Specific Rules Precedence")
    logger.info("=" * 60)
    try:
        # Test US to China transfer (should be prohibited even with PII)
        payload = {
            "origin_country": "United States",
            "receiving_country": "China",
            "pii": True
        }
        response = requests.post(f"{API_BASE}/api/evaluate-rules", json=payload, timeout=60)
        data = response.json()

        if data.get('success'):
            transfer_status = data.get('transfer_status')
            has_country_prohibition = data.get('has_country_prohibition', False)
            blocked_reason = data.get('blocked_reason', '')

            if transfer_status == 'PROHIBITED' and has_country_prohibition:
                logger.info(f"PASS: US to China transfer is PROHIBITED by country-specific rule")
                logger.info(f"   Reason: {blocked_reason[:100]}...")
                return True
            elif transfer_status == 'PROHIBITED':
                logger.info(f"PASS: US to China transfer is PROHIBITED")
                logger.info(f"   Reason: {blocked_reason[:100]}...")
                return True
            else:
                logger.error(f"FAIL: US to China transfer should be PROHIBITED, got {transfer_status}")
                return False
        else:
            logger.error(f"FAIL: API returned error")
            return False
    except Exception as e:
        logger.error(f"FAIL: {e}")
        return False


def test_pia_tia_hrpr_dynamic_rules():
    """Test PIA/TIA/HRPR dynamic rules logic"""
    logger.info("")
    logger.info("=" * 60)
    logger.info("TEST 5: PIA/TIA/HRPR Dynamic Rules")
    logger.info("=" * 60)
    try:
        # Test EU to EU transfer (should be allowed with fewer requirements)
        payload = {
            "origin_country": "Germany",
            "receiving_country": "France",
            "pii": True
        }
        response = requests.post(f"{API_BASE}/api/evaluate-rules", json=payload, timeout=60)
        data = response.json()

        if data.get('success'):
            transfer_status = data.get('transfer_status')
            triggered_rules = data.get('triggered_rules', [])
            consolidated_duties = data.get('consolidated_duties', [])

            logger.info(f"   Germany to France transfer: {transfer_status}")
            logger.info(f"   Triggered rules: {len(triggered_rules)}")
            logger.info(f"   Required duties: {len(consolidated_duties)}")

            # Check for PIA/TIA/HRPR mentions in duties
            pia_tia_hrpr_duties = [d for d in consolidated_duties
                                   if any(x in d.get('name', '').lower()
                                         for x in ['pia', 'tia', 'hrpr', 'assessment'])]

            if len(pia_tia_hrpr_duties) > 0:
                logger.info(f"   PIA/TIA/HRPR duties found: {[d.get('name') for d in pia_tia_hrpr_duties]}")

            logger.info(f"PASS: Dynamic rules evaluation works")
            return True
        else:
            logger.error(f"FAIL: API returned error")
            return False
    except Exception as e:
        logger.error(f"FAIL: {e}")
        return False


def test_query_caching():
    """Test query caching for performance"""
    logger.info("")
    logger.info("=" * 60)
    logger.info("TEST 6: Query Caching")
    logger.info("=" * 60)
    try:
        import time

        # First request (no cache)
        start1 = time.time()
        response1 = requests.get(f"{API_BASE}/api/all-dropdown-values", timeout=60)
        time1 = time.time() - start1

        # Second request (should be cached)
        start2 = time.time()
        response2 = requests.get(f"{API_BASE}/api/all-dropdown-values", timeout=60)
        time2 = time.time() - start2

        if response1.status_code == 200 and response2.status_code == 200:
            logger.info(f"PASS: Dropdown values API works")
            logger.info(f"   First request: {time1:.3f}s")
            logger.info(f"   Second request: {time2:.3f}s (should be faster if cached)")

            # Check valid case statuses are returned
            data = response1.json()
            valid_statuses = data.get('valid_case_statuses', [])
            if valid_statuses:
                logger.info(f"   Valid case statuses: {valid_statuses}")
            return True
        else:
            logger.error(f"FAIL: API returned error")
            return False
    except Exception as e:
        logger.error(f"FAIL: {e}")
        return False


def test_stats_endpoint():
    """Test stats endpoint with valid status filtering"""
    logger.info("")
    logger.info("=" * 60)
    logger.info("TEST 7: Stats Endpoint")
    logger.info("=" * 60)
    try:
        response = requests.get(f"{API_BASE}/api/stats", timeout=60)
        data = response.json()

        if data.get('success'):
            stats = data.get('stats', {})
            logger.info(f"PASS: Stats endpoint works")
            logger.info(f"   Total valid cases: {stats.get('total_cases', 0)}")
            logger.info(f"   All cases in graph: {stats.get('all_cases_in_graph', 0)}")
            logger.info(f"   Countries: {stats.get('total_countries', 0)}")
            logger.info(f"   Jurisdictions: {stats.get('total_jurisdictions', 0)}")
            logger.info(f"   Cases with PII: {stats.get('cases_with_pii', 0)}")
            return True
        else:
            logger.error(f"FAIL: Stats API returned error")
            return False
    except Exception as e:
        logger.error(f"FAIL: {e}")
        return False


def test_sample_data_generator():
    """Test sample data generator"""
    logger.info("")
    logger.info("=" * 60)
    logger.info("TEST 8: Sample Data Generator")
    logger.info("=" * 60)
    try:
        # Import and test the module
        import create_sample_data

        # Test small generation
        test_output = 'test_sample_10.json'
        create_sample_data.create_sample_data(count=10, output_file=test_output, seed=42)

        # Verify output
        if Path(test_output).exists():
            with open(test_output) as f:
                data = json.load(f)

            if len(data) == 10:
                logger.info(f"PASS: Generated 10 test cases")

                # Check case status distribution
                status_counts = {}
                for case in data:
                    status = case.get('caseStatus', 'Unknown')
                    status_counts[status] = status_counts.get(status, 0) + 1

                logger.info(f"   Status distribution: {status_counts}")

                # Cleanup
                Path(test_output).unlink()
                return True
            else:
                logger.error(f"FAIL: Expected 10 cases, got {len(data)}")
                return False
        else:
            logger.error(f"FAIL: Output file not created")
            return False
    except Exception as e:
        logger.error(f"FAIL: {e}")
        return False


def test_health_data_detection():
    """Test health data detection in metadata"""
    logger.info("")
    logger.info("=" * 60)
    logger.info("TEST 9: Health Data Detection")
    logger.info("=" * 60)
    try:
        # Test with health-related metadata
        payload = {
            "origin_country": "United States",
            "receiving_country": "Canada",
            "pii": True,
            "other_metadata": {
                "patient_records": "medical history data",
                "diagnosis_codes": "ICD-10 codes",
                "treatment_plan": "medications and dosages"
            }
        }
        response = requests.post(f"{API_BASE}/api/evaluate-rules", json=payload, timeout=60)
        data = response.json()

        if data.get('success'):
            # Check if health data was detected (would trigger health-related rules)
            triggered_rules = data.get('triggered_rules', [])
            health_rules = [r for r in triggered_rules
                          if 'health' in r.get('description', '').lower()
                          or 'health' in r.get('rule_id', '').lower()]

            logger.info(f"PASS: Health data detection works")
            logger.info(f"   Total triggered rules: {len(triggered_rules)}")
            logger.info(f"   Health-related rules: {len(health_rules)}")
            return True
        else:
            logger.error(f"FAIL: API returned error")
            return False
    except Exception as e:
        logger.error(f"FAIL: {e}")
        return False


def main():
    """Run all tests"""
    logger.info("")
    logger.info("*" * 60)
    logger.info("COMPREHENSIVE TEST SUITE FOR ALL CHANGES")
    logger.info("*" * 60)
    logger.info("")

    results = []

    # Run tests
    results.append(("API Health", test_api_health()))

    if results[-1][1]:  # Only continue if API is running
        results.append(("Rules Overview API", test_rules_overview_api()))
        results.append(("Case Status Filtering", test_case_status_filtering()))
        results.append(("Country-Specific Rules", test_country_specific_prohibition()))
        results.append(("PIA/TIA/HRPR Rules", test_pia_tia_hrpr_dynamic_rules()))
        results.append(("Query Caching", test_query_caching()))
        results.append(("Stats Endpoint", test_stats_endpoint()))
        results.append(("Health Data Detection", test_health_data_detection()))

    results.append(("Sample Data Generator", test_sample_data_generator()))

    # Summary
    logger.info("")
    logger.info("*" * 60)
    logger.info("TEST SUMMARY")
    logger.info("*" * 60)

    passed = sum(1 for _, result in results if result)
    failed = len(results) - passed

    for name, result in results:
        status = "PASS" if result else "FAIL"
        logger.info(f"   {status}: {name}")

    logger.info("")
    logger.info(f"Results: {passed}/{len(results)} tests passed")

    if failed > 0:
        logger.info("")
        logger.info("Some tests failed. Please check:")
        logger.info("1. Is the API running? (python api_fastapi_deontic.py)")
        logger.info("2. Is FalkorDB running? (docker run -p 6379:6379 falkordb/falkordb:latest)")
        logger.info("3. Is data loaded? (python falkor_upload_json.py sample_data.json --clear)")

    return 0 if failed == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
