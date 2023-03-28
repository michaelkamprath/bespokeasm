import io
import math

from bespokeasm.assembler.line_object import LineObject, LineWithBytes
from bespokeasm.assembler.model import AssemblerModel
from bespokeasm.assembler.pretty_printer import PrettyPrinterBase
from bespokeasm.assembler.line_identifier import LineIdentifier


class ListingPrettyPrinter(PrettyPrinterBase):
    """
    line number | address | machine code (6 bytes wide) | instruction | comment
    """
    def __init__(self, line_objs:  list[LineObject], model: AssemblerModel, main_filename: str) -> None:
        super().__init__(line_objs, model)
        self._address_size = math.ceil(self.model.address_size/4)
        self._address_format_str = f'{{0:0{self._address_size}x}}'
        self._main_filename = main_filename
        self._bytes_per_line = min(6, self.max_byte_count)

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
        for lo in lobjs:
            # detect a new file
            if lo.line_id.filename != cur_filename:
                # print new file header
                cur_filename = lo.line_id.filename
                self._print_file_header(output, cur_filename)

            self._print_line_object(output, lo)
        return output.getvalue()

    def _print_file_header(self, output: io.StringIO, filename: str) -> None:
        output.write('\n********************\n\n')
        output.write(f'File: {filename}\n')
        output.write('---\n')

    def _print_line_object(self, output: io.StringIO, lobj: LineObject) -> None:
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
        line_bytes = None if not isinstance(lobj, LineWithBytes) else self._generate_bytecode_line_string(lobj.get_bytes())

        # write the line number
        output.write(f'{lobj.line_id.line_num:4d} | ')

        # write the address
        if lobj.address is not None:
            output.write(self._address_format_str.format(lobj.address))
        else:
            output.write(' ' * (self._address_size))
        output.write(' | ')

        # write the machine code
        if line_bytes is not None:
            output.write(line_bytes[0])
        else:
            output.write(' ' * self._bytes_per_line * 3)
        output.write('| ')

        # write the instruction
        output.write(f'{lobj.instruction: <{self.max_instruction_width}} | ')

        # write the comment
        output.write(lobj.comment)
        output.write('\n')

        if line_bytes is not None and len(line_bytes) > 1:
            for bytes in line_bytes[1:]:
                output.write(
                    ' '*4 + ' | ' + ' '*self._address_size + ' | ' + bytes
                    + '| ' + ' '*self.max_instruction_width + ' | \n'
                )

    def _generate_bytecode_line_string(self, line_bytes: bytearray) -> list[str]:
        # conver the line_bytes to a list of strings, each string being a hex representation of a byte.
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
        for b in line_bytes:
            if cur_str is None:
                cur_str = ''
            cur_str += f'{b:02x} '
            if len(cur_str) == self._bytes_per_line*3:
                results.append(cur_str)
                cur_str = None
        if cur_str is not None:
            results.append(f'{cur_str:<{self._bytes_per_line*3}}')
        return results
