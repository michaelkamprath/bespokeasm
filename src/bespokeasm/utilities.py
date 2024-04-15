import re


PATTERN_HEX = r'(?:\$|0x)[0-9a-fA-F]+|[0-9a-fA-F]+H\b'
PATTERN_NUMERIC = fr'(?:{PATTERN_HEX}|(?:b|%)[01]+|\d+|\'.\')'
PATTERN_NUMERIC_COMPILED = re.compile(f'^({PATTERN_NUMERIC})$', flags=re.IGNORECASE | re.MULTILINE)
PATTERN_CHARACTER_ORDINAL = re.compile(r'\'(.)\'', flags=re.IGNORECASE | re.MULTILINE)


def parse_numeric_string(numeric_str: str) -> int:
    """returns an integer value for the passed numeric string. Supports decimal,
    hexadecimal, and binary numbers. Throws `ValueError` for strings that are not
    parsable.
    """
    if numeric_str.startswith('$'):
        return int(numeric_str[1:], 16)
    elif numeric_str.startswith('0x'):
        return int(numeric_str[2:], 16)
    elif numeric_str.endswith('H'):
        return int(numeric_str[:-1], 16)
    elif numeric_str.startswith('b') or numeric_str.startswith('%'):
        return int(numeric_str[1:], 2)
    elif numeric_str.startswith('\'') or numeric_str.startswith('"'):
        match = re.match(PATTERN_CHARACTER_ORDINAL, numeric_str)
        if match is None:
            raise ValueError(f'Invalid character literal: {numeric_str}')
        return ord(match.group(1))
    else:
        return int(numeric_str)


def is_string_numeric(value_str: str) -> bool:
    """Tests whether the passed string is numeric"""
    if value_str.isspace():
        # strings of only whitespace don't play well with the regex
        return False
    match = re.match(PATTERN_NUMERIC_COMPILED, value_str.strip())
    return match is not None and len(match.groups()) > 0


PATTERN_ALLOWED_LABELS = re.compile(
        r'^(?!__|\.\.)(?:(?:\.|_|[a-zA-Z])[a-zA-Z0-9_]*)$',
        flags=re.IGNORECASE | re.MULTILINE
    )


def is_valid_label(s: str):
    res = re.search(PATTERN_ALLOWED_LABELS, s)
    return (res is not None)
