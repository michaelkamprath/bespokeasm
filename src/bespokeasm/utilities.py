import re

from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap
from ruamel.yaml.comments import CommentedSeq


DEFAULT_NUMERIC_BASE_ALIASES = {
    'decimal': 'decimal',
    'hex': 'hex',
    'hexadecimal': 'hex',
    'base16': 'hex',
    'octal': 'octal',
    'base8': 'octal',
    'binary': 'binary',
    'base2': 'binary',
}
DEFAULT_NUMERIC_BASE_PATTERNS = {
    'decimal': r'\d+',
    'hex': r'[0-9a-fA-F]+',
    'octal': r'[0-7]+',
    'binary': r'[01]+',
}
DEFAULT_NUMERIC_BASE_RADIX = {
    'decimal': 10,
    'hex': 16,
    'octal': 8,
    'binary': 2,
}
PATTERN_HEX = r'(?:\$|0x)[0-9a-fA-F]+|[0-9a-fA-F]+H\b'
PATTERN_CHARACTER_ORDINAL = r"'(?:[^'\\]|\\.)'"
PATTERN_NUMERIC = fr'(?:{PATTERN_HEX}|(?:b|%)[01]+|\d+|{PATTERN_CHARACTER_ORDINAL})'
PATTERN_NUMERIC_COMPILED = re.compile(f'^({PATTERN_NUMERIC})$', flags=re.IGNORECASE | re.MULTILINE)
PATTERN_EXPLICIT_NUMERIC = fr'(?:{PATTERN_HEX}|(?:b|%)[01]+|{PATTERN_CHARACTER_ORDINAL})'
PATTERN_EXPLICIT_NUMERIC_COMPILED = re.compile(
    f'^({PATTERN_EXPLICIT_NUMERIC})$',
    flags=re.IGNORECASE | re.MULTILINE,
)
PATTERN_CHARACTER_ORDINAL_COMPILED = re.compile(
    f'^{PATTERN_CHARACTER_ORDINAL}$',
    flags=re.IGNORECASE | re.MULTILINE,
)


def normalize_default_numeric_base(default_numeric_base: str | None) -> str:
    """Resolve a base name (or alias) to its canonical form: 'decimal', 'hex', 'octal', 'binary'.

    `None` resolves to 'decimal'. Matching is case-insensitive and tolerates surrounding
    whitespace. Aliases (e.g. 'hexadecimal', 'base16', 'base8', 'base2') map to their
    canonical name. Unknown values raise `ValueError`.
    """
    if default_numeric_base is None:
        return 'decimal'
    normalized_base = str(default_numeric_base).strip().lower()
    if normalized_base not in DEFAULT_NUMERIC_BASE_ALIASES:
        raise ValueError(f'Unknown default numeric base: {default_numeric_base}')
    return DEFAULT_NUMERIC_BASE_ALIASES[normalized_base]


def is_explicit_numeric_string(value_str: str) -> bool:
    """True iff `value_str` carries an explicit base prefix/suffix (`0x`, `$`, `b`, `%`,
    trailing `H`) or is a single-character ordinal (e.g. `'A'`).

    Whitespace-only and empty strings return False.
    """
    if value_str.isspace():
        return False
    match = re.match(PATTERN_EXPLICIT_NUMERIC_COMPILED, value_str.strip())
    return match is not None and len(match.groups()) > 0


def is_unprefixed_numeric_string(value_str: str, default_numeric_base: str = 'decimal') -> bool:
    """True iff `value_str` is a bare numeric token whose digits are valid in `default_numeric_base`.

    Whitespace-only and empty strings return False. The base is normalized via
    `normalize_default_numeric_base`, so aliases like 'base16' are accepted.
    """
    if value_str.isspace():
        return False
    normalized_base = normalize_default_numeric_base(default_numeric_base)
    pattern = DEFAULT_NUMERIC_BASE_PATTERNS[normalized_base]
    return re.fullmatch(pattern, value_str.strip(), flags=re.IGNORECASE) is not None


