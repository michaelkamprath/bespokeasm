import binascii
import click
import os
import sys

from bespokeasm.assembler.assembly_file import AssemblyFile
from bespokeasm.assembler.line_identifier import LineIdentifier
from bespokeasm.assembler.line_object import LineWithBytes, LineObject
from bespokeasm.assembler.line_object.label_line import LabelLine
from bespokeasm.assembler.line_object.predefined_data import PredefinedDataLine
from bespokeasm.assembler.memory_zone.manager import MemoryZoneManager
from bespokeasm.assembler.model import AssemblerModel
from bespokeasm.assembler.pretty_printer.factory import PrettyPrinterFactory


class Assembler:
    def __init__(
                self,
                source_file: str,
                config_file: str,
                generate_binary: bool,
                output_file: str,
                binary_start: int,
                binary_end: int,
                binary_fill_value: int,
                enable_pretty_print: bool,
                pretty_print_format: str,
                pretty_print_output: str,
                is_verbose: int,
                include_paths: list[str],
            ):
        self.source_file = source_file
        self._output_file = output_file
        self._config_file = config_file
        self._generate_binary = generate_binary
        self._enable_pretty_print = enable_pretty_print
        self._pretty_print_format = pretty_print_format
        self._pretty_print_output = pretty_print_output
        self._binary_fill_value = binary_fill_value & 0xff
        self._verbose = is_verbose
        self._binary_start = binary_start
        self._binary_end = binary_end
        self._model = AssemblerModel(self._config_file, self._verbose)
        self._include_paths = include_paths

    def assemble_bytecode(self):
        global_label_scope = self._model.global_label_scope
        memzone_manager = MemoryZoneManager(
            self._model.address_size,
            self._model.default_origin,
            self._model.predefined_memory_zones,
        )
        # create the predefined memory blocks
        predefines_lineid = LineIdentifier(0, os.path.basename(self._config_file))
        predefined_line_obs: list[LineObject] = []
        for predefined_memory in self._model.predefined_data_blocks:
            label: str = predefined_memory['name']
            address: int = predefined_memory['address']
            value: int = predefined_memory['value']
            byte_length: int = predefined_memory['size']
            # create data object
            data_obj = PredefinedDataLine(
                predefines_lineid,
                byte_length,
                value,
                label,
                memzone_manager.global_zone,
            )
            data_obj.set_start_address(address)
            predefined_line_obs.append(data_obj)
            # set data object's label
            global_label_scope.set_label_value(label, address, predefines_lineid)

            # add its label to the global scope
        # find base file containing directory
        include_dirs = set([os.path.dirname(self.source_file)]+list(self._include_paths))

        asm_file = AssemblyFile(self.source_file, global_label_scope)
        line_obs: list[LineObject] = asm_file.load_line_objects(
            self._model,
            include_dirs,
            memzone_manager,
            self._verbose
        )

        if self._verbose > 2:
            click.echo(f'Found {len(line_obs)} lines across all source files')

        # First pass: assign addresses to labels
        for lobj in line_obs:
            lobj.set_start_address(lobj.memory_zone.current_address)
            if lobj.address is None:
                sys.exit(f'ERROR: {lobj.line_id} - INTERNAL line object address is None. Memory zone = {lobj.memory_zone}')

            try:
                lobj.memory_zone.current_address = lobj.address + lobj.byte_size
            except ValueError as e:
                sys.exit(f'ERROR: {lobj.line_id} - {str(e)}')

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
        bytecode = bytearray()
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

        if self._generate_binary:
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
                bytecode.extend(insertion_bytes)
                addr += len(insertion_bytes)

            click.echo(f'Writing {len(bytecode)} bytes of byte code to {self._output_file}')
            with open(self._output_file, 'wb') as f:
                f.write(bytecode)
        elif self._verbose > 1:
            print('NOT writing byte code to binary image.')

        if self._enable_pretty_print:
            pprinter = PrettyPrinterFactory.getPrettyPrinter(self._pretty_print_format, line_obs, self._model)
            pretty_str = pprinter.pretty_print(max_instruction_text_size)
            if self._pretty_print_output == 'stdout':
                print(pretty_str)
            else:
                with open(self._pretty_print_output, 'w') as f:
                    f.write(pretty_str)
