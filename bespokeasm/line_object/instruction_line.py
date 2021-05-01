import re
import sys

from bespokeasm.line_object import LineWithBytes
from bespokeasm.utilities import is_string_numeric
from bespokeasm.packed_bits import PackedBits

class MachineCodePart:
    def __init__(self, part_str, label, value, value_size, byte_align):
        self._part_str = part_str.lower()
        self._label = label
        self._value = value
        self._value_size = value_size
        self._byte_align = byte_align

    def part_str(self):
        return self._part_str
    def label(self):
        return self._label
    def value(self):
        return self._value
    def set_value(self, value):
        self._value = value
    def value_size(self):
        return self._value_size
    def byte_align(self):
        return self._byte_align
    def __repr__(self):
        return str(self)
    def __str__(self):
        return f'{{part="{self._part_str}", value={self._value}, value_size={self._value_size}, label={self._label}, align={self._byte_align}}}'
    def __eq__(self, other):
        return \
            self._part_str == other._part_str \
            and self._label == other._label \
            and self._value == other._value \
            and self._value_size == other._value_size \
            and self._byte_align == other._byte_align

class InstructionLine(LineWithBytes):
    COMMAND_EXTRACT_PATTERN = re.compile(r'^\s*(\w+)', flags=re.IGNORECASE|re.MULTILINE)

    def factory(line_num: int, line_str: str, comment: str, isa_model: dict):
        """Tries to contruct a instrion lin object from the passed instruction line"""
        #extract the instruction command
        command_match = re.search(InstructionLine.COMMAND_EXTRACT_PATTERN, line_str)
        if command_match is None or len(command_match.groups()) != 1:
            sys.exit(f'ERROR: line {line_num} - Wrongly formatted instruction: {line_str}')
        command_str = command_match.group(1).strip()
        if command_str not in isa_model['instructions']:
            sys.exit(f'ERROR: line {line_num} - Unreconized instruction: {line_str}')
        argument_str = line_str.strip()[len(command_str):]
        return InstructionLine(line_num, command_str, argument_str, isa_model, line_str, comment)

    def __init__(
            self,
            line_num: int,
            command_str: str,
            argument_str: str,
            isa_model: dict,
            instruction: str,
            comment: str
        ):
        super().__init__(line_num, instruction, comment)
        self._command = command_str
        self._argument_str = argument_str
        self._isa_model = isa_model
        self._command_config = isa_model['instructions'][command_str]
        self._parts = []

        self._parts.append(self._create_instruction_part(self._command))
        self._parts.extend(self._extract_argument_parts(
                self._argument_str,
                self._command_config['arguments'],
                self._isa_model['address_size']
            ))

    def _create_instruction_part(self, command_str):
        return MachineCodePart(
                    self._command,
                    None,
                    self._command_config['bits']['value'],
                    self._command_config['bits']['size'],
                    True
                )

    def _extract_argument_parts(self, args_str, arg_model_list, address_size):
        arg_list = []
        arg_str_list = args_str.split(',')
        if len(arg_str_list) == 1 and arg_str_list[0] == '':
            arg_str_list = []
        # first sanity check we have as many arguments as parts
        if len(arg_str_list) != len(arg_model_list):
            print(
                f'ERROR - argument list size does not match model. args = {arg_str_list}, '
                f'{len(arg_str_list)} != {len(arg_model_list)}'
            )
            return []
        for i in range(len(arg_model_list)):
            arg_model = arg_model_list[i]
            arg_str = arg_str_list[i].strip()
            if arg_model['type'] == 'address':
                arg_list.append(self._create_numeric_part(
                    arg_str,
                    address_size,
                    arg_model['byte_align']
                ))
            elif arg_model['type'] == 'numeric':
                arg_list.append(self._create_numeric_part(
                    arg_str,
                    arg_model['bit_size'],
                    arg_model['byte_align']
                ))
        return arg_list

    def _create_numeric_part(self, arg_str, bit_size, byte_align):
        arg = arg_str.strip()
        if is_string_numeric(arg):
            # its a number
            return MachineCodePart(
                arg_str,
                None,
                parse_numeric_string(arg_str),
                bit_size,
                byte_align
            )
        else:
            # its a label of some sort
            return MachineCodePart(
                arg_str,
                arg_str,
                None,
                bit_size,
                byte_align
            )

    def _calc_byte_size_for_parts(parts_list: list):
        # must calculate byte count even though some values
        # may not have been filled in. This function is class
        # for testability reasons.
        byte_count = 0
        cur_byte_bit_count = 0
        for part in parts_list:
            if part.byte_align() and cur_byte_bit_count > 0:
                byte_count += 1
                cur_byte_bit_count = 0
            cur_byte_bit_count += part.value_size()
            if cur_byte_bit_count > 8:
                byte_count += int(cur_byte_bit_count/8)
                cur_byte_bit_count = cur_byte_bit_count%8
        if cur_byte_bit_count > 0:
            byte_count += 1
        return byte_count

    def byte_size(self) -> int:
        """Returns the number of bytes this instruction will generate"""
        return InstructionLine._calc_byte_size_for_parts(self._parts)

    def generate_bytes(self, label_dict: dict[str, int]) -> bytearray:
        """Finalize the bytes for this line with the label assignemnts"""
        # first set labels as needed
        for p in self._parts:
            if p.label() is not None and p.value() is None:
                if p.label() not in label_dict:
                    sys.exit(f'ERROR: line {self.line_number()} - label "{p.label()}" is undefined')
                p.set_value(label_dict[p.label()])
        # second pass pack the bits
        packed_bits = PackedBits()
        for p in self._parts:
            packed_bits.append_bits(p.value(), p.value_size(), p.byte_align())
        self._bytes.extend(packed_bits.get_bytes())