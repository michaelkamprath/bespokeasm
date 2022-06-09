import binascii
import click
import io
import math
import os
import sys

from bespokeasm.assembler.assembly_file import AssemblyFile
from bespokeasm.assembler.line_identifier import LineIdentifier
from bespokeasm.assembler.line_object import LineWithBytes, LineObject
from bespokeasm.assembler.line_object.label_line import LabelLine
from bespokeasm.assembler.line_object.predefined_data import PredefinedDataLine
from bespokeasm.assembler.model import AssemblerModel
from bespokeasm.assembler.label_scope import LabelScope


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
        self._binary_fill_value = binary_fill_value & 0xff
        self._verbose = is_verbose
        self._binary_start = binary_start
        self._binary_end = binary_end
        self._model = AssemblerModel(self._config_file, self._verbose)
        self._include_paths = include_paths

    def assemble_bytecode(self):
        global_label_scope = self._model.global_label_scope

        # create the predefined memory blocks
        predefines_lineid = LineIdentifier(0, os.path.basename(self._config_file))
        predefined_line_obs: list[LineObject] = []
        for predefined_memory in self._model.predefined_memory_blocks:
            label: str = predefined_memory['name']
            address: int = predefined_memory['address']
            value: int = predefined_memory['value']
            byte_length: int = predefined_memory['size']
            # create data object
            data_obj = PredefinedDataLine(predefines_lineid, byte_length, value, label)
            data_obj.set_start_address(address)
            predefined_line_obs.append(data_obj)
            # set data object's label
            global_label_scope.set_label_value(label, address, predefines_lineid)

            # add its label to the global scope
        # find base file containing directory
        include_dirs = set([os.path.dirname(self.source_file)]+list(self._include_paths))

        asm_file = AssemblyFile(self.source_file, global_label_scope)
        line_obs: list[LineObject] = asm_file.load_line_objects(self._model, include_dirs, self._verbose)

        if self._verbose > 2:
            click.echo(f'Found {len(line_obs)} lines across all source files')

        # First pass: assign addresses to labels
        cur_address = self._model.default_origin
        for lobj in line_obs:
            lobj.set_start_address(cur_address)
            cur_address = lobj.address + lobj.byte_size
            if isinstance(lobj, LabelLine) and not lobj.is_constant:
                lobj.label_scope.set_label_value(lobj.get_label(), lobj.get_value(), lobj.line_id)

        # now merge prefined line objects and parsed line objects
        line_obs.extend(predefined_line_obs)

        # Sort lines according to their assigned address. This allows for .org directives
        line_obs.sort(key=lambda x: x.address)
        max_generated_address = line_obs[-1].address
        line_dict = {lobj.address: lobj for lobj in line_obs if isinstance(lobj, LineWithBytes)}

        # second pass: build the machine code and check for overlaps
        if self._verbose > 2:
            print("\nProcessing lines:")
        max_instruction_text_size = 0
        byte_code = bytearray()
        last_line = None
        for lobj in line_obs:
            if isinstance(lobj, LineWithBytes):
                lobj.generate_bytes()
            if self._verbose > 2:
                click.echo(f'Processing {lobj.line_id} = {lobj} at address ${lobj.address:x}')
            if len(lobj.instruction) > max_instruction_text_size:
                max_instruction_text_size = len(lobj.instruction)
            if isinstance(lobj, LineWithBytes):
                if last_line is not None and (last_line.address + last_line.byte_size) > lobj.address:
                    print(line_obs)
                    sys.exit(
                        f'ERROR: {lobj.line_id} - Address of byte code at this line overlaps with bytecode from '
                        f'line {last_line.line_id} at address {hex(lobj.address)}'
                    )
                last_line = lobj

        # Finally generate the binaey image
        fill_bytes = bytearray([self._binary_fill_value])
        addr = self._binary_start

        if self._verbose > 2:
            print("\nGenerating byte code:")
        while addr <= (max_generated_address if self._binary_end is None else self._binary_end):
            lobj = line_dict.get(addr, None)
            insertion_bytes = fill_bytes
            if lobj is not None:
                line_bytes = lobj.get_bytes()
                if line_bytes is not None:
                    insertion_bytes = line_bytes
                    if self._verbose > 2:
                        line_bytes_str = binascii.hexlify(line_bytes, sep=' ').decode("utf-8")
                        click.echo(f'Address ${addr:x} : {lobj} bytes = {line_bytes_str}')
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
        for lobj in line_obs:
            line_str = f'{lobj.line_id.line_num}'.rjust(7)
            address_value = lobj.address
            address_str = address_format_str.format(address_value).center(COL_WIDTH_ADDRESS)
            instruction_str = lobj.instruction.ljust(max_instruction_text_size)
            if isinstance(lobj, LineWithBytes):
                line_bytes = lobj.get_bytes()
            else:
                line_bytes = None
            if line_bytes is not None:
                bytes_list = list(line_bytes)
                # print first line
                output.write(
                    f' {line_str} | {instruction_str} | {address_str} | 0x{bytes_list[0]:02x} | '
                    f'{bytes_list[0]:08b} | {lobj.comment}\n'
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
                    f'{blank_binary_text} | {lobj.comment}\n'
                )
        return output.getvalue()
