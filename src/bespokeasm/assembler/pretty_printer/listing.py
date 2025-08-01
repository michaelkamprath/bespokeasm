import io
import math
import sys

from bespokeasm.assembler.bytecode.word import Word
from bespokeasm.assembler.line_identifier import LineIdentifier
from bespokeasm.assembler.line_object import LineObject
from bespokeasm.assembler.line_object import LineWithWords
from bespokeasm.assembler.line_object.directive_line.memzone import SetMemoryZoneLine
from bespokeasm.assembler.line_object.label_line import LabelLine
from bespokeasm.assembler.line_object.preprocessor_line import PreprocessorLine
from bespokeasm.assembler.model import AssemblerModel
from bespokeasm.assembler.pretty_printer import PrettyPrinterBase


class ListingPrettyPrinter(PrettyPrinterBase):
    MAX_NUM_BYTES_PER_LINE = 6
    INSTRUCTION_INDENT = 4

    def __init__(self, line_objs:  list[LineObject], model: AssemblerModel, main_filename: str) -> None:
        super().__init__(line_objs, model, instruction_indent=ListingPrettyPrinter.INSTRUCTION_INDENT)
        self._address_size = math.ceil(self.model.address_size/4)
        self._address_format_str = f'{{0:0{self._address_size}x}}'
        self._main_filename = main_filename
        self._bytes_per_line = min(
            ListingPrettyPrinter.MAX_NUM_BYTES_PER_LINE,
            self.max_byte_count,
        )
        self._word_size = model.word_size

    def pretty_print(self) -> str:
        if len(self.line_objects) < 1:
            return ''

        output = io.StringIO()

        # create a new list of line objects sorted by file then line number.
        lobjs: list[LineIdentifier] = self.line_objects.copy()
        lobjs.sort(
            key=lambda x:
                f'{x.line_id.line_num:04d}'
                if x.line_id.filename == self._main_filename
                else f'z_{x.line_id.filename}_{x.line_id.line_num:04d}'
        )

        cur_filename = None
        hex_width = Word(0, self._word_size).ideal_hex_width
        for lo in lobjs:
            # detect a new file and print the file header
            if lo.line_id.filename != cur_filename:
                # print new file header
                cur_filename = lo.line_id.filename
                self._print_file_header(output, cur_filename, hex_width)

            # print the line object
            self._print_line_object(output, lo, hex_width)
        return output.getvalue()

    def _print_file_header(self, output: io.StringIO, filename: str, hex_width: int) -> None:
        COMMENT_HEADER = 'comment'
        comment_header_width = len(COMMENT_HEADER) if len(COMMENT_HEADER) > self.max_comment_width else self.max_comment_width

        output.write(f'\n\nFile: {filename}\n')
        output.write(
            '-'*(self.max_line_num_width + 2) + '+' +
            '-'*(self._address_size + 2) + '+' +
            '-'*(self._bytes_per_line*(hex_width+1) + 1) + '+' +
            '-'*(self.max_instruction_width + 2) + '+' +
            '-'*(comment_header_width + 2) + '\n'
        )

        if self._address_size >= 8:
            address_header = 'address'
        elif self._address_size >= 4:
            address_header = 'addr'
        else:
            address_header = 'a'

        if self._bytes_per_line >= 5:
            bytes_header = 'machine code'
        elif self._bytes_per_line >= 2:
            if self._word_size == 8:
                bytes_header = 'bytes'
            else:
                bytes_header = 'words'
        else:
            if self._word_size == 8:
                bytes_header = 'b'
            else:
                bytes_header = 'w'

        if self.max_instruction_width >= 11:
            instruction_header = ' instruction'
        elif self.max_instruction_width >= 6:
            instruction_header = ' instr'
        else:
            instruction_header = ' i'

        output.write(
            'line'.center(self.max_line_num_width + 2) + '|' +
            address_header.center(self._address_size + 2) + '|' +
            bytes_header.center(self._bytes_per_line*(hex_width+1) + 1) + '|' +
            instruction_header.ljust(self.max_instruction_width + 2) + '|' +
            f' {COMMENT_HEADER}\n'
        )

        output.write(
            '-'*(self.max_line_num_width + 2) + '+' +
            '-'*(self._address_size + 2) + '+' +
            '-'*(self._bytes_per_line*(hex_width+1) + 1) + '+' +
            '-'*(self.max_instruction_width + 2) + '+' +
            '-'*(comment_header_width + 2) + '\n'
        )

    def _print_line_object(self, output: io.StringIO, lobj: LineObject, hex_width: int) -> None:
        # wite the lobj details to output using the following format:
        #    line number in decimal | address in hex | machine code in hex (6 bytes wide) | instruction text | comment text
        #     1 | 0000 | 00 00 00 00 00 00 | nop | this is a comment
        #
        # If the lobj is not of type LineWithBytes, then the machine code field is left blank.
        # If the lobj is of type LineWithBytes, then the machine code is shown as a series of bytes separated by spaces.
        # If the machine code is less than 6 bytes, then only those bytes are shown with the remaining being whitespace. If
        # the machine code is more than 6 bytes, then the extra bytes are shown on the next line with the other fields in
        # the line being whitespace.
        # The instruction text is left justified and padded with whitespace to the max_instruction_width.
        # The comment text is left justified.
        #

        # first, get the line bytes, if any
        line_bytes = None if not isinstance(lobj, LineWithWords) \
                        else ListingPrettyPrinter._generate_bytecode_line_string(
                            lobj.get_words(),
                            self._bytes_per_line,
                            self._word_size,
                        )

        # write the line number
        output.write(f' {lobj.line_id.line_num:{self.max_line_num_width}d} | ')

        # write the address
        if lobj.address is not None:
            output.write(self._address_format_str.format(lobj.address))
        else:
            output.write(' ' * (self._address_size))
        output.write(' | ')

        # write the machine code
        if line_bytes is not None:
            try:
                output.write(line_bytes[0])
            except IndexError:
                sys.exit(f'ERROR - internal: line_bytes is empty for line {lobj} at {lobj.line_id}')
        else:
            output.write(' ' * (self._bytes_per_line * (hex_width+1)))
        output.write('| ')

        # write the instruction
        if not isinstance(lobj, LabelLine) \
                and not isinstance(lobj, SetMemoryZoneLine) \
                and not isinstance(lobj, PreprocessorLine):
            instruction_str = ' '*ListingPrettyPrinter.INSTRUCTION_INDENT + lobj.instruction
        else:
            instruction_str = lobj.instruction
        output.write(f'{instruction_str: <{self.max_instruction_width}} | ')

        # write the comment
        output.write(lobj.comment)
        output.write('\n')

        if line_bytes is not None and len(line_bytes) > 1:
            for bytes in line_bytes[1:]:
                output.write(
                    ' '*(self.max_line_num_width+1) + ' | ' + ' '*self._address_size
                    + ' | ' + bytes + '| '
                    + ' '*self.max_instruction_width + ' | \n'
                )

    @classmethod
    def _generate_bytecode_line_string(
        cls,
        line_words: list[Word],
        words_per_str: int,
        word_size: int,
    ) -> list[str]:
        # convert the line_bytes to a list of strings, each string being a hex representation of a byte.
        # Each line should contain at most 6 bytes. There should be as many strings in the return list
        # as needed for each string to contain up to 6 bytes of line_bytes. The first byt through 6th byte
        # in line_bytes gets added to the first string in the list, the 7th through 12th bytes get added
        # to the second string in the list, etc. If the number of bytes in line_bytes is not a multiple of
        # 6, then the last string in the list will be padded with whitespace to make it 6 bytes wide.
        #
        # Example:
        #   line_bytes = b'\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a\x0b\x0c\x0d\x0e\x0f'
        #   return = ['00 01 02 03 04 05', '06 07 08 09 0a 0b', '0c 0d 0e 0f    ']
        #
        #   line_bytes = b'\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a\x0b\x0c\x0d\x0e'
        #   return = ['00 01 02 03 04 05', '06 07 08 09 0a 0b', '0c 0d 0e       ']
        #
        #   line_bytes = b'\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a\x0b\x0c\x0d'
        #   return = ['00 01 02 03 04 05', '06 07 08 09 0a 0b', '0c 0d          ']
        #
        results: list[str] = []
        cur_str = None
        hex_width = Word(0, word_size).ideal_hex_width
        for w in line_words:
            if cur_str is None:
                cur_str = ''
            cur_str += f'{w:x} '
            if len(cur_str) == words_per_str*(hex_width+1):
                results.append(cur_str)
                cur_str = None
        if cur_str is not None:
            results.append(f'{cur_str:<{words_per_str*(hex_width+1)}}')
        return results
