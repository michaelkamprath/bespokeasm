import re
import sys
from enum import Enum, auto

from bespokeasm.utilities import parse_numeric_string
from bespokeasm.instruction_parser import parse_instruction, MachineCodePart, calc_byte_size_for_parts
from bespokeasm.packed_bits import PackedBits

class LineType(Enum):
    INSTRUCTION = auto()
    LABEL = auto()
    CONSTANT = auto()
    DATA = auto()
    COMMENT = auto()

class LineParser:
    PATTERN_COMMENTS = re.compile(
        r'((?<=\;).*)$',
        flags=re.IGNORECASE|re.MULTILINE
    )
    PATTERN_INSTRUCTION_CONTENT = re.compile(
        r'^([^\;\n]*)',
        flags=re.IGNORECASE|re.MULTILINE
    )
    PATTERN_LABEL = re.compile(
        r'^\s*(\.?\w*):',
        flags=re.IGNORECASE|re.MULTILINE
    )
    PATTERN_CONSTANT = re.compile(
        r'^\s*(\w*)(?:\s*)?\=(?:\s*)?(\$[0-9a-f]*|0x[0-9a-f]*|b[01]*|\w*)',
        flags=re.IGNORECASE|re.MULTILINE
    )

    PATTERN_DATA_DIRECTIVE = re.compile(
        r'^(\.byte)\s*(\$[0-9a-f]*|0x[0-9a-f]*|b[01]*|\d*)',
        flags=re.IGNORECASE|re.MULTILINE
    )

    def __init__(self, line_str, line_num, instruction_model):
        self.line_str = line_str
        self.line_num = line_num
        self._instruction_model = instruction_model

        # init attributes
        self.type = None
        self.label_name = None
        self.label_value = None
        self.parts_list = 0
        self._address = None
        self._bytes = None

        # find comments
        comment_match = re.search(LineParser.PATTERN_COMMENTS, self.line_str)
        if comment_match is not None:
            self._comment = comment_match.group(1).strip()
        else:
            self._comment = ''

        # find instruction
        instruction_match = re.search(LineParser.PATTERN_INSTRUCTION_CONTENT, self.line_str)
        if instruction_match is not None:
            self._instruction_text = instruction_match.group(1).strip()
        else:
            self._instruction_text = ''

        # parse instruction
        if len(self._instruction_text) > 0:
            self._parse_instruction_string(self._instruction_text)
        else:
            self.instruction = ''
            self.type = LineType.COMMENT
            self.bytes = []



    def __repr__(self):
        return str(self)

    def __str__(self):
        if self.type == LineType.INSTRUCTION:
            return f'INSTRUCTION : line_num = {self.line_num}, parts = {self.parts_list}, comment = {self._comment}'
        elif self.type == LineType.LABEL:
            return f'LABEL       : line_num = {self.line_num}, label_name = {self.label_name}'
        elif self.type == LineType.CONSTANT:
            return f'CONSTANT    : line_num = {self.line_num}, label_name = {self.label_name}, label_value = {self.label_value}'
        elif self.type == LineType.DATA:
            return f'DATA        : line_num = {self.line_num}, bytes = {self._bytes}'
        elif self.type == LineType.COMMENT:
            return f'COMMENT     : line_num = {self.line_num}, comment = {self._comment}'
        else:
            return 'UNKNOWN LINE TYPE'

    def _parse_instruction_string(self, instruction_str):
        # first determine if there is a label
        label_match = re.search(LineParser.PATTERN_LABEL, instruction_str)
        if label_match is not None:
            # set this line up as a label
            self._set_up_label(label_match.group(1).strip())
            return

        # Now determine is the line is a constant
        constant_match = re.search(LineParser.PATTERN_CONSTANT, instruction_str)
        if constant_match is not None and len(constant_match.groups()) == 2:
            self._set_up_constant(constant_match.group(1).strip(), constant_match.group(2).strip())
            return

        # is it data directive?
        data_match = re.search(LineParser.PATTERN_DATA_DIRECTIVE, instruction_str)
        if data_match is not None and len(data_match.groups()) == 2:
            self._set_up_data_directive(data_match.group(1).strip(), data_match.group(2).strip())
            return

        # It must be an instruction
        self.parts_list = parse_instruction(instruction_str, self._instruction_model)
        self.instruction = self.parts_list[0].part_str()
        self.type = LineType.INSTRUCTION
        self.bytes = None

    def _set_up_label(self, label_str):
        self.type = LineType.LABEL
        self.label_name = label_str

    def _set_up_constant(self, label_str, constant_str):
        self.type = LineType.CONSTANT
        self.label_name = label_str
        self.label_value = parse_numeric_string(constant_str)

    def _set_up_data_directive(self, directive_str, value_str):
        self.type = LineType.DATA
        if directive_str == '.byte':
            pb = PackedBits()
            pb.append_bits(parse_numeric_string(value_str), 8, True)
            self._bytes = pb.get_bytes()

    def byte_size(self):
        if self.type == LineType.INSTRUCTION:
            return calc_byte_size_for_parts(self.parts_list)
        elif self.type == LineType.DATA:
            return len(self._bytes)
        else:
            return 0

    def set_address(self, address):
        self._address = address
    def get_address(self):
        return self._address

    def get_label(self):
        return self.label_name
    def has_label(self):
        return self.label_name is not None
    def get_label_value(self):
        return self.label_value
    def is_address_label(self):
        return self.type == LineType.LABEL
    def set_address_label_value(self, value):
        if self.is_address_label():
            self.label_value = value

    #
    # these are only for display purposes
    #
    def get_instruction_text(self):
        if self.type in [LineType.INSTRUCTION, LineType.DATA]:
            return '    ' + self._instruction_text
        else:
            return self._instruction_text
    def get_comment_text(self):
        return self._comment

    def get_bytes(self, label_dict):
        if self.type == LineType.INSTRUCTION:
            # first set labels as needed
            for p in self.parts_list:
                if p.label() is not None and p.value() is None:
                    if p.label() not in label_dict:
                        sys.exit(f'ERROR: line {self.line_num} - label "{p.label()}" is undefined')
                    p.set_value(label_dict[p.label()])

            # second pass pack the bits
            packed_bits = PackedBits()
            for p in self.parts_list:
                packed_bits.append_bits(p.value(), p.value_size(), p.byte_align())

            return packed_bits.get_bytes()
        elif self.type == LineType.DATA:
            return self._bytes
        else:
            return None