def parse_numeric_string(numeric_str: str, default_numeric_base: str = 'decimal') -> int:
    """Return the integer value of `numeric_str`.

    Supports explicit prefixes/suffixes (`0x`, `$`, trailing `H` for hex; `0b`, `b`, `%` for binary),
    single-character ordinals (e.g. `'A'`, `'\\n'`), and an optional leading `+`/`-` sign.
    Bare digit tokens are interpreted in `default_numeric_base` (decimal/hex/octal/binary).
    Surrounding whitespace is tolerated.

    Raises `ValueError` for: empty strings, sign-only strings (`'+'`, `'-'`),
    multi-character or empty character ordinals, unterminated character literals,
    or digit tokens that aren't valid in the configured base.
    """
    stripped_numeric = numeric_str.strip()
    if stripped_numeric == '':
        raise ValueError('Invalid numeric literal: empty string')

    sign = 1
    unsigned_numeric = stripped_numeric
    if stripped_numeric[0] in ('+', '-'):
        sign = -1 if stripped_numeric[0] == '-' else 1
        unsigned_numeric = stripped_numeric[1:]
        if unsigned_numeric == '':
            raise ValueError(f'Invalid numeric literal: {numeric_str}')

    normalized_base = normalize_default_numeric_base(default_numeric_base)
    lowered_numeric = unsigned_numeric.lower()
    uppered_numeric = unsigned_numeric.upper()
    if unsigned_numeric.startswith('$'):
        return sign * int(unsigned_numeric[1:], 16)
    elif lowered_numeric.startswith('0x'):
        return sign * int(unsigned_numeric[2:], 16)
    elif uppered_numeric.endswith('H'):
        return sign * int(unsigned_numeric[:-1], 16)
    elif lowered_numeric.startswith('0b') and len(unsigned_numeric) > 2:
        return sign * int(unsigned_numeric[2:], 2)
    elif (lowered_numeric.startswith('b') or unsigned_numeric.startswith('%')) and len(unsigned_numeric) > 1:
        return sign * int(unsigned_numeric[1:], 2)
    elif unsigned_numeric.startswith('\'') or unsigned_numeric.startswith('"'):
        match = re.match(PATTERN_CHARACTER_ORDINAL_COMPILED, unsigned_numeric)
        if match is None:
            raise ValueError(f'Invalid character literal: {numeric_str}')
        try:
            decoded_literal = bytes(unsigned_numeric[1:-1], 'utf-8').decode('unicode_escape')
        except UnicodeDecodeError as decode_error:
            raise ValueError(f'Invalid character literal: {numeric_str}') from decode_error
        if len(decoded_literal) != 1:
            raise ValueError(f'Invalid character literal: {numeric_str}')
        return sign * ord(decoded_literal)
    else:
        if not is_unprefixed_numeric_string(unsigned_numeric, normalized_base):
            raise ValueError(
                f'Invalid {normalized_base} numeric literal: {numeric_str}'
            )
        return sign * int(unsigned_numeric, DEFAULT_NUMERIC_BASE_RADIX[normalized_base])


def is_string_numeric(value_str: str, default_numeric_base: str = 'decimal') -> bool:
    """Tests whether the passed string is numeric"""
    if value_str.isspace():
        # strings of only whitespace don't play well with the regex
        return False
    stripped_value = value_str.strip()
    return is_explicit_numeric_string(stripped_value) or is_unprefixed_numeric_string(
        stripped_value,
        default_numeric_base,
    )


PATTERN_GLOBAL_SYMBOL = r'[a-zA-Z][a-zA-Z0-9_]*'
PATTERN_FILE_SYMBOL = r'_(?!_)[a-zA-Z0-9_]+'
PATTERN_LOCAL_SYMBOL = r'\.[a-zA-Z0-9_]+'
PATTERN_SYMBOL = (
    fr'(?:{PATTERN_GLOBAL_SYMBOL}|{PATTERN_FILE_SYMBOL}|{PATTERN_LOCAL_SYMBOL})'
)
PATTERN_CONSTANT_SYMBOL = PATTERN_SYMBOL
PATTERN_ALLOWED_SYMBOLS = re.compile(
    fr'^{PATTERN_SYMBOL}$',
    flags=re.IGNORECASE | re.MULTILINE,
)
# Retain the established public name for callers that treat all assembler
# symbols as labels.
PATTERN_ALLOWED_LABELS = PATTERN_ALLOWED_SYMBOLS


