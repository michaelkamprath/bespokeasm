from bespokeasm.assembler.model.operand import OperandType

from .indexed_register import IndexedRegisterOperand


class IndirectIndexedRegisterOperand(IndexedRegisterOperand):
    OPERAND_PATTERN_TEMPLATE = r'\[\s*({0})\s*(\+|\-)\s*({1})\s*\]'

    def __init__(
        self,
        operand_id: str,
        arg_config_dict: dict,
        default_multi_word_endian: str,
        default_intra_word_endian: str,
        regsiters: set[str],
        word_size: int,
        word_segment_size: int,
    ) -> None:
        super().__init__(
            operand_id,
            arg_config_dict,
            default_multi_word_endian,
            default_intra_word_endian,
            regsiters,
            word_size,
            word_segment_size,
        )

    def __str__(self):
        return f'IndirectIndexedRegisterOperand<{self.id}, register={self.register}, match_pattern={self.match_pattern}>'

    @property
    def type(self) -> OperandType:
        return OperandType.INDIRECT_INDEXED_REGISTER

    @property
    def match_pattern(self) -> str:
        if not self.has_decorator:
            pattern_str = IndirectIndexedRegisterOperand.OPERAND_PATTERN_TEMPLATE.format(
                self.register,
                self._index_parse_pattern,
            )
        elif self.decorator_is_prefix:
            pattern_str = r'(?<!(?:\+|\-|\d|\w)){}{}'.format(
                self.decorator_pattern,
                IndirectIndexedRegisterOperand.OPERAND_PATTERN_TEMPLATE.format(self.register, self._index_parse_pattern),
            )
        else:
            pattern_str = r'{}{}(?!(?:\+|\-|\d|\w))'.format(
                IndirectIndexedRegisterOperand.OPERAND_PATTERN_TEMPLATE.format(self.register, self._index_parse_pattern),
                self.decorator_pattern,
            )
        return pattern_str
