from bespokeasm.assembler.byte_code.parts import NumericByteCodePart
from bespokeasm.assembler.line_identifier import LineIdentifier
from bespokeasm.assembler.model.operand import Operand, OperandType, ParsedOperand


class EmptyOperand(Operand):
    def __init__(self, operand_id: str, arg_config_dict: dict, default_endian: str):
        super().__init__(operand_id, arg_config_dict, default_endian)

    def __str__(self):
        return f'EmptyOperand<{self.id}>'

    @property
    def type(self) -> OperandType:
        return OperandType.EMPTY

    def null_operand(self) -> bool:
        '''This operand type does not parse any thing from teh instruction'''
        return True

    def parse_operand(self, line_id: LineIdentifier, operand: str, register_labels: set[str]) -> ParsedOperand:
        bytecode_part = NumericByteCodePart(
            self.bytecode_value,
            self.bytecode_size,
            False,
            'big',
            line_id
        ) if self.bytecode_value is not None else None
        return ParsedOperand(self, bytecode_part, None)