def is_valid_symbol(value: str) -> bool:
    """Return whether a value is a valid global, file, or local symbol name."""
    return PATTERN_ALLOWED_SYMBOLS.fullmatch(value) is not None


def is_valid_label(value: str) -> bool:
    """Return whether a value is a valid assembler label or symbol name."""
    return is_valid_symbol(value)


# Number format preservation utilities
class FormatPreservedInt(int):
    """An integer that remembers its original string representation.

    The numeric value is taken from `value` (parsed if it's a string). The string used
    by `repr`/`str` comes from `original_str` if provided, otherwise from `value` itself
    (or `str(value)` for ints).

    When `original_str` is supplied alongside a `value`, the two must represent the same
    numeric quantity — otherwise `ValueError` is raised. This guards against accidentally
    decoupling the displayed format from the underlying integer (which would silently
    corrupt round-tripped YAML output).

    Note: arithmetic on a FormatPreservedInt returns a plain `int`; format preservation
    does not propagate through operators.
    """

    def __new__(cls, value, original_str=None):
        if isinstance(value, str):
            parsed_value = parse_numeric_string(value)
        else:
            parsed_value = int(value)
        if original_str is not None and parse_numeric_string(original_str) != parsed_value:
            raise ValueError(
                f'FormatPreservedInt: original_str {original_str!r} does not represent '
                f'the same value as {value!r} (parsed as {parsed_value})'
            )
        instance = super().__new__(cls, parsed_value)
        if original_str is not None:
            instance.original_str = original_str
        elif isinstance(value, str):
            instance.original_str = value
        else:
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
    """Recursively walk `obj` and wrap inner lists found under any `disallowed_pairs` key in
    `FlowStyleList` so they serialize as YAML flow sequences.

    Recursion descends through dicts and lists. At a `disallowed_pairs` key, the value's
    direct list children are wrapped, but the wrapping does not recurse further into those
    children — `disallowed_pairs` is expected to contain leaf pair-lists, not nested
    structures. Non-list values under `disallowed_pairs` fall through to the normal
    recursion. Scalars are returned unchanged.
    """
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
                    if (stripped.startswith('0b') and len(stripped) > 2 and all(c in '01' for c in stripped[2:])) or \
                       (stripped.startswith('b') and len(stripped) > 1 and all(c in '01' for c in stripped[1:])):
                        obj[key] = FormatPreservedInt(stripped, stripped)
                    elif (stripped.startswith('0x') and len(stripped) > 2
                          and all(c in '0123456789abcdefABCDEF' for c in stripped[2:])) or \
                         (stripped.startswith('$') and len(stripped) > 1
                          and all(c in '0123456789abcdefABCDEF' for c in stripped[1:])) or \
                         (stripped.endswith('H') and len(stripped) > 1
                          and all(c in '0123456789abcdefABCDEF' for c in stripped[:-1])):
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
                    if (stripped.startswith('0b') and len(stripped) > 2 and all(c in '01' for c in stripped[2:])) or \
                       (stripped.startswith('b') and len(stripped) > 1 and all(c in '01' for c in stripped[1:])):
                        obj[i] = FormatPreservedInt(stripped, stripped)
                    elif (stripped.startswith('0x') and len(stripped) > 2
                          and all(c in '0123456789abcdefABCDEF' for c in stripped[2:])) or \
                         (stripped.startswith('$') and len(stripped) > 1
                          and all(c in '0123456789abcdefABCDEF' for c in stripped[1:])) or \
                         (stripped.endswith('H') and len(stripped) > 1
                          and all(c in '0123456789abcdefABCDEF' for c in stripped[:-1])):
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
