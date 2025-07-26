import re

from bespokeasm.assembler.line_identifier import LineIdentifier
from bespokeasm.assembler.bytecode.parts import \
    NumericByteCodePart, ExpressionByteCodePart, ExpressionByteCodePartInMemoryZone
from bespokeasm.assembler.model.operand import OperandWithArgument, OperandType, ParsedOperand
from bespokeasm.assembler.memory_zone.manager import MemoryZoneManager


class NumericExpressionOperand(OperandWithArgument):
    def __init__(
        self,
        operand_id: str,
        arg_config_dict: dict,
        default_multi_word_endian: str,
        default_intra_word_endian: str,
        word_size: int,
        word_segment_size: int,
        require_arg: bool = True,
    ) -> None:
        super().__init__(
            operand_id,
            arg_config_dict,
            default_multi_word_endian,
            default_intra_word_endian,
            word_size,
            word_segment_size,
            require_arg,
        )

    def __str__(self):
        return f'NumericExpressionOperand<{self.id}>'

    @property
    def type(self) -> OperandType:
        return OperandType.NUMERIC

    @property
    def match_pattern(self) -> str:
        return r'(?:[\$\%\w\(\)\+\-\s]*[\w\)])'

    @property
    def enforce_argument_valid_address(self) -> bool:
        return self.config['argument'].get('valid_address', False)

    def _parse_bytecode_parts(
        self,
        line_id: LineIdentifier,
        operand: str,
        register_labels: set[str],
        memzone_manager: MemoryZoneManager,
    ) -> ParsedOperand:
        bytecode_part = NumericByteCodePart(
            self.bytecode_value,
            self.bytecode_size,
            False,
            self._default_multi_word_endian,
            self._default_intra_word_endian,
            line_id,
            self._word_size,
            self._word_segment_size,
        ) if self.bytecode_value is not None else None
        if self.enforce_argument_valid_address:
            arg_part = ExpressionByteCodePartInMemoryZone(
                memzone_manager.global_zone,
                operand,
                self.argument_size,
                self.argument_word_align,
                self.argument_multi_word_endian,
                self.argument_intra_word_endian,
                line_id,
                self._word_size,
                self._word_segment_size,
            )
        else:
            arg_part = ExpressionByteCodePart(
                operand,
                self.argument_size,
                self.argument_word_align,
                self.argument_multi_word_endian,
                self.argument_intra_word_endian,
                line_id,
                self._word_size,
                self._word_segment_size,
            )
        if arg_part.contains_register_labels(register_labels):
            return None
        return ParsedOperand(self, bytecode_part, arg_part, operand, self._word_size, self._word_segment_size)

    def parse_operand(
        self,
        line_id: LineIdentifier,
        operand: str,
        register_labels: set[str],
        memzone_manager: MemoryZoneManager,
    ) -> ParsedOperand:
        # do not match if expression contains square brack or curly braces
        punctuation_match = re.search(r'[\[\]\{\}]+', operand)
        if punctuation_match is not None:
            return None
        try:
            op = self._parse_bytecode_parts(line_id, operand, register_labels, memzone_manager)
        except SyntaxError:
            return None
        return op
