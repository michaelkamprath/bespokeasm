import re

from bespokeasm.assembler.line_identifier import LineIdentifier
from bespokeasm.assembler.bytecode.parts import \
    NumericByteCodePart, ExpressionByteCodePart, ExpressionByteCodePartInMemoryZone
from bespokeasm.assembler.model.operand import OperandWithArgument, OperandType, ParsedOperand
from bespokeasm.assembler.memory_zone.manager import MemoryZoneManager


class NumericExpressionOperand(OperandWithArgument):
    def __init__(self, operand_id: str, arg_config_dict: dict, default_endian: str, require_arg: bool = True) -> None:
        super().__init__(operand_id, arg_config_dict, default_endian, require_arg)

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
            'big',
            line_id
        ) if self.bytecode_value is not None else None
        if self.enforce_argument_valid_address:
            arg_part = ExpressionByteCodePartInMemoryZone(
                memzone_manager.global_zone,
                operand,
                self.argument_size,
                self.argument_byte_align,
                self.argument_endian,
                line_id,
            )
        else:
            arg_part = ExpressionByteCodePart(
                operand,
                self.argument_size,
                self.argument_byte_align,
                self.argument_endian,
                line_id,
            )
        if arg_part.contains_register_labels(register_labels):
            return None
        return ParsedOperand(self, bytecode_part, arg_part, operand)

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
