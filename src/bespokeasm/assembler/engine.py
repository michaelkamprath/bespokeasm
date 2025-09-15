import os
import sys

import click
from bespokeasm.assembler.assembly_file import AssemblyFile
from bespokeasm.assembler.bytecode.word import Word
from bespokeasm.assembler.label_scope import LabelScopeType
from bespokeasm.assembler.line_identifier import LineIdentifier
from bespokeasm.assembler.line_object import LineObject
from bespokeasm.assembler.line_object import LineWithWords
from bespokeasm.assembler.line_object.label_line import LabelLine
from bespokeasm.assembler.line_object.predefined_data import PredefinedDataLine
from bespokeasm.assembler.memory_zone.manager import MemoryZoneManager
from bespokeasm.assembler.model import AssemblerModel
from bespokeasm.assembler.preprocessor import Preprocessor
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
                predefined: list[str],
            ):
        self._source_file = source_file
        self._output_file = output_file
        self._config_file = config_file
        self._generate_binary = generate_binary
        self._enable_pretty_print = enable_pretty_print
        self._pretty_print_format = pretty_print_format
        self._pretty_print_output = pretty_print_output
        self._binary_fill_value = binary_fill_value
        self._verbose = is_verbose
        self._binary_start = binary_start
        self._binary_end = binary_end
        self._model = AssemblerModel(self._config_file, self._verbose)
        self._include_paths = include_paths
        self._predefined_symbols = predefined

    def assemble_bytecode(self):
        global_label_scope = self._model.global_label_scope
        memzone_manager = MemoryZoneManager(
            self._model.address_size,
            self._model.default_origin,
            self._model.predefined_memory_zones,
        )

        # create preprocessor
        preprocessor: Preprocessor = Preprocessor(self._model.predefined_symbols, self._model)
        # add any predefined macros from the command line
        preprocessor.add_cli_symbols(self._predefined_symbols)

        # create the predefined memory blocks
        predefines_lineid = LineIdentifier(0, os.path.basename(self._config_file))
        predefined_line_obs: list[LineObject] = []
        for predefined_memory in self._model.predefined_data_blocks:
            label: str = predefined_memory['name']
            address: int = predefined_memory['address']
            value: int = predefined_memory['value']
            word_length: int = predefined_memory['size']
            # create data object
            data_obj = PredefinedDataLine(
                predefines_lineid,
                word_length,
                value,
                label,
                memzone_manager.global_zone,
                self._model.word_size,
                self._model.word_segment_size,
                self._model.intra_word_endianness,
                self._model.multi_word_endianness,
            )
            data_obj.set_start_address(address)
            predefined_line_obs.append(data_obj)
            # set data object's label
            global_label_scope.set_label_value(
                label,
                address,
                predefines_lineid,
                scope=LabelScopeType.GLOBAL,
            )

            # add its label to the global scope
        # find base file containing directory
        include_dirs = [os.path.dirname(self._source_file)]+list(self._include_paths)
        # Deduplicate the include directories.
        # This search approach will include the last instance of a directory.
        deduplicated_dirs = list()
        for i in range(len(include_dirs)):
            left_path = os.path.realpath(include_dirs[i])
            is_duplicate = False
            for j in range(i+1, len(include_dirs)):
                right_path = os.path.realpath(include_dirs[j])
                if left_path == right_path:
                    # these are the same directory
                    is_duplicate = True
                    break
            if not is_duplicate:
                deduplicated_dirs.append(left_path)
        include_dirs = set(deduplicated_dirs)
        if self._verbose > 1:
            print(f'Source will be searched in the following include directories: {include_dirs}')

        asm_file = AssemblyFile(self._source_file, global_label_scope)
        line_obs: list[LineObject] = asm_file.load_line_objects(
            self._model,
            include_dirs,
            memzone_manager,
            preprocessor,
            self._verbose
        )

        if self._verbose > 2:
            click.echo(f'Found {len(line_obs)} lines across all source files')

        compilable_line_obs: list[LineObject] = [lobj for lobj in line_obs if lobj.compilable]
        # First pass: assign addresses to labels
        for lobj in compilable_line_obs:
            lobj.set_start_address(lobj.memory_zone.current_address)
            if lobj.address is None:
                sys.exit(f'ERROR: {lobj.line_id} - INTERNAL line object address is None. Memory zone = {lobj.memory_zone}')

            try:
                lobj.memory_zone.current_address = lobj.address + lobj.word_count
            except ValueError as e:
                sys.exit(f'ERROR: {lobj.line_id} - {str(e)}')

            if isinstance(lobj, LabelLine) and not lobj.is_constant:
                lobj.label_scope.set_label_value(lobj.get_label(), lobj.get_value(), lobj.line_id)

        # now merge prefined line objects and parsed line objects
        compilable_line_obs.extend(predefined_line_obs)

        # Sort lines according to their assigned address. This allows for .org directives
        compilable_line_obs.sort(key=lambda x: x.address)
        max_generated_address = compilable_line_obs[-1].address
        line_dict = {
            lobj.address: lobj
            for lobj in compilable_line_obs
            if isinstance(lobj, LineWithWords) and not lobj.is_muted
        }

        # second pass: build the machine code and check for overlaps
        if self._verbose > 2:
            print('\nProcessing lines:')
        bytecode = bytearray()
        last_line = None

        for lobj in compilable_line_obs:
            if isinstance(lobj, LineWithWords):
                lobj.generate_words()
            if self._verbose > 2:
                click.echo(f'Processing {lobj.line_id} = {lobj} at address ${lobj.address:x}')
            if isinstance(lobj, LineWithWords):
                if last_line is not None and (last_line.address + last_line.word_count) > lobj.address:
                    sys.exit(
                        f'ERROR: {lobj.line_id} - Address of byte code at this line overlaps with bytecode from '
                        f'line <{last_line.line_id}> at address {hex(lobj.address)}\n'
                        f'  memory zone of current line <{lobj.line_id}> = {lobj.memory_zone}\n'
                        f'  memory zone of other line <{last_line.line_id}> = {last_line.memory_zone}\n'
                    )
                last_line = lobj

        # Finally generate the binary image
        fill_word = Word(
            self._binary_fill_value & ((1 << self._model.word_size) - 1),
            self._model.word_size,
            self._model.word_segment_size,
            self._model.intra_word_endianness,
        )

        if self._generate_binary:
            bytecode = Assembler._generate_bytes(
                line_dict,
                max_generated_address,
                fill_word,
                self._binary_start,
                self._binary_end,
                self._verbose,
            )
            click.echo(f'Writing {len(bytecode)} bytes of byte code to {self._output_file}')
            with open(self._output_file, 'wb') as f:
                f.write(bytecode)
        elif self._verbose > 1:
            print('NOT writing byte code to binary image.')

        if self._enable_pretty_print:
            pprinter = PrettyPrinterFactory.getPrettyPrinter(
                self._pretty_print_format,
                compilable_line_obs,
                self._model,
                self._source_file,
            )
            pretty_str = pprinter.pretty_print()
            if self._pretty_print_output == 'stdout':
                print(pretty_str)
            else:
                with open(self._pretty_print_output, 'w') as f:
                    f.write(pretty_str)

    @classmethod
    def _generate_bytes(
        cls,
        line_dict: dict[int, LineObject],
        max_generated_address: int,
        fill_word: Word,
        start_address: int,
        end_address: int,
        log_level: int,
    ) -> bytearray:
        words = []
        addr = start_address
        if log_level > 2:
            print('\nGenerating byte code:')
        while addr <= (max_generated_address if end_address is None else end_address):
            lobj = line_dict.get(addr, None)
            word_advance = 1
            if lobj is not None and isinstance(lobj, LineWithWords):
                lobj_words = lobj.get_words()
                words.extend(lobj_words)
                word_advance = lobj.word_count
                if log_level > 2:
                    word_str = ', '.join(f'0x{w.value:x}' for w in lobj_words)
                    click.echo(f'Address ${addr:x} : {lobj} words = [{word_str}]')
            else:
                words.append(fill_word)
            addr += word_advance

        # Use compact_bytes=True to pack bits for arbitrary word sizes
        return Word.words_to_bytes(words, compact_bytes=True)
