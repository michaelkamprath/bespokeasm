import io
import math

from bespokeasm.assembler.line_object import LineObject
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

    def pretty_print(self) -> str:
        if len(self.line_objects) < 1:
            return ''

        output = io.StringIO()

        # create a new list of line objects sorted by file then line number.
        lobjs: list[LineIdentifier] = self.line_objects.copy()
        lobjs.sort(
            key=lambda x: str(x.line_id) if x.filename == self._main_filename else f'z_{x.filename}_{x.line_id}'
        )

        cur_filename = None
        for lo in lobjs:
            # detect a new file
            if lo.filename != cur_filename:
                # print new file header
                cur_filename = lo.filename
                self._print_file_header(output, cur_filename)

            self._print_line_object(output, lo)
        return output.getvalue()

    def _print_file_header(self, output: io.StringIO, filename: str) -> None:
        output.write('********************\n\n')
        output.write(f'File: {filename}\n')
        output.write('---\n')

    def _print_line_object(self, output: io.StringIO, lobj: LineObject) -> None:
        raise NotImplementedError
