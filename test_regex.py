import re

PATTERN_ALLOWED_LABELS = re.compile(
        r'^(?!__|\.\.)(?:[a-zA-Z](?:[a-zA-Z0-9_]*)|[._][a-zA-Z0-9_]+)$',
        flags=re.IGNORECASE | re.MULTILINE
    )

test_cases = [
    'reserved..',
    'reserved__',
    'reserved..middle',
    'reserved__middle',
    '__reserved',
    '..reserved',
    # Numeric-only test cases
    '123',
    '0',
    '42',
    '999999',
    # Valid labels with numbers
    'a123',
    'label_42',
    'test123abc',
]

for test_case in test_cases:
    result = PATTERN_ALLOWED_LABELS.search(test_case) is not None
    print(f'{test_case}: {result}')
