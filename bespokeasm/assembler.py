import click
import json
import sys
from bespokeasm.line_parser import LineParser

class Assembler:

    def __init__(self, source_file, config_file, is_verbose):
        self.source_file = source_file
        self._config_file = config_file
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
            click.echo(f'Found {len(label_addresses)} labels: {list(label_addresses.keys())}')
        # second pass: built byte code
        byte_code = bytearray()
        for l in line_obs:
            line_bytes = l.get_bytes(label_addresses)
            if self._verbose > 1:
                click.echo(f'Processing line = {l}, with bytes = {line_bytes}')
            if line_bytes is not None:
                byte_code.extend(line_bytes)

        print('\nAddress | Byte | Binary')
        for i in range(len(byte_code)):
            x = byte_code[i]
            print('0x{0:x} | 0x{1:02x} | {1:08b}'.format(i, x, x))

