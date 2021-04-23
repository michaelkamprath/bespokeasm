def parse_numeric_string(numeric_str):
    if numeric_str.startswith('$'):
        return int(numeric_str[1:], 16)
    elif numeric_str.startswith('0x'):
        return int(numeric_str[2:], 16)
    elif numeric_str.startswith('b'):
        return int(numeric_str[1:], 2)
    else:
        return int(numeric_str)