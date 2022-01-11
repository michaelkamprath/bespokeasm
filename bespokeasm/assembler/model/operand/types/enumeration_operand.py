import re
import sys

from bespokeasm.assembler.line_identifier import LineIdentifier
from bespokeasm.assembler.byte_code.parts import NumericByteCodePart
from bespokeasm.assembler.model.operand import OperandWithArgument, OperandType, ParsedOperand

# TODO: Validate that the passed key is not a label of any sort
class EnumerationOperand(OperandWithArgument):
    _bytecode_dictionary: dict[str,int]
    _argument_dictionary: dict[str,int]

    def __init__(self, operand_id: str, arg_config_dict: dict, default_endian: str, registers: set[str]):
        super().__init__(operand_id, arg_config_dict, default_endian)
        self._bytecode_dictionary = None
        if self.has_bytecode:
            self._bytecode_dictionary = self._config['bytecode'].get('value_dict', None)
        self._argument_dictionary = None
        if self.has_argument:
            self._argument_dictionary = self._config['argument'].get('value_dict', None)
        # validate
        if self.has_bytecode_value_dict:
            if registers.intersection(set(self.bytecode_value_dict.keys())):
                sys.exit(f'ERROR - Dictionary key operand "{operand_id}" uses a register label as a key in the byte code dictionary')
        if self.has_argument_value_dict:
            if registers.intersection(set(self.argument_value_dict.keys())):
                sys.exit(f'ERROR - Dictionary key operand "{operand_id}" uses a register label as a key in the argument dictionary')

    def __str__(self):
        return f'DictionaryKey<{self.id}>'

    @property
    def type(self) -> OperandType:
        return OperandType.DICTIONARY_KEY

    @property
    def has_bytecode_value_dict(self) -> bool:
        return self._bytecode_dictionary is not None

    @property
    def bytecode_value_dict(self) -> dict[str,int]:
        return self._bytecode_dictionary

    @property
    def has_argument_value_dict(self) -> bool:
        return self._argument_dictionary is not None

    @property
    def argument_value_dict(self) -> dict[str,int]:
        return self._argument_dictionary


    @property
    def bytecode_value(self) -> int:
        # bytecode value must be looked up in dictionary
        return None

    @property
    def match_pattern(self) -> str:
        if self._argument_dictionary is not None:
            keys_str = '|'.join(self._argument_dictionary.keys())
            return r'\b({0})\b'.format(keys_str)
        else:
            return ''

    def parse_operand(self, line_id: LineIdentifier, operand: str, register_labels: set[str]) -> ParsedOperand:
        match = re.match(self.match_pattern, operand.strip())
        if match is not None and len(match.groups()) > 0:
            matched_key = match.group(1).strip()
            bytecode_part = None
            if self.has_bytecode_value_dict:
                bytecode_value = self.bytecode_value_dict.get(matched_key, None)
                if bytecode_value is not None:
                    bytecode_part = NumericByteCodePart(bytecode_value, self.bytecode_size, False, 'big', line_id)
            arg_part = None
            if self.has_argument_value_dict:
                arg_value = self.argument_value_dict.get(matched_key, None)
                if arg_value is not None:
                    arg_part = NumericByteCodePart(arg_value, self.argument_size, self.argument_byte_align, self.argument_endian, line_id)
            if bytecode_part is None and arg_part is None:
                return None
            return ParsedOperand(self, bytecode_part, arg_part)
        return None