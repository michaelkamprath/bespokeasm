import re

from bespokeasm.assembler.line_identifier import LineIdentifier
from bespokeasm.assembler.memory_zone.manager import MemoryZoneManager
from bespokeasm.assembler.model.operand import OperandType
from bespokeasm.assembler.model.operand import ParsedOperand
from bespokeasm.assembler.model.operand.operand_label import parse_operand_label_annotation
from bespokeasm.assembler.parsing import encloses_whole

from .numeric_expression import NumericExpressionOperand


class IndirectNumericOperand(NumericExpressionOperand):
    """A numeric expression in the operand's enclosure, `[vec]`, `(vec)` or `{vec}`."""

    def __init__(
        self,
        operand_id: str,
        arg_config_dict: dict,
        default_multi_word_endian: str,
        default_intra_word_endian: str,
        word_size: int,
        word_segment_size: int,
        diagnostic_reporter,
    ):
        super().__init__(
            operand_id,
            arg_config_dict,
            default_multi_word_endian,
            default_intra_word_endian,
            word_size,
            word_segment_size,
            diagnostic_reporter,
            require_arg=True,
        )

    def __str__(self):
        return f'IndirectNumericOperand<{self.id},arg_size={self.argument_size}>'

    @property
    def type(self) -> OperandType:
        return OperandType.INDIRECT_NUMERIC

    @property
    def enclosure_depth(self) -> int:
        return 1

    @property
    def match_pattern(self) -> str:
        opener, closer = (re.escape(delimiter) for delimiter in self.enclosure_delimiters)
        return fr'{opener * self.enclosure_depth}.+{closer * self.enclosure_depth}'

    def _enclosed_expression(self, operand: str) -> str | None:
        """The text inside the operand's enclosure, or None when ``operand`` isn't written in it.
        The expression parser then decides whether the text is an expression: it rejects an
        empty one, and the commas, brackets and braces of other operand forms, such as
        `[[vec]]` read as `[vec]`."""
        opener, closer = self.enclosure_delimiters
        text = operand.strip()
        for _ in range(self.enclosure_depth):
            if not encloses_whole(text, opener, closer):
                return None
            text = text[1:-1].strip()
        return text

    def parse_operand(
        self,
        line_id: LineIdentifier,
        operand: str,
        register_labels: set[str],
        memzone_manager: MemoryZoneManager,
    ) -> ParsedOperand:
        expression = self._enclosed_expression(operand)
        if expression is None:
            return None
        return self._parse_value(line_id, expression, register_labels, memzone_manager)

    def _parse_value(
        self,
        line_id: LineIdentifier,
        expression: str,
        register_labels: set[str],
        memzone_manager: MemoryZoneManager,
    ) -> ParsedOperand | None:
        """The operand's bytecode and argument for ``expression``, which may carry an operand
        label, or None when it isn't a numeric expression."""
        parsed_operand_label = parse_operand_label_annotation(line_id, expression, register_labels, self.type)
        try:
            return self._parse_bytecode_parts(
                line_id,
                parsed_operand_label.operand_expression,
                register_labels,
                memzone_manager,
                operand_label=parsed_operand_label.label_name,
            )
        except SyntaxError:
            return None
