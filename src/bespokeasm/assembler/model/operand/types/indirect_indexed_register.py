import re

from bespokeasm.assembler.model.operand import OperandType

from .indexed_register import IndexedRegisterOperand


class IndirectIndexedRegisterOperand(IndexedRegisterOperand):
    # `{0}` and `{3}` are the enclosure's opening and closing delimiters, `{1}` the register and
    # `{2}` the index operands' patterns.
    OPERAND_PATTERN_TEMPLATE = r'{0}\s*({1})\s*(\+|\-)\s*({2})\s*{3}'

    def __init__(
        self,
        operand_id: str,
        arg_config_dict: dict,
        default_multi_word_endian: str,
        default_intra_word_endian: str,
        regsiters: set[str],
        word_size: int,
        word_segment_size: int,
        diagnostic_reporter,
    ) -> None:
        super().__init__(
            operand_id,
            arg_config_dict,
            default_multi_word_endian,
            default_intra_word_endian,
            regsiters,
            word_size,
            word_segment_size,
            diagnostic_reporter,
        )

    def __str__(self):
        return f'IndirectIndexedRegisterOperand<{self.id}, register={self.register}, match_pattern={self.match_pattern}>'

    @property
    def type(self) -> OperandType:
        return OperandType.INDIRECT_INDEXED_REGISTER

    @property
    def enclosure_depth(self) -> int:
        return 1

    @property
    def _base_pattern(self) -> str:
        opener, closer = (re.escape(delimiter) for delimiter in self.enclosure_delimiters)
        return IndirectIndexedRegisterOperand.OPERAND_PATTERN_TEMPLATE.format(
            opener, self.register, self._index_parse_pattern, closer,
        )

    @property
    def match_pattern(self) -> str:
        if not self.has_decorator:
            pattern_str = self._base_pattern
        elif self.decorator_is_prefix:
            pattern_str = r'(?<!(?:\+|\-|\d|\w)){}{}'.format(
                self.decorator_pattern,
                self._base_pattern,
            )
        else:
            pattern_str = r'{}{}(?!(?:\+|\-|\d|\w))'.format(
                self._base_pattern,
                self.decorator_pattern,
            )
        return pattern_str
