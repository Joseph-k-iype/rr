#!/usr/bin/env python3
"""
Test deduplication functionality in falkor_upload_json.py
"""

import sys
sys.path.insert(0, '/Users/josephkiype/Desktop/development/code/deterministic policy')

from falkor_upload_json import parse_pipe_separated

print("=" * 70)
print("TESTING DEDUPLICATION")
print("=" * 70)

# Test cases with duplicates
test_cases = [
    {
        'input': 'China|China|India',
        'expected': ['China', 'India'],
        'description': 'Duplicate China'
    },
    {
        'input': 'United States|China|China|India',
        'expected': ['United States', 'China', 'India'],
        'description': 'Duplicate China in middle'
    },
    {
        'input': 'Germany|France|United Kingdom|France',
        'expected': ['Germany', 'France', 'United Kingdom'],
        'description': 'Duplicate France at end'
    },
    {
        'input': 'Marketing|Analytics|Marketing|Sales|Analytics',
        'expected': ['Marketing', 'Analytics', 'Sales'],
        'description': 'Multiple duplicates'
    },
    {
        'input': 'PII|Financial Data|PII|PII|Health Data',
        'expected': ['PII', 'Financial Data', 'Health Data'],
        'description': 'Triple duplicate PII'
    },
    {
        'input': 'Spain',
        'expected': ['Spain'],
        'description': 'Single value no duplicates'
    },
    {
        'input': '',
        'expected': [],
        'description': 'Empty string'
    },
    {
        'input': 'A|B|C|B|A|C|A',
        'expected': ['A', 'B', 'C'],
        'description': 'Complex duplicates'
    },
    {
        'input': '  Germany  |  France  |  Germany  ',
        'expected': ['Germany', 'France'],
        'description': 'Whitespace and duplicates'
    },
    {
        'input': 'X||Y||X',
        'expected': ['X', 'Y'],
        'description': 'Empty values and duplicates'
    }
]

print("\n📋 Running test cases...\n")

passed = 0
failed = 0

for i, test in enumerate(test_cases, 1):
    result = parse_pipe_separated(test['input'])
    expected = test['expected']

    if result == expected:
        print(f"✅ Test {i}: {test['description']}")
        print(f"   Input:    '{test['input']}'")
        print(f"   Output:   {result}")
        print(f"   Expected: {expected}")
        passed += 1
    else:
        print(f"❌ Test {i}: {test['description']}")
        print(f"   Input:    '{test['input']}'")
        print(f"   Output:   {result}")
        print(f"   Expected: {expected}")
        failed += 1
    print()

print("=" * 70)
print(f"RESULTS: {passed} passed, {failed} failed")
print("=" * 70)

if failed == 0:
    print("✅ All tests passed! Deduplication is working correctly.")
    sys.exit(0)
else:
    print("❌ Some tests failed. Check implementation.")
    sys.exit(1)
