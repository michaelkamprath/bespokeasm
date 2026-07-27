import re

from bespokeasm.assembler.line_identifier import LineIdentifier
from bespokeasm.assembler.line_object import LineObject
from bespokeasm.assembler.memory_zone import MemoryZone
from bespokeasm.expression import ExpressionNode
from bespokeasm.expression import parse_expression
from bespokeasm.utilities import is_valid_label
from bespokeasm.utilities import PATTERN_SYMBOL


class CounterCoordinateLine(LineObject):
    """Zero-width declaration of a scoped coordinate on a flow counter."""

    _PATTERN = re.compile(
        fr'^\s*({PATTERN_SYMBOL})\s*:=\s*(.+?)\s*$',
        flags=re.IGNORECASE,
    )
    _COORDINATE_PATTERN = re.compile(
        fr'^\s*COORDINATE\s*\(\s*({PATTERN_SYMBOL})\s*,\s*(.+)\)\s*$',
        flags=re.IGNORECASE,
    )

    @classmethod
    def factory(
        cls,
        line_id: LineIdentifier,
        line_str: str,
        comment: str,
        current_memzone: MemoryZone,
        default_numeric_base: str,
    ) -> LineObject | None:
        """Parse ``name := COORDINATE(counter, offset)`` before address labels."""
        match = cls._PATTERN.fullmatch(line_str)
        if match is None:
            return None
        label = match.group(1)
        if not is_valid_label(label):
            raise SyntaxError(f'ERROR: {line_id} - invalid coordinate label: {label}')
        counter_name = None
        offset_expression = None
        coordinate_match = cls._COORDINATE_PATTERN.fullmatch(match.group(2))
        if coordinate_match is not None:
            counter_name = coordinate_match.group(1)
            if not is_valid_label(counter_name):
                raise SyntaxError(
                    f'ERROR: {line_id} - invalid flow-counter name: {counter_name}'
                )
            offset_expression = parse_expression(
                line_id,
                coordinate_match.group(2),
                default_numeric_base,
            )
        return cls(
            line_id,
            label,
            counter_name,
            offset_expression,
            line_str,
            comment,
            current_memzone,
        )

    def __init__(
        self,
        line_id: LineIdentifier,
        label: str,
        counter_name: str | None,
        offset_expression: ExpressionNode | None,
        instruction: str,
        comment: str,
        current_memzone: MemoryZone,
    ) -> None:
        super().__init__(line_id, instruction, comment, current_memzone)
        self._label = label
        self._counter_name = counter_name
        self._offset_expression = offset_expression

    @property
    def label(self) -> str:
        """Return the exact scoped spelling declared by the source."""
        return self._label

    @property
    def counter_name(self) -> str | None:
        """Return the counter named by ``COORDINATE()``, if well formed."""
        return self._counter_name

    @property
    def offset_expression(self) -> ExpressionNode | None:
        """Return the ordinary compile-time stack-offset expression."""
        return self._offset_expression
