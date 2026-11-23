"""Tokenizer for ``#annotate <namespace> { key[=value] }`` directive lines."""
from __future__ import annotations

import re

from bespokeasm.assembler.annotations.schema import RawArgument
from bespokeasm.assembler.diagnostic_reporter import AssemblerError
from bespokeasm.assembler.line_identifier import LineIdentifier

DIRECTIVE = '#annotate'

_NAMESPACE_PATTERN = re.compile(r'\s*([A-Za-z][A-Za-z0-9_]*)(?=\s|$)')
_ARGUMENT_PATTERN = re.compile(
    r'''\s*(?P<key>[A-Za-z_][A-Za-z0-9_]*)
        (?:\s*=\s*(?P<value>
            "(?:[^"\\]|\\.)*"            # quoted string
          | '(?:[^'\\]|\\.)'             # character literal
          | [^\s"'=]+                    # symbol word or numeric literal
        ))?
        (?=\s|$)''',
    flags=re.VERBOSE,
)
_ESCAPE_PATTERN = re.compile(r'\\(.)')
# In a quoted value, \n is a line break and \t a tab; any other escaped character stands for itself.
_ESCAPES = {'n': '\n', 't': '\t'}


def parse_annotation_directive(line_id: LineIdentifier, instruction: str) -> tuple[str, list[RawArgument]]:
    """Split an ``#annotate`` line (comment already removed) into its namespace and raw arguments."""
    text = instruction.strip()
    if not text.startswith(DIRECTIVE):
        raise AssemblerError(line_id, f'not an {DIRECTIVE} directive: {text}')
    rest = text[len(DIRECTIVE):]
    namespace_match = _NAMESPACE_PATTERN.match(rest)
    if namespace_match is None:
        raise AssemblerError(
            line_id,
            f'{DIRECTIVE} requires an annotation namespace, for example '
            f'"{DIRECTIVE} listing heading=\\"Tables\\""',
        )
    namespace = namespace_match.group(1)
    position = namespace_match.end()
    arguments: list[RawArgument] = []
    while rest[position:].strip():
        match = _ARGUMENT_PATTERN.match(rest, position)
        if match is None:
            raise AssemblerError(
                line_id,
                f"annotation '{namespace}': cannot parse argument at \"{rest[position:].strip()}\"; "
                'arguments are written key=value or key, and values with spaces are quoted',
            )
        value = match.group('value')
        quoted = value is not None and value.startswith('"')
        if quoted:
            value = _ESCAPE_PATTERN.sub(lambda escape: _ESCAPES.get(escape.group(1), escape.group(1)), value[1:-1])
        arguments.append(RawArgument(match.group('key'), value, quoted))
        position = match.end()
    return namespace, arguments
