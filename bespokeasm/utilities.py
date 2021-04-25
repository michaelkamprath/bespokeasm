import re

def parse_numeric_string(numeric_str: str) -> int:
    """returns an integer value for the passed numeric string. Supports decimal,
    hexadecimal, and binary numbers
    """
    if numeric_str.startswith('$'):
        return int(numeric_str[1:], 16)
    elif numeric_str.startswith('0x'):
        return int(numeric_str[2:], 16)
    elif numeric_str.startswith('b'):
        return int(numeric_str[1:], 2)
    else:
        return int(numeric_str)

PATTERN_NUMERIC_ARG = re.compile(r'^(\$[0-9a-f]*|0x[0-9a-f]*|b[01]*|\d*)$', flags=re.IGNORECASE|re.MULTILINE)
def is_string_numeric(value_str: str) -> bool:
    """Tests whether the passed string is numeric"""
    if value_str.isspace():
        # strings of only whitespace don't play well with the regex
        return False
    match = re.match(PATTERN_NUMERIC_ARG, value_str.strip())
    return match is not None and len(match.groups()) > 0