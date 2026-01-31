import re
import sys
from functools import cached_property

import bespokeasm.assembler.model.operand.factory as OF
from bespokeasm.assembler.bytecode.parts import CompositeByteCodePart
from bespokeasm.assembler.bytecode.parts import NumericByteCodePart
from bespokeasm.assembler.line_identifier import LineIdentifier
from bespokeasm.assembler.memory_zone.manager import MemoryZoneManager
from bespokeasm.assembler.model.operand import Operand
from bespokeasm.assembler.model.operand import OperandType
from bespokeasm.assembler.model.operand import ParsedOperand

from .register import RegisterOperand


class IndexedRegisterOperand(RegisterOperand):
    _index_operand_list: list[Operand]

    OPERAND_PATTERN_TEMPLATE = r'({0})\s*(\+|\-)\s*({1})'

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
        self._index_operand_list = []
        op_match_patterns = []
        for op_id, op_config in self._config['index_operands'].items():
            op = OF.OperandFactory.factory(
                op_id,
                op_config,
                default_multi_word_endian,
                default_intra_word_endian,
                regsiters,
                word_size,
                word_segment_size,
                diagnostic_reporter,
            )
            if op.null_operand:
                sys.exit(f'ERROR: indirect indexed register operand "{operand_id}" configured with a empty index "{op_id}".')
            self._index_operand_list.append(op)
            op_match_patterns.append(op.match_pattern)
        # check to see that all operands have the same byte code size
        op_bytecode_size = self._index_operand_list[0].bytecode_size
        for op in self._index_operand_list[1:]:
            if op.bytecode_size != op_bytecode_size:
                sys.exit(f'ERROR - not all index operands configured with same byte code size for operand "{operand_id}"')

        # Operands are sorted according to matching precedence order, which is set
        # by the enum value of the types. This allows matching to consider an operand
        # as a special register operand (for example) before just saying it's an expression
        self._index_operand_list.sort(key=lambda op: op.type.value, reverse=False)

        self._index_parse_pattern = '|'.join(op_match_patterns)
        self._parse_pattern = re.compile(
            fr'^{self.match_pattern}$',
            flags=(re.IGNORECASE | re.MULTILINE),
        )

    def __str__(self):
        return f'IndexedRegisterOperand<{self.id}, register={self.register}, match_pattern={self.match_pattern}>'

    @property
    def type(self) -> OperandType:
        return OperandType.INDEXED_REGISTER

    @cached_property
    def match_pattern(self) -> str:
        return IndexedRegisterOperand.OPERAND_PATTERN_TEMPLATE.format(
            self.register,
            self._index_parse_pattern,
        )

    def parse_operand(
        self,
        line_id: LineIdentifier,
        operand: str,
        register_labels: set[str],
        memzone_manager: MemoryZoneManager,
    ) -> ParsedOperand:
        # first check that operand is what we expect
        match = re.match(self._parse_pattern, operand.strip())
        if match is not None and len(match.groups()) >= 3:
            matched_register = match.group(1)
            if matched_register != self.register:
                return None
            index_operation = match.group(2)
            if index_operation != '+':
                # for now, we only support addition when indexing
                return None
            index_operand_str = match.group(3)
            bytecode_part = NumericByteCodePart(
                self.bytecode_value,
                self.bytecode_size,
                False,
                self._default_multi_word_endian,
                self._default_intra_word_endian,
                line_id,
                self._word_size,
                self._word_segment_size,
            ) if self.bytecode_value is not None else NumericByteCodePart(
                0,
                0,
                False,
                self._default_multi_word_endian,
                self._default_intra_word_endian,
                line_id,
                self._word_size,
                self._word_segment_size,
            )
            # find an index operand match
            for index_op in self._index_operand_list:
                parsed_index: ParsedOperand = index_op.parse_operand(
                    line_id,
                    index_operand_str,
                    register_labels,
                    memzone_manager,
                )
                if parsed_index is not None:
                    if parsed_index.bytecode is not None:
                        composit_bytecode = CompositeByteCodePart(
                            [bytecode_part, parsed_index.bytecode],
                            bytecode_part.word_align,
                            bytecode_part.multi_word_endian,
                            bytecode_part.intra_word_endian,
                            line_id,
                            self._word_size,
                            self._word_segment_size,
                        )
                        return ParsedOperand(
                            self,
                            composit_bytecode,
                            parsed_index.argument,
                            operand,
                            self._word_size,
                            self._word_segment_size,
                        )
                    return ParsedOperand(
                        self,
                        bytecode_part,
                        parsed_index.argument,
                        operand,
                        self._word_size,
                        self._word_segment_size,
                    )
        return None
