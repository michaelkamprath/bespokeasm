import re
import sys

from bespokeasm.assembler.line_identifier import LineIdentifier
from bespokeasm.assembler.byte_code.parts import NumericByteCodePart, CompositeByteCodePart
from bespokeasm.assembler.model.operand import Operand, OperandType, ParsedOperand
from .register import RegisterOperand

import bespokeasm.assembler.model.operand.factory as OF


class IndirectIndexedRegisterOperand(RegisterOperand):
    _index_operand_list: list[Operand]

    OPERAND_PATTERN_TEMPLATE = r'^\[\s*({0})\s*(\+|\-)\s*({1})\s*\]$'

    def __init__(self, operand_id: str, arg_config_dict: dict, default_endian: str, regsiters: set[str]) -> None:
        super().__init__(operand_id, arg_config_dict, default_endian, regsiters)
        self._index_operand_list = []
        op_match_patterns = []
        for op_id, op_config in self._config['index_operands'].items():
            op = OF.OperandFactory.factory(op_id, op_config, default_endian, regsiters)
            if op.null_operand:
                sys.exit(f'ERROR: indirect indexed register operand "{operand_id}" configured with a empty index "{op_id}".')
            self._index_operand_list.append(op)
            op_match_patterns.append(op.match_pattern)
        # check to see that all operands have the same byte code size
        op_bytecode_size = self._index_operand_list[0].bytecode_size
        for op in self._index_operand_list[1:]:
            if op.bytecode_size != op_bytecode_size:
                sys.exit(f'ERROR - not all index operands confirded with same byte code size for operand "{operand_id}"')

        # Operands are sorted according to matching precedence order, which is set
        # by the enum value of the types. This allows matching to consider an operand
        # as a special register operand (for example) before just saying it's an expression
        self._index_operand_list.sort(key=lambda op: op.type.value, reverse=False)

        self._index_parse_pattern = '|'.join(op_match_patterns)
        self._parse_pattern = re.compile(
            self.match_pattern,
            flags=(re.IGNORECASE | re.MULTILINE),
        )

    def __str__(self):
        return f'IndirectIndexedRegisterOperand<{self.id}, register={self.register}, match_pattern={self.match_pattern}>'

    @property
    def type(self) -> OperandType:
        return OperandType.INDIRECT_INDEXED_REGISTER

    @property
    def match_pattern(self) -> str:
        return self.OPERAND_PATTERN_TEMPLATE.format(self.register, self._index_parse_pattern)

    def parse_operand(self, line_id: LineIdentifier, operand: str, register_labels: set[str]) -> ParsedOperand:
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
            bytecode_part = NumericByteCodePart(self.bytecode_value, self.bytecode_size, False, 'big', line_id) \
                if self.bytecode_value is not None else NumericByteCodePart(0, 0, False, 'big', line_id)
            # find an index operand match
            for index_op in self._index_operand_list:
                parsed_index = index_op.parse_operand(line_id, index_operand_str, register_labels)
                if parsed_index is not None:
                    if parsed_index.byte_code is not None:
                        composit_byte_code = CompositeByteCodePart(
                            [bytecode_part, parsed_index.byte_code],
                            bytecode_part.byte_align,
                            bytecode_part.endian,
                            line_id
                        )
                        return ParsedOperand(self, composit_byte_code, parsed_index.argument, operand)
                    return ParsedOperand(self, bytecode_part, parsed_index.argument, operand)
        return None
