import re

PATTERN_ALLOWED_LABELS = re.compile(
        r'^(?!__|\.\.)(?:[a-zA-Z](?:[a-zA-Z0-9_]*)|[._][a-zA-Z0-9_]+)$',
        flags=re.IGNORECASE | re.MULTILINE
    )


def is_valid_label(s: str):
    res = re.search(PATTERN_ALLOWED_LABELS, s)
    return (res is not None)
