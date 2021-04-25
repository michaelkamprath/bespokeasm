import math
import re

from bespokeasm.utilities import parse_numeric_string


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

def parse_instruction(instruction_str, instruction_model):
    parts_list = []
    for instruction in instruction_model['instructions']:
        if instruction_str.lower().startswith(instruction['prefix'].lower()):
            parts_list.append(_create_instruction_part(instruction))
            parts_list.extend(_extract_argument_parts(
                instruction_str[len(instruction['prefix']):].strip(),
                instruction['arguments'],
                instruction_model['address_size']
            ))
            break
    return parts_list

def _create_instruction_part(instruction):
    return MachineCodePart(
                instruction['prefix'],
                None,
                instruction['bits']['value'],
                instruction['bits']['size'],
                True
            )

def _extract_argument_parts(args_str, arg_model_list, address_size):
    arg_list = []
    arg_str_list = args_str.split(',')
    if len(arg_str_list) == 1 and arg_str_list[0] == '':
        arg_str_list = []
    # first sanity check we have as many arguments as parts
    if len(arg_str_list) != len(arg_model_list):
        print(f'ERROR - argument list size does not match mode. args = {arg_str_list}, {len(arg_str_list)} != {len(arg_model_list)}')
        return []
    for i in range(len(arg_model_list)):
        arg_model = arg_model_list[i]
        if arg_model['type'] == 'address':
            arg_list.append(_create_numeric_part(
                arg_str_list[i],
                address_size,
                arg_model['byte_align']
            ))
        elif arg_model['type'] == 'numeric':
            arg_list.append(_create_numeric_part(
                arg_str_list[i],
                arg_model['bit_size'],
                arg_model['byte_align']
            ))
    return arg_list

PATTERN_NUMERIC_ARG = re.compile(r'^(\$[0-9a-f]*|0x[0-9a-f]*|b[01]*|\d*)$', flags=re.IGNORECASE|re.MULTILINE)

def _create_numeric_part(arg_str, bit_size, byte_align):
    match = re.match(PATTERN_NUMERIC_ARG, arg_str.strip())
    if match is not None and len(match.groups()) > 0:
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

def calc_byte_size_for_parts(parts_list):
    # must calculate byte count even though some values
    # may not have been filled in
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