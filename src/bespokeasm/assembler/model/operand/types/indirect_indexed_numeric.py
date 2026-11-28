import bespokeasm.assembler.model.operand.factory as OF
from bespokeasm.assembler.bytecode.parts import CompositeByteCodePart
from bespokeasm.assembler.line_identifier import LineIdentifier
from bespokeasm.assembler.memory_zone.manager import MemoryZoneManager
from bespokeasm.assembler.model.operand import Operand
from bespokeasm.assembler.model.operand import OperandType
from bespokeasm.assembler.model.operand import ParsedOperand
from bespokeasm.assembler.parsing import top_level_indexes
from bespokeasm.utilities import DEFAULT_INDEX_SEPARATOR
from bespokeasm.utilities import INDEX_SEPARATORS

from .indirect_numeric import IndirectNumericOperand


class IndirectIndexedNumericOperand(IndirectNumericOperand):
    """A numeric expression and an index in the operand's enclosure, separated by the operand's
    `index_separator`, as the 6502's `($40,x)` or `[$1234 + [a+6]]`. The index is one of the
    operand's `index_operands`, which may be any operand type, as for
    `indirect_indexed_register`: its bytecode follows this operand's own, and its argument, if
    any, follows the value's."""

    def __init__(
        self,
        operand_id: str,
        arg_config_dict: dict,
        default_multi_word_endian: str,
        default_intra_word_endian: str,
        registers: set[str],
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
        )
        self._index_operand_list = [
            OF.OperandFactory.factory(
                index_id,
                index_config,
                default_multi_word_endian,
                default_intra_word_endian,
                registers,
                word_size,
                word_segment_size,
                diagnostic_reporter,
                default_numeric_base=self.default_numeric_base,
            )
            for index_id, index_config in self.config['index_operands'].items()
        ]
        # Tried in the same precedence order as the operands of an operand set.
        self._index_operand_list.sort(key=lambda op: op.type.value)

    def __str__(self):
        return f'IndirectIndexedNumericOperand<{self.id},arg_size={self.argument_size}>'

    @property
    def type(self) -> OperandType:
        return OperandType.INDIRECT_INDEXED_NUMERIC

    @property
    def index_operands(self) -> list[Operand]:
        return self._index_operand_list

    @property
    def index_separator(self) -> str:
        """The character between the value and the index: `,` or `+`."""
        return INDEX_SEPARATORS[self.config.get('index_separator', DEFAULT_INDEX_SEPARATOR)]

    @Operand.default_numeric_base.setter
    def default_numeric_base(self, value: str):
        self._default_numeric_base = value
        for operand in self._index_operand_list:
            operand.default_numeric_base = value

    def parse_operand(
        self,
        line_id: LineIdentifier,
        operand: str,
        register_labels: set[str],
        memzone_manager: MemoryZoneManager,
    ) -> ParsedOperand:
        enclosed = self._enclosed_expression(operand)
        if enclosed is None:
            return None
        separators = top_level_indexes(enclosed, self.index_separator)
        # The value may itself contain top-level `+`, so the index is the text after the last
        # top-level `+` that leaves a valid index and a valid value: `$1234 + 2 + [a+6]`.
        for separator in reversed(separators):
            parsed = self._parse_split(
                line_id, operand, enclosed[:separator].strip(), enclosed[separator + 1:].strip(),
                register_labels, memzone_manager,
            )
            if parsed is not None:
                return parsed
        return None

    def _parse_split(
        self,
        line_id: LineIdentifier,
        operand: str,
        value_text: str,
        index_text: str,
        register_labels: set[str],
        memzone_manager: MemoryZoneManager,
    ) -> ParsedOperand:
        parsed_index = next(
            (
                parsed for parsed in (
                    index_operand.parse_operand(line_id, index_text, register_labels, memzone_manager)
                    for index_operand in self._index_operand_list
                )
                if parsed is not None
            ),
            None,
        )
        if parsed_index is None:
            return None
        parsed_value = self._parse_value(line_id, value_text, register_labels, memzone_manager)
        if parsed_value is None:
            return None
        bytecode = parsed_value.bytecode
        if parsed_index.bytecode is not None:
            bytecode = parsed_index.bytecode if bytecode is None else CompositeByteCodePart(
                [bytecode, parsed_index.bytecode],
                bytecode.word_align,
                bytecode.multi_word_endian,
                bytecode.intra_word_endian,
                line_id,
                self._word_size,
                self._word_segment_size,
            )
        return ParsedOperand(
            self,
            bytecode,
            parsed_value.argument,
            operand,
            self._word_size,
            self._word_segment_size,
            operand_label=parsed_value.operand_label,
            trailing_arguments=parsed_index.arguments,
        )
