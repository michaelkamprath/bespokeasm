import sys

from bespokeasm.assembler.line_identifier import LineIdentifier
from bespokeasm.assembler.bytecode.parts import ExpressionByteCodePartWithValidation
from bespokeasm.assembler.model.operand import Operand, OperandType, ParsedOperand
from bespokeasm.assembler.memory_zone.manager import MemoryZoneManager
from bespokeasm.expression import EXPRESSION_PARTS_PATTERN


class NumericBytecode(Operand):
    def __init__(
        self,
        operand_id: str,
        arg_config_dict: dict,
        default_endian: str,
        word_size: int,
        word_segment_size: int,
    ):
        super().__init__(operand_id, arg_config_dict, default_endian, word_size, word_segment_size)
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
        return EXPRESSION_PARTS_PATTERN

    def parse_operand(
        self,
        line_id: LineIdentifier,
        operand: str,
        register_labels: set[str],
        memzone_manager: MemoryZoneManager,
    ) -> ParsedOperand:
        # do not match if expression contains square bracks
        if '[' in operand or ']' in operand:
            return None

        bytecode_part = ExpressionByteCodePartWithValidation(
            self.bytecode_max,
            self.bytecode_min,
            operand,
            self.bytecode_size,
            False,
            'big',
            line_id,
            self._word_size,
            self._word_segment_size,
        )
        if bytecode_part.contains_register_labels(register_labels):
            return None
        return ParsedOperand(self, bytecode_part, None, operand, self._word_size, self._word_segment_size)
