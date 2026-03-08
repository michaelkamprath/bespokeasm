import re

from bespokeasm.assembler.bytecode.parts import ExpressionByteCodePart
from bespokeasm.assembler.bytecode.parts import ExpressionByteCodePartInMemoryZone
from bespokeasm.assembler.bytecode.parts import NumericByteCodePart
from bespokeasm.assembler.line_identifier import LineIdentifier
from bespokeasm.assembler.memory_zone.manager import MemoryZoneManager
from bespokeasm.assembler.model.operand import OperandType
from bespokeasm.assembler.model.operand import OperandWithArgument
from bespokeasm.assembler.model.operand import ParsedOperand
from bespokeasm.assembler.model.operand.operand_label import parse_operand_label_annotation
from bespokeasm.utilities import PATTERN_CHARACTER_ORDINAL


class NumericExpressionOperand(OperandWithArgument):
    def __init__(
        self,
        operand_id: str,
        arg_config_dict: dict,
        default_multi_word_endian: str,
        default_intra_word_endian: str,
        word_size: int,
        word_segment_size: int,
        diagnostic_reporter,
        require_arg: bool = True,
    ) -> None:
        super().__init__(
            operand_id,
            arg_config_dict,
            default_multi_word_endian,
            default_intra_word_endian,
            word_size,
            word_segment_size,
            diagnostic_reporter,
            require_arg=require_arg,
        )

    def __str__(self):
        return f'NumericExpressionOperand<{self.id}>'

    @property
    def type(self) -> OperandType:
        return OperandType.NUMERIC

    @property
    def match_pattern(self) -> str:
        base_pattern = r'(?:[\$\%\w\(\)\+\-\s]*[\w\)])'
        return fr'(?:@(?:[._a-zA-Z][a-zA-Z0-9_]*)\s*:\s*)?{base_pattern}'

    @property
    def enforce_argument_valid_address(self) -> bool:
        return self.config['argument'].get('valid_address', False)

    def _parse_bytecode_parts(
        self,
        line_id: LineIdentifier,
        operand: str,
        register_labels: set[str],
        memzone_manager: MemoryZoneManager,
        operand_label: str | None = None,
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
        return ParsedOperand(
            self,
            bytecode_part,
            arg_part,
            operand,
            self._word_size,
            self._word_segment_size,
            operand_label=operand_label,
        )

    def parse_operand(
        self,
        line_id: LineIdentifier,
        operand: str,
        register_labels: set[str],
        memzone_manager: MemoryZoneManager,
    ) -> ParsedOperand:
        parsed_operand_label = parse_operand_label_annotation(line_id, operand, register_labels, self.type)
        operand = parsed_operand_label.operand_expression
        operand_without_char_literals = re.sub(PATTERN_CHARACTER_ORDINAL, '', operand)
        # do not match if expression contains square brack or curly braces
        punctuation_match = re.search(r'[\[\]\{\}]+', operand_without_char_literals)
        if punctuation_match is not None:
            return None
        try:
            op = self._parse_bytecode_parts(
                line_id,
                operand,
                register_labels,
                memzone_manager,
                operand_label=parsed_operand_label.label_name,
            )
        except SyntaxError:
            return None
        return op
