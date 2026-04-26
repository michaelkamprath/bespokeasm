import re
import sys
from collections.abc import Iterable


DECORATOR_SYMBOLS = {
    'plus': '+',
    'plus_plus': '++',
    'minus': '-',
    'minus_minus': '--',
    'exclamation': '!',
    'at': '@',
}

DECORATOR_REGEX_PATTERNS = {
    decorator_type: re.escape(symbol)
    for decorator_type, symbol in DECORATOR_SYMBOLS.items()
}

DECORATOR_TOKEN_PATTERN = '|'.join(
    sorted((re.escape(symbol) for symbol in DECORATOR_SYMBOLS.values()), key=len, reverse=True)
)

MNEMONIC_TOKEN_PATTERN = re.compile(
    rf'^\s*((?:{DECORATOR_TOKEN_PATTERN})\w[\w._]*|\w[\w._]*(?:{DECORATOR_TOKEN_PATTERN})|\w[\w._]*)',
    flags=re.IGNORECASE | re.MULTILINE,
)


def get_decorator_symbol(
    decorator_config: dict | None,
    *,
    context: str,
) -> tuple[str, bool] | None:
    if not decorator_config or not isinstance(decorator_config, dict):
        return None

    decorator_type = decorator_config.get('type')
    if decorator_type is None:
        sys.exit(f'ERROR - {context} decorator type is not configured.')

    symbol = DECORATOR_SYMBOLS.get(decorator_type)
    if symbol is None:
        sys.exit(
            f'ERROR - {context} uses unknown decorator type "{decorator_type}". '
            f'Allowed values: {", ".join(DECORATOR_SYMBOLS.keys())}'
        )
    return symbol, bool(decorator_config.get('is_prefix', False))


def get_decorator_regex_pattern(
    decorator_config: dict | None,
    *,
    context: str,
) -> str:
    if not decorator_config or not isinstance(decorator_config, dict):
        return ''

    decorator_type = decorator_config.get('type')
    if decorator_type is None:
        sys.exit(f'ERROR - {context} decorator type is not configured.')

    pattern = DECORATOR_REGEX_PATTERNS.get(decorator_type)
    if pattern is None:
        sys.exit(
            f'ERROR - {context} uses unknown decorator type "{decorator_type}". '
            f'Allowed values: {", ".join(DECORATOR_REGEX_PATTERNS.keys())}'
        )
    return pattern


def apply_decorator_symbol(
    root: str,
    decorator_config: dict | None,
    *,
    context: str,
) -> str:
    decorator_info = get_decorator_symbol(decorator_config, context=context)
    if decorator_info is None:
        return root
    symbol, is_prefix = decorator_info
    return f'{symbol}{root}' if is_prefix else f'{root}{symbol}'


def build_mnemonic_alternation(mnemonics: Iterable[str]) -> str:
    escaped_mnemonics = [re.escape(mnemonic) for mnemonic in mnemonics]
    escaped_mnemonics.sort(key=len, reverse=True)
    return '|'.join(escaped_mnemonics)


def split_decorated_mnemonic(token: str) -> tuple[str, str, bool] | None:
    prefix_match = re.match(
        rf'^({DECORATOR_TOKEN_PATTERN})(\w[\w._]*)$',
        token,
        flags=re.IGNORECASE | re.MULTILINE,
    )
    if prefix_match is not None:
        return prefix_match.group(2), prefix_match.group(1), True

    postfix_match = re.match(
        rf'^(\w[\w._]*)({DECORATOR_TOKEN_PATTERN})$',
        token,
        flags=re.IGNORECASE | re.MULTILINE,
    )
    if postfix_match is not None:
        return postfix_match.group(1), postfix_match.group(2), False

    return None
