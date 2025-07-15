from bespokeasm.assembler.bytecode.parts import NumericByteCodePart
from bespokeasm.assembler.line_identifier import LineIdentifier
from bespokeasm.assembler.model.operand import Operand, OperandType, ParsedOperand
from bespokeasm.assembler.memory_zone.manager import MemoryZoneManager


class EmptyOperand(Operand):
    def __init__(
        self,
        operand_id: str,
        arg_config_dict: dict,
        default_multi_word_endian: str,
        default_intra_word_endian: str,
        word_size: int,
        word_segment_size: int,
    ):
        super().__init__(
            operand_id,
            arg_config_dict,
            default_multi_word_endian,
            default_intra_word_endian,
            word_size,
            word_segment_size,
        )

    def __str__(self):
        return f'EmptyOperand<{self.id}>'

    @property
    def type(self) -> OperandType:
        return OperandType.EMPTY

    def null_operand(self) -> bool:
        '''This operand type does not parse any thing from teh instruction'''
        return True

    def parse_operand(
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
        return ParsedOperand(self, bytecode_part, None, operand, self._word_size, self._word_segment_size)
