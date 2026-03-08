from __future__ import annotations

import re
from dataclasses import dataclass

from bespokeasm.assembler.line_identifier import LineIdentifier
from bespokeasm.assembler.model.operand import OperandType
from bespokeasm.utilities import is_valid_label


_OPERAND_LABEL_PATTERN = re.compile(r'@([._a-zA-Z][a-zA-Z0-9_]*):')

_SUPPORTED_OPERAND_LABEL_TYPES = {
    OperandType.NUMERIC,
    OperandType.INDIRECT_NUMERIC,
    OperandType.DEFERRED_NUMERIC,
    OperandType.ADDRESS,
    OperandType.RELATIVE_ADDRESS,
}


class OperandLabelError(ValueError):
    def __init__(self, line_id: LineIdentifier, message: str, category: str = 'user') -> None:
        super().__init__(message)
        self._line_id = line_id
        self._message = message
        self._category = category

    @property
    def line_id(self) -> LineIdentifier:
        return self._line_id

    @property
    def message(self) -> str:
        return self._message

    @property
    def category(self) -> str:
        return self._category


@dataclass(frozen=True)
class ParsedOperandLabel:
    operand_expression: str
    label_name: str | None = None


def supports_operand_labels(operand_type: OperandType) -> bool:
    return operand_type in _SUPPORTED_OPERAND_LABEL_TYPES


def contains_operand_label_annotation(operand_str: str) -> bool:
    stripped = operand_str.strip()
    return bool(_OPERAND_LABEL_PATTERN.search(stripped)) or (stripped.startswith('@') and ':' in stripped)


def parse_operand_label_annotation(
    line_id: LineIdentifier,
    operand_expression: str,
    register_labels: set[str],
    operand_type: OperandType,
) -> ParsedOperandLabel:
    stripped = operand_expression.strip()
    if stripped == '':
        return ParsedOperandLabel(stripped, None)

    matches = list(_OPERAND_LABEL_PATTERN.finditer(stripped))
    if len(matches) == 0:
        # If it looks like operand-label syntax but did not parse, emit targeted syntax guidance.
        if stripped.startswith('@'):
            if ':' not in stripped:
                raise OperandLabelError(
                    line_id,
                    f'Malformed operand-label syntax in "{operand_expression}". '
                    'Expected "@name: expression" (missing ":" after operand-label name).',
                )
            raise OperandLabelError(
                line_id,
                f'Malformed operand-label syntax in "{operand_expression}". Expected "@name: expression".',
            )
        return ParsedOperandLabel(stripped, None)

    if not supports_operand_labels(operand_type):
        raise OperandLabelError(
            line_id,
            f'Operand labels are not supported for operand type "{operand_type.name.lower()}".',
        )

    # Operand labels must prefix the operand expression.
    first_match = matches[0]
    if first_match.start() != 0:
        raise OperandLabelError(
            line_id,
            'Operand-label annotation must appear at the start of the operand expression.',
        )

    if len(matches) > 1:
        raise OperandLabelError(
            line_id,
            'Multiple operand-label annotations on the same operand are not allowed.',
        )

    label_name = first_match.group(1)
    if not is_valid_label(label_name):
        raise OperandLabelError(
            line_id,
            f'Invalid operand-label name "{label_name}".',
        )
    if label_name in register_labels:
        raise OperandLabelError(
            line_id,
            f'Operand-label name "{label_name}" conflicts with a register name.',
        )

    operand_without_label = stripped[first_match.end():].strip()
    if operand_without_label == '':
        raise OperandLabelError(
            line_id,
            'Operand label annotation and operand expression must appear on the same physical line.',
        )

    # Ensure no second annotation remains after stripping the first.
    if _OPERAND_LABEL_PATTERN.search(operand_without_label):
        raise OperandLabelError(
            line_id,
            'Multiple operand-label annotations on the same operand are not allowed.',
        )

    return ParsedOperandLabel(operand_without_label, label_name)
