import sys

from bespokeasm.assembler.line_identifier import LineIdentifier
from bespokeasm.assembler.byte_code.parts import ExpressionByteCodePartWithValidation
from bespokeasm.assembler.model.operand import Operand, OperandType, ParsedOperand


class NumericBytecode(Operand):
    def __init__(self, operand_id: str, arg_config_dict: dict, default_endian: str):
        super().__init__(operand_id, arg_config_dict, default_endian)
        # validate config
        if self.bytecode_max < self.bytecode_min:
            sys.exit(
                f'ERROR - Configuration for operand numeric bytecode {operand_id} '
                f'has a max value {self.bytecode_max} smaller than the min value {self.bytecode_min}'
            )

    def __str__(self):
        return f'NumericBytecode<{self.id}>'

    @property
    def type(self) -> OperandType:
        return OperandType.NUMERIC_BYTECODE

    @property
    def bytecode_value(self) -> int:
        return None

    @property
    def bytecode_max(self) -> int:
        return self._config['bytecode']['max']

    @property
    def bytecode_min(self) -> int:
        return self._config['bytecode']['min']

    @property
    def match_pattern(self) -> str:
        return r'(?:[\$\%\w\(\)\+\-\s]*[\w\)])'

    def parse_operand(self, line_id: LineIdentifier, operand: str, register_labels: set[str]) -> ParsedOperand:
        # do not match if expression contains square bracks
        if "[" in operand or "]" in operand:
            return None

        bytecode_part = ExpressionByteCodePartWithValidation(
            self.bytecode_max,
            self.bytecode_min,
            operand,
            self.bytecode_size,
            False,
            'big',
            line_id
        )
        if bytecode_part.contains_register_labels(register_labels):
            return None
        return ParsedOperand(self, bytecode_part, None)