import binascii
import click
import io
import math
import os
import sys
from bespokeasm.assembler import label_scope

from bespokeasm.assembler.assembly_file import AssemblyFile
from bespokeasm.assembler.line_object import LineWithBytes, LineObject
from bespokeasm.assembler.line_object.directive_line import AddressOrgLine
from bespokeasm.assembler.line_object.label_line import LabelLine
from bespokeasm.assembler.line_object.factory import LineOjectFactory
from bespokeasm.assembler.model import AssemblerModel
from bespokeasm.assembler.label_scope import LabelScope, LabelScopeType

class Assembler:
    def __init__(
            self,
            source_file: str,
            config_file: str,
            output_file: str,
            binary_start: int,
            binary_end: int,
            binary_fill_value: int,
            enable_pretty_print: bool,
            pretty_print_output: str,
            is_verbose: int,
            include_paths: list[str],
        ):
        self.source_file = source_file
        self._output_file = output_file
        self._config_file = config_file
        self._enable_pretty_print = enable_pretty_print
        self._pretty_print_output = pretty_print_output
        self._binary_fill_value = binary_fill_value&0xff
        self._verbose = is_verbose
        self._binary_start = binary_start
        self._binary_end = binary_end
        self._model = AssemblerModel(self._config_file, self._verbose)
        self._include_paths = include_paths

    def assemble_bytecode(self):
        global_label_scope = LabelScope.global_scope(self._model.registers)
        # find base file containing directory
        include_dirs = set([os.path.dirname(self.source_file)]+list(self._include_paths))

        asm_file = AssemblyFile(self.source_file, global_label_scope)
        line_obs = asm_file.load_line_objects(self._model, include_dirs, self._verbose)

        if self._verbose > 2:
            click.echo(f'Found {len(line_obs)} lines across all source files')

        # First pass: assign addresses to labels
        cur_address = 0
        for l in line_obs:
            l.set_start_address(cur_address)
            cur_address = l.address + l.byte_size
            if isinstance(l, LabelLine) and not l.is_constant:
                l.label_scope.set_label_value(l.get_label(), l.get_value(), l.line_id)

        # Sort lines according to their assigned address. This allows for .org directives
        line_obs.sort(key=lambda x: x.address)
        max_generated_address = line_obs[-1].address
        line_dict = { l.address: l for l in line_obs if isinstance(l, LineWithBytes)}

        # second pass: build the machine code and check for overlaps
        if self._verbose > 2:
            print("\nProcessing lines:")
        max_instruction_text_size = 0
        byte_code = bytearray()
        last_line = None
        for l in line_obs:
            if isinstance(l, LineWithBytes):
                l.generate_bytes()
            if self._verbose > 2:
                click.echo(f'Processing {l.line_id} = {l} at address ${l.address:x}')
            if len(l.instruction) > max_instruction_text_size:
                max_instruction_text_size = len(l.instruction)
            if isinstance(l, LineWithBytes):
                if last_line is not None and (last_line.address + last_line.byte_size) > l.address:
                    sys.exit(f'ERROR: {l.line_id} - Address of byte code overlaps with bytecode from line {last_line.line_id}')
                last_line = l

        # Finally generate the binaey image
        fill_bytes = bytearray([self._binary_fill_value])
        addr = self._binary_start

        if self._verbose > 2:
            print("\nGenerating byte code:")
        while addr <= (max_generated_address if self._binary_end is None else self._binary_end):
            l = line_dict.get(addr, None)
            insertion_bytes = fill_bytes
            if l is not None:
                line_bytes = l.get_bytes()
                if line_bytes is not None:
                    insertion_bytes = line_bytes
                    if self._verbose > 2:
                        line_bytes_str = binascii.hexlify(line_bytes, sep=' ').decode("utf-8")
                        click.echo(f'Address ${addr:x} : {l} bytes = {line_bytes_str}')
            byte_code.extend(insertion_bytes)
            addr += len(insertion_bytes)

        click.echo(f'Writing {len(byte_code)} bytes of byte code to {self._output_file}')
        with open(self._output_file, 'wb') as f:
            f.write(byte_code)

        if self._enable_pretty_print:
            pretty_str = self._pretty_print_results(line_obs, max_instruction_text_size)
            if self._pretty_print_output == 'stdout':
                print(pretty_str)
            else:
                with open(self._pretty_print_output, 'w') as f:
                    f.write(pretty_str)



    def _pretty_print_results(self, line_obs, max_instruction_text_size):
        output = io.StringIO()

        address_size = math.ceil(self._model.address_size/4)
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
            line_str = f'{l.line_id.line_num}'.rjust(7)
            address_value = l.address
            address_str = address_format_str.format(address_value).center(COL_WIDTH_ADDRESS)
            instruction_str = l.instruction.ljust(max_instruction_text_size)
            if isinstance(l, LineWithBytes):
                line_bytes = l.get_bytes()
            else:
                line_bytes = None
            if line_bytes is not None:
                bytes_list = list(line_bytes)
                # print first line
                output.write(
                    f' {line_str} | {instruction_str} | {address_str} | 0x{bytes_list[0]:02x} | '
                    f'{bytes_list[0]:08b} | {l.comment}\n'
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
                    f'{blank_binary_text} | {l.comment}\n'
                )
        return output.getvalue()