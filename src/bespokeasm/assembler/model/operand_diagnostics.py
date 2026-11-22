"""Explain why an instruction's operands matched none of its configured forms.

Operand matching is a search: every variant of an instruction, and every operand
definition at every position, is tried in turn and silently rejected until one
accepts. When nothing accepts, the search alone cannot say why. This module re-walks
the candidates for the failed instruction and produces a message that names the first
operand the user got wrong and what would have been accepted in its place.
"""
from __future__ import annotations

from collections.abc import Iterable

from bespokeasm.assembler.diagnostic_reporter import ExpressionSyntaxError
from bespokeasm.assembler.line_identifier import LineIdentifier
from bespokeasm.assembler.memory_zone.manager import MemoryZoneManager
from bespokeasm.assembler.model.operand import Operand
from bespokeasm.assembler.model.operand import OperandType
from bespokeasm.assembler.model.operand_parser import OperandParser
from bespokeasm.expression import parse_expression

_EXPRESSION_OPERAND_TYPES = {
    OperandType.NUMERIC,
    OperandType.NUMERIC_BYTECODE,
    OperandType.ADDRESS,
    OperandType.RELATIVE_ADDRESS,
    OperandType.INDIRECT_NUMERIC,
    OperandType.DEFERRED_NUMERIC,
}


def _plural(count: int, noun: str) -> str:
    if count == 0:
        return f'no {noun}s'
    return f'{count} {noun}{"" if count == 1 else "s"}'


def _quote(text: str) -> str:
    # Operands that are themselves double-quoted strings read better unwrapped.
    return text if '"' in text else f'"{text}"'


def _quote_list(items: Iterable[str]) -> str:
    return ', '.join(_quote(item) for item in items)


def _join_or(items: list[str]) -> str:
    if len(items) <= 1:
        return ''.join(items)
    return ', '.join(items[:-1]) + f', or {items[-1]}'


def describe_operands(operands: list[Operand]) -> str:
    """Return a human-readable summary of the forms a set of operand definitions accepts."""
    registers: list[str] = []
    others: list[str] = []
    for operand in operands:
        kind = operand.type
        if kind == OperandType.EMPTY:
            continue
        if kind == OperandType.REGISTER:
            name = operand.register
            if getattr(operand, 'has_decorator', False):
                decorator = operand.config['decorator'].get('type', '')
                name = f'{decorator}{name}' if operand.decorator_is_prefix else f'{name}{decorator}'
            if name not in registers:
                registers.append(name)
            continue
        if kind == OperandType.INDIRECT_REGISTER:
            text = f'[{operand.register}]'
            if getattr(operand, 'has_offset', False):
                text = f'[{operand.register}] or [{operand.register} + offset]'
        elif kind == OperandType.INDEXED_REGISTER:
            text = f'{operand.register} + index'
        elif kind == OperandType.INDIRECT_INDEXED_REGISTER:
            text = f'[{operand.register} + index]'
        elif kind == OperandType.NUMERIC:
            text = 'a numeric value or expression'
        elif kind == OperandType.NUMERIC_BYTECODE:
            text = f'a numeric value from {operand.bytecode_min} to {operand.bytecode_max}'
        elif kind == OperandType.ADDRESS:
            text = 'an address'
        elif kind == OperandType.RELATIVE_ADDRESS:
            text = 'a relative address'
        elif kind == OperandType.INDIRECT_NUMERIC:
            text = '[address]'
        elif kind == OperandType.DEFERRED_NUMERIC:
            text = '[[address]]'
        elif kind == OperandType.DICTIONARY_KEY:
            keys = (
                operand.argument_value_dict if operand.has_argument_value_dict
                else operand.bytecode_value_dict
            ) or {}
            text = f'one of {", ".join(str(key) for key in keys)}'
        else:
            text = str(operand)
        if text not in others:
            others.append(text)
    parts: list[str] = []
    if registers:
        parts.append(f'register {", ".join(registers)}' if len(registers) == 1 else f'a register ({", ".join(registers)})')
    parts.extend(others)
    return _join_or(parts)


class OperandMismatchExplainer:
    def __init__(
        self,
        kind: str,
        mnemonic: str,
        variants: Iterable,
        line_id: LineIdentifier,
        operands: list[str],
        registers: set[str],
        memzone_manager: MemoryZoneManager,
        default_numeric_base: str,
    ) -> None:
        self._kind = kind
        self._mnemonic = mnemonic
        self._parsers: list[OperandParser | None] = [variant._operand_parser for variant in variants]
        self._line_id = line_id
        self._operands = operands
        self._registers = registers
        self._memzone_manager = memzone_manager
        self._default_numeric_base = default_numeric_base

    @property
    def _subject(self) -> str:
        return f'{self._kind} "{self._mnemonic}"'

    def explain(self) -> str:
        given_count = len(self._operands)
        accepted_counts: set[int] = set()
        for parser in self._parsers:
            accepted_counts.update(parser.source_operand_counts() if parser is not None else {0})

        if given_count not in accepted_counts:
            return self._explain_count_mismatch(given_count, accepted_counts)

        for index, operand_text in enumerate(self._operands):
            if operand_text.strip() == '':
                return f'operand {index + 1} of {self._subject} is empty'

        best_failure: tuple[int, list[Operand]] | None = None
        for parser in self._parsers:
            if parser is None or given_count not in parser.source_operand_counts():
                continue
            failure = self._first_failing_position(parser, given_count)
            if failure is None:
                disallowed = parser.disallowed_combination(
                    self._line_id, self._operands, self._registers, self._memzone_manager,
                )
                if disallowed is not None:
                    return (
                        f'the operand combination {_quote_list(self._operands)} is not allowed '
                        f'for {self._subject}'
                    )
                continue
            if best_failure is None or failure[0] > best_failure[0]:
                best_failure = failure

        if best_failure is None:
            return (
                f'{self._subject} does not accept the operands {_quote_list(self._operands)}'
            )
        position, candidates = best_failure
        return self._explain_operand(position, candidates)

    def _explain_count_mismatch(self, given_count: int, accepted_counts: set[int]) -> str:
        accepted = sorted(accepted_counts)
        if len(accepted) == 1:
            takes = _plural(accepted[0], 'operand')
        else:
            takes = f'{" or ".join(str(count) for count in accepted)} operands'
        given = f'{given_count} {"was" if given_count == 1 else "were"} given'
        if given_count > 0:
            given += f' ({_quote_list(self._operands)})'
        return f'{self._subject} takes {takes}, but {given}'

    def _first_failing_position(self, parser: OperandParser, given_count: int) -> tuple[int, list[Operand]] | None:
        for position, operand_text in enumerate(self._operands):
            candidates = parser.candidate_operands(position, given_count)
            if not candidates:
                return position, candidates
            if not any(self._accepts(candidate, operand_text) for candidate in candidates):
                return position, candidates
        return None

    def _accepts(self, candidate: Operand, operand_text: str) -> bool:
        try:
            return candidate.parse_operand(
                self._line_id, operand_text, self._registers, self._memzone_manager,
            ) is not None
        except Exception:
            return False

    def _explain_operand(self, position: int, candidates: list[Operand]) -> str:
        operand_text = self._operands[position]
        prefix = f'operand {position + 1} {_quote(operand_text)} of {self._subject}'
        expects_expression = any(candidate.type in _EXPRESSION_OPERAND_TYPES for candidate in candidates)
        if expects_expression:
            expression_text = operand_text
            for opener, closer in (('[[', ']]'), ('[', ']')):
                if expression_text.startswith(opener) and expression_text.endswith(closer):
                    expression_text = expression_text[len(opener):-len(closer)]
                    break
            try:
                expression = parse_expression(self._line_id, expression_text, self._default_numeric_base)
            except ExpressionSyntaxError as error:
                return f'{prefix}: {error.message}'
            except Exception:
                expression = None
            if expression is not None and expression.contains_register_labels(self._registers):
                used = sorted(expression.contained_labels() & self._registers)
                return f'{prefix} uses register {_quote_list(used)} in a numeric expression'
        expected = describe_operands(candidates)
        if expected:
            return f'{prefix} is not valid; expected {expected}'
        return f'{prefix} is not valid'


def explain_operand_mismatch(
    kind: str,
    mnemonic: str,
    variants: Iterable,
    line_id: LineIdentifier,
    operands: list[str],
    registers: set[str],
    memzone_manager: MemoryZoneManager,
    default_numeric_base: str,
) -> str:
    """Return a message explaining why ``operands`` matched no variant of ``mnemonic``."""
    return OperandMismatchExplainer(
        kind, mnemonic, variants, line_id, operands, registers, memzone_manager, default_numeric_base,
    ).explain()
