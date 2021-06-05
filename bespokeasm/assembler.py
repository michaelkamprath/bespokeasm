import click
import io
import json
import math
import re
import sys
import yaml

from bespokeasm.line_object import LineWithBytes, LineObject
from bespokeasm.line_object.directive_line import DirectiveLine
from bespokeasm.line_object.label_line import LabelLine
from bespokeasm.line_object.instruction_line import InstructionLine

class Assembler:

    def __init__(self, source_file, config_file, output_file, binary_start, binary_end, enable_pretty_print, pretty_print_output, is_verbose):
        self.source_file = source_file
        self._output_file = output_file
        self._config_file = config_file
        self._enable_pretty_print = enable_pretty_print
        self._pretty_print_output = pretty_print_output
        self._verbose = is_verbose
        self._binary_start = binary_start
        self._binary_end = binary_end

        self._config_dict = self._load_config_dict(self._config_file)

    def _load_config_dict(self, config_file_path: str):
        if config_file_path.endswith('.json'):
            with open(config_file_path, 'r') as json_file:
                return json.load(json_file)
        elif config_file_path.endswith('.yaml'):
            with open(config_file_path, 'r') as yaml_file:
                try:
                    return yaml.safe_load(yaml_file)
                except yaml.YAMLError as exc:
                    sys.exit(f'ERROR: {exc}')
        else:
            sys.exit('ERROR: unknown ISA config file type')

    def assemble_bytecode(self):

        line_obs = []
        with open(self.source_file, 'r') as f:
            line_num = 0
            for  line in f:
                line_num += 1
                line_str = line.strip()
                if len(line_str) > 0:
                    line_obs.append(self._parse_line(line_num, line_str))

        if self._verbose:
            click.echo(f'Found {len(line_obs)} lines in source file')
        # First pass: assign addresses to labels
        cur_address = 0
        label_addresses = {}
        for l in line_obs:
            l.set_start_address(cur_address)
            cur_address = l.address() + l.byte_size()
            if isinstance(l, LabelLine):
                if l.get_label() not in label_addresses:
                    label_addresses[l.get_label()] = l.get_value()
                else:
                    sys.exit(f'ERROR: line {l.line_number()} - label "{l.get_label()}" is defined multiple lines')
        if self._verbose:
            click.echo(f'Found {len(label_addresses)} labels: {label_addresses}')
        # second pass: build byte code
        max_instruction_text_size = 0
        byte_code = bytearray()
        for l in line_obs:
            if isinstance(l, LineWithBytes):
                l.generate_bytes(label_addresses)
                line_bytes = l.get_bytes()
                if self._verbose > 2:
                    click.echo(f'Processing line = {l}, with bytes = {line_bytes}')
                if line_bytes is not None:
                    byte_code.extend(line_bytes)
            if len(l.instruction()) > max_instruction_text_size:
                max_instruction_text_size = len(l.instruction())

        max_address = len(byte_code) if self._binary_end is None else min(self._binary_end + 1, len(byte_code))
        finalized_byte_code = byte_code[self._binary_start:max_address]
        click.echo(f'Writing {len(finalized_byte_code)} bytes of byte code to {self._output_file}')
        with open(self._output_file, 'wb') as f:
            f.write(finalized_byte_code)

        if self._enable_pretty_print:
            pretty_str = self._pretty_print_results(line_obs, max_instruction_text_size, label_addresses)
            if self._pretty_print_output == 'stdout':
                print(pretty_str)
            else:
                with open(self._pretty_print_output, 'w') as f:
                    f.write(pretty_str)

    PATTERN_COMMENTS = re.compile(
        r'((?<=\;).*)$',
        flags=re.IGNORECASE|re.MULTILINE
    )
    PATTERN_INSTRUCTION_CONTENT = re.compile(
        r'^([^\;\n]*)',
        flags=re.IGNORECASE|re.MULTILINE
    )
    def _parse_line(self, line_num: int, line_str: str):
        # find comments
        comment_str = ''
        comment_match = re.search(Assembler.PATTERN_COMMENTS, line_str)
        if comment_match is not None:
            comment_str = comment_match.group(1).strip()

        # find instruction
        instruction_str = ''
        instruction_match = re.search(Assembler.PATTERN_INSTRUCTION_CONTENT, line_str)
        if instruction_match is not None:
            instruction_str = instruction_match.group(1).strip()

        # parse instruction
        if len(instruction_str) > 0:
            # try label
            line_obj = LabelLine.factory(line_num, instruction_str, comment_str)
            if line_obj is not None:
                return line_obj

            # try directives
            line_obj = DirectiveLine.factory(line_num, instruction_str, comment_str)
            if line_obj is not None:
                return line_obj

            # try instruction
            line_obj = InstructionLine.factory(line_num, instruction_str, comment_str, self._config_dict)
            if line_obj is not None:
                return line_obj

        # if we got here, the line is only a comment
        line_obj = LineObject(line_num, instruction_str, comment_str)
        return line_obj

    def _pretty_print_results(self, line_obs, max_instruction_text_size, label_addresses):
        output = io.StringIO()

        address_size = math.ceil(self._config_dict['general']['address_size']/4)
        address_format_str = f'0x{{0:0{address_size}x}}'
        COL_WIDTH_LINE = 7
        COL_WIDTH_ADDRESS = max(address_size + 3, 7)
        COL_WIDTH_BYTE = 4
        COL_WIDTH_BINARY = 8
        blank_line_num = ''.join([' '*COL_WIDTH_LINE])
        blank_instruction_text = ''.join([' '*max_instruction_text_size])
        blank_address_text = ''.join([' '*COL_WIDTH_ADDRESS])
        blank_byte_text = ''.join([' '*COL_WIDTH_BYTE])
        blank_binary_text = ''.join([' '*COL_WIDTH_BINARY])

        header_text = ' {0} | {1} | {2} | {3} | {4} | Comment '.format(
            'Line'.center(COL_WIDTH_LINE),
            'Code'.ljust(max_instruction_text_size),
            'Address'.center(COL_WIDTH_ADDRESS),
            'Byte'.center(COL_WIDTH_BYTE),
            'Binary'.center(COL_WIDTH_BINARY),
        )
        header_line_text = '-{0}-+-{1}-+-{2}-+-{3}-+-{4}-+---------------'.format(
            ''.join('-'*(COL_WIDTH_LINE)),
            ''.join('-'*(max_instruction_text_size)),
            ''.join('-'*(COL_WIDTH_ADDRESS)),
            ''.join('-'*(COL_WIDTH_BYTE)),
            ''.join('-'*(COL_WIDTH_BINARY)),
        )
        output.write(f'\n{header_text}\n{header_line_text}\n')
        for l in line_obs:
            line_str = f'{l.line_number()}'.rjust(7)
            address_value = l.address()
            address_str = address_format_str.format(address_value).center(COL_WIDTH_ADDRESS)
            instruction_str = l.instruction().ljust(max_instruction_text_size)
            if isinstance(l, LineWithBytes):
                line_bytes = l.get_bytes()
            else:
                line_bytes = None
            if line_bytes is not None:
                bytes_list = list(line_bytes)
                # print first line
                output.write(
                    f' {line_str} | {instruction_str} | {address_str} | 0x{bytes_list[0]:02x} | '
                    f'{bytes_list[0]:08b} | {l.comment()}\n'
                )
                for b in bytes_list[1:]:
                    address_value += 1
                    address_str = address_format_str.format(address_value).center(COL_WIDTH_ADDRESS)
                    output.write(
                        f' {blank_line_num} | {blank_instruction_text} | {address_str} | 0x{b:02x} | {b:08b} |\n'
                    )
            else:
                output.write(
                    f' {line_str} | {instruction_str} | {blank_address_text} | {blank_byte_text} | '
                    f'{blank_binary_text} | {l.comment()}\n'
                )
        return output.getvalue()