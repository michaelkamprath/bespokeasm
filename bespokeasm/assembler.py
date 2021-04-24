import click
import sys
from line_parser import LineParser

class Assembler:

    def __init__(self, source_file, is_verbose):
        self.source_file = source_file
        self._verbose = is_verbose

    def assemble_bytecode(self):

        line_obs = []
        with open(self.source_file, 'r') as f:
            line_num = 0
            for  line in f:
                line_num += 1
                line_str = line.strip()
                if len(line_str) > 0:
                    line_obs.append(LineParser(line_str, line_num))

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

        print(''.join('0x{:02x}\n'.format(x) for x in byte_code))
