import click
import json
import math
import sys

from bespokeasm.line_parser import LineParser

class Assembler:

    def __init__(self, source_file, config_file, output_file, enable_pretty_print, pretty_print_output, is_verbose):
        self.source_file = source_file
        self._output_file = output_file
        self._config_file = config_file
        self._enable_pretty_print = enable_pretty_print
        self._pretty_print_output = pretty_print_output
        self._verbose = is_verbose

        with open(self._config_file, 'r') as json_file:
            self._config_dict = json.load(json_file)

    def assemble_bytecode(self):

        line_obs = []
        with open(self.source_file, 'r') as f:
            line_num = 0
            for  line in f:
                line_num += 1
                line_str = line.strip()
                if len(line_str) > 0:
                    line_obs.append(LineParser(line_str, line_num, self._config_dict))

        if self._verbose:
            click.echo(f'Found {len(line_obs)} lines in source file')
        # First pass: assign addresses to labels
        cur_address = 0
        label_addresses = {}
        for l in line_obs:
            l.set_address(cur_address)
            cur_address += l.byte_size()
            if l.is_address_label():
                l.set_address_label_value(cur_address)
            if l.has_label():
                if l.get_label() not in label_addresses:
                    label_addresses[l.get_label()] = l.get_label_value()
                else:
                    sys.exit(f'ERROR: line {l.line_num} - label "{l.get_label()}" is defined multiple lines')
        if self._verbose:
            click.echo(f'Found {len(label_addresses)} labels: {label_addresses}')
        # second pass: build byte code
        max_instruction_text_size = 0
        byte_code = bytearray()
        for l in line_obs:
            line_bytes = l.get_bytes(label_addresses)
            if self._verbose > 2:
                click.echo(f'Processing line = {l}, with bytes = {line_bytes}')
            if line_bytes is not None:
                byte_code.extend(line_bytes)
            if len(l.get_instruction_text()) > max_instruction_text_size:
                max_instruction_text_size = len(l.get_instruction_text())

        click.echo(f'Writing {len(byte_code)} bytes of byte code to {self._output_file}')
        with open(self._output_file, 'wb') as f:
            f.write(byte_code)

        self._pretty_print_results(line_obs, max_instruction_text_size, label_addresses)



    def _pretty_print_results(self, line_obs, max_instruction_text_size, label_addresses):
        if self._enable_pretty_print and self._pretty_print_output == 'stdout':
            address_size = math.ceil(self._config_dict['address_size']/4)
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
            print(f'\n{header_text}\n{header_line_text}')
            for l in line_obs:
                line_str = f'{l.line_num}'.rjust(7)
                address_value = l.get_address()
                address_str = address_format_str.format(address_value).center(COL_WIDTH_ADDRESS)
                instruction_str = l.get_instruction_text().ljust(max_instruction_text_size)
                line_bytes = l.get_bytes(label_addresses)
                if line_bytes is not None:
                    bytes_list = list(line_bytes)
                    # print first line
                    print(f' {line_str} | {instruction_str} | {address_str} | 0x{bytes_list[0]:02x} | {bytes_list[0]:08b} | {l.get_comment_text()}')
                    for b in bytes_list[1:]:
                        address_value += 1
                        address_str = address_format_str.format(address_value).rjust(7)
                        print(f'{blank_line_num} | {blank_instruction_text} | {address_str} | 0x{b:02x} | {b:08b} |')
                else:
                    print(f' {line_str} | {instruction_str} | {blank_address_text} | {blank_byte_text} | {blank_binary_text} | {l.get_comment_text()}')