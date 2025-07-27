import re

from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap
from ruamel.yaml.comments import CommentedSeq


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
    elif numeric_str.startswith('0b'):
        return int(numeric_str[2:], 2)
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


# Number format preservation utilities
class FormatPreservedInt(int):
    """An integer that remembers its original string representation."""

    def __new__(cls, value, original_str=None):
        if isinstance(value, str):
            # If value is a string, parse it and store the original
            parsed_value = parse_numeric_string(value)
            instance = super().__new__(cls, parsed_value)
            instance.original_str = value
        else:
            # If value is already an int, use it as is
            instance = super().__new__(cls, value)
            instance.original_str = str(value)
        return instance

    def __repr__(self):
        return self.original_str

    def __str__(self):
        return self.original_str


# YAML formatting utilities
class FlowStyleList(list):
    """A list that forces flow style when dumped to YAML."""
    pass


def convert_disallowed_pairs_to_flow_style(obj):
    """Recursively convert disallowed_pairs inner lists to FlowStyleList."""
    if isinstance(obj, dict):
        result = {}
        for key, value in obj.items():
            if key == 'disallowed_pairs' and isinstance(value, list):
                # Convert inner lists to FlowStyleList
                result[key] = [FlowStyleList(item) if isinstance(item, list) else item for item in value]
            else:
                result[key] = convert_disallowed_pairs_to_flow_style(value)
        return result
    elif isinstance(obj, list):
        return [convert_disallowed_pairs_to_flow_style(item) for item in obj]
    else:
        return obj


def load_yaml_with_format_preservation(yaml_str):
    """Load YAML while preserving number formats and comments."""
    yaml_loader = YAML()
    yaml_loader.preserve_quotes = True
    yaml_loader.indent(mapping=2, sequence=4, offset=2)

    # Load with ruamel.yaml
    config = yaml_loader.load(yaml_str)

    # Convert number values to FormatPreservedInt while preserving comment structure
    def convert_numbers_to_format_preserved(obj):
        if isinstance(obj, CommentedMap):
            for key, value in obj.items():
                if isinstance(value, str) and value.strip():
                    # Apply our number format detection
                    stripped = value.strip()
                    if (stripped.startswith('0b') and all(c in '01' for c in stripped[2:])) or \
                       (stripped.startswith('b') and all(c in '01' for c in stripped[1:])):
                        obj[key] = FormatPreservedInt(stripped, stripped)
                    elif (stripped.startswith('0x') and all(c in '0123456789abcdefABCDEF' for c in stripped[2:])) or \
                         (stripped.startswith('$') and all(c in '0123456789abcdefABCDEF' for c in stripped[1:])) or \
                         (stripped.endswith('H') and all(c in '0123456789abcdefABCDEF' for c in stripped[:-1])):
                        obj[key] = FormatPreservedInt(stripped, stripped)
                    elif stripped.isdigit():
                        obj[key] = FormatPreservedInt(stripped, stripped)
                else:
                    convert_numbers_to_format_preserved(value)
        elif isinstance(obj, CommentedSeq):
            for i, item in enumerate(obj):
                if isinstance(item, str) and item.strip():
                    # Apply our number format detection
                    stripped = item.strip()
                    if (stripped.startswith('0b') and all(c in '01' for c in stripped[2:])) or \
                       (stripped.startswith('b') and all(c in '01' for c in stripped[1:])):
                        obj[i] = FormatPreservedInt(stripped, stripped)
                    elif (stripped.startswith('0x') and all(c in '0123456789abcdefABCDEF' for c in stripped[2:])) or \
                         (stripped.startswith('$') and all(c in '0123456789abcdefABCDEF' for c in stripped[1:])) or \
                         (stripped.endswith('H') and all(c in '0123456789abcdefABCDEF' for c in stripped[:-1])):
                        obj[i] = FormatPreservedInt(stripped, stripped)
                    elif stripped.isdigit():
                        obj[i] = FormatPreservedInt(stripped, stripped)
                else:
                    convert_numbers_to_format_preserved(item)

    convert_numbers_to_format_preserved(config)
    return config


def dump_yaml_with_formatting(updated_dict, output_stream):
    """Dump YAML with proper formatting for disallowed_pairs, preserved number formats, and comments."""
    yaml_dumper = YAML()
    yaml_dumper.preserve_quotes = True
    yaml_dumper.indent(mapping=2, sequence=4, offset=2)

    # Register FlowStyleList representer for ruamel.yaml
    def represent_flow_style_list(self, data):
        return self.represent_sequence('tag:yaml.org,2002:seq', data, flow_style=True)

    yaml_dumper.representer.add_representer(FlowStyleList, represent_flow_style_list)

    # Register FormatPreservedInt representer for ruamel.yaml
    def represent_format_preserved_int(self, data):
        return self.represent_scalar('tag:yaml.org,2002:int', data.original_str)

    yaml_dumper.representer.add_representer(FormatPreservedInt, represent_format_preserved_int)

    # If the input is already a ruamel.yaml object, use it directly
    if isinstance(updated_dict, (CommentedMap, CommentedSeq)):
        # Apply disallowed_pairs formatting to the ruamel object
        def apply_disallowed_pairs_formatting(obj):
            if isinstance(obj, CommentedMap):
                for key, value in obj.items():
                    if key == 'disallowed_pairs' and isinstance(value, CommentedSeq):
                        # Convert inner lists to FlowStyleList
                        for i, item in enumerate(value):
                            if isinstance(item, CommentedSeq):
                                value[i] = FlowStyleList(item)
                    else:
                        apply_disallowed_pairs_formatting(value)
            elif isinstance(obj, CommentedSeq):
                for item in obj:
                    apply_disallowed_pairs_formatting(item)

        apply_disallowed_pairs_formatting(updated_dict)
        yaml_dumper.dump(updated_dict, output_stream)
    else:
        # Convert regular dict to ruamel format and apply formatting
        formatted_dict = convert_disallowed_pairs_to_flow_style(updated_dict)
        yaml_dumper.dump(formatted_dict, output_stream)
