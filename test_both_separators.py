#!/usr/bin/env python3
"""
Test that both pipe (|) and comma (,) separators work
"""

import sys
sys.path.insert(0, '/Users/josephkiype/Desktop/development/code/deterministic policy')

from falkor_upload_json import parse_pipe_separated

print("=" * 70)
print("TESTING BOTH PIPE (|) AND COMMA (,) SEPARATORS")
print("=" * 70)

test_cases = [
    # Pipe separator
    {
        'input': 'China|India|USA',
        'expected': ['China', 'India', 'USA'],
        'description': 'Pipe separator only'
    },
    # Comma separator
    {
        'input': 'Germany,France,Spain',
        'expected': ['Germany', 'France', 'Spain'],
        'description': 'Comma separator only'
    },
    # Mixed separators
    {
        'input': 'UK|USA,Canada',
        'expected': ['UK', 'USA', 'Canada'],
        'description': 'Mixed pipe and comma'
    },
    {
        'input': 'Japan,Korea|China,India',
        'expected': ['Japan', 'Korea', 'China', 'India'],
        'description': 'Multiple mixed separators'
    },
    # Duplicates with pipe
    {
        'input': 'China|China|India',
        'expected': ['China', 'India'],
        'description': 'Duplicates with pipe'
    },
    # Duplicates with comma
    {
        'input': 'France,Germany,France',
        'expected': ['France', 'Germany'],
        'description': 'Duplicates with comma'
    },
    # Duplicates with mixed separators
    {
        'input': 'US|Canada,US,Mexico|Canada',
        'expected': ['US', 'Canada', 'Mexico'],
        'description': 'Duplicates with mixed separators'
    },
    # Whitespace with pipe
    {
        'input': '  Spain  |  Italy  |  Spain  ',
        'expected': ['Spain', 'Italy'],
        'description': 'Whitespace with pipe'
    },
    # Whitespace with comma
    {
        'input': '  Brazil  ,  Argentina  ,  Brazil  ',
        'expected': ['Brazil', 'Argentina'],
        'description': 'Whitespace with comma'
    },
    # Empty values with pipe
    {
        'input': 'A||B||C',
        'expected': ['A', 'B', 'C'],
        'description': 'Empty values with pipe'
    },
    # Empty values with comma
    {
        'input': 'X,,Y,,Z',
        'expected': ['X', 'Y', 'Z'],
        'description': 'Empty values with comma'
    },
    # Mixed empty values
    {
        'input': 'A|,B,,|C',
        'expected': ['A', 'B', 'C'],
        'description': 'Mixed separators with empty values'
    },
    # Real-world example from user
    {
        'input': 'United States|China|China|India',
        'expected': ['United States', 'China', 'India'],
        'description': 'User example with pipes'
    },
    {
        'input': 'Germany,France,United Kingdom,France,Germany',
        'expected': ['Germany', 'France', 'United Kingdom'],
        'description': 'User example with commas'
    },
    # Complex real-world mixed
    {
        'input': 'Office Support|Customer Service,Office Support,Marketing',
        'expected': ['Office Support', 'Customer Service', 'Marketing'],
        'description': 'Complex mixed separators'
    },
    # Single values
    {
        'input': 'Spain',
        'expected': ['Spain'],
        'description': 'Single value (no separator)'
    },
    {
        'input': '',
        'expected': [],
        'description': 'Empty string'
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
    print("✅ All tests passed! Both separators working correctly.")
    sys.exit(0)
else:
    print("❌ Some tests failed. Check implementation.")
    sys.exit(1)
