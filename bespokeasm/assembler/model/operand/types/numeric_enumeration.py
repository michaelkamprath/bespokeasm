import re

from bespokeasm.assembler.line_identifier import LineIdentifier
from bespokeasm.assembler.byte_code.parts import ExpressionEnumerationByteCodePart
from bespokeasm.assembler.model.operand import OperandType, ParsedOperand
from bespokeasm.assembler.model.operand.types.numeric_expression import NumericExpressionOperand


class NumericEnumerationOperand(NumericExpressionOperand):
    '''Similar to EnumerationOperand, but allows use of numeric expressions as the key value.'''
    _bytecode_dictionary: dict[int, int]
    _argument_dictionary: dict[int, int]

    def __init__(self, operand_id: str, arg_config_dict: dict, default_endian: str, registers: set[str]):
        super().__init__(operand_id, arg_config_dict, default_endian, False)
        self._bytecode_dictionary = None
        if self.has_bytecode:
            self._bytecode_dictionary = self._config['bytecode'].get('value_dict', None)
        self._argument_dictionary = None
        if self.has_argument:
            self._argument_dictionary = self._config['argument'].get('value_dict', None)

    def __str__(self):
        return f'DictionaryKey<{self.id}>'

    @property
    def type(self) -> OperandType:
        return OperandType.DICTIONARY_KEY

    @property
    def has_bytecode_value_dict(self) -> bool:
        return self._bytecode_dictionary is not None

    @property
    def bytecode_value_dict(self) -> dict[int, int]:
        return self._bytecode_dictionary

    @property
    def has_argument_value_dict(self) -> bool:
        return self._argument_dictionary is not None

    @property
    def argument_value_dict(self) -> dict[int, int]:
        return self._argument_dictionary

    @property
    def bytecode_value(self) -> int:
        # bytecode value must be looked up in dictionary
        return None

    def parse_operand(self, line_id: LineIdentifier, operand: str, register_labels: set[str]) -> ParsedOperand:
        match = re.match(self.match_pattern, operand.strip())
        if match is not None:
            bytecode_part = None
            if self.has_bytecode_value_dict:
                bytecode_part = ExpressionEnumerationByteCodePart(
                    self.bytecode_value_dict,
                    operand,
                    self.bytecode_size,
                    False,
                    'big',
                    line_id
                )
            arg_part = None
            if self.has_argument_value_dict:
                arg_part = ExpressionEnumerationByteCodePart(
                    self.argument_value_dict,
                    operand,
                    self.argument_size,
                    self.argument_byte_align,
                    self.argument_endian,
                    line_id
                )
            if bytecode_part is None and arg_part is None:
                return None
            return ParsedOperand(self, bytecode_part, arg_part, operand)
        return None
