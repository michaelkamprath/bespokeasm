import io
import sys

from bespokeasm.assembler.bytecode.word import Word
from bespokeasm.assembler.line_object import LineWithWords, LineObject
from bespokeasm.assembler.model import AssemblerModel
from bespokeasm.assembler.pretty_printer import PrettyPrinterBase
from bespokeasm.assembler.line_object.directive_line.address import AddressOrgLine


class MinHexPrettyPrinter(PrettyPrinterBase):
    def __init__(self, line_objs:  list[LineObject], model: AssemblerModel) -> None:
        if model.word_size != 8:
            sys.exit('ERROR - Min Hex Pretty Printer only supports 8-bit words')
        super().__init__(line_objs, model)

    def pretty_print(self) -> str:
        output = io.StringIO()
        line_byte_count = 0
        address_width = int(self.model.address_size/4)
        for lobj in self.line_objects:
            if isinstance(lobj, LineWithWords) and not lobj.is_muted:
                line_bytes = Word.words_to_bytes(lobj.get_words(), False, 'big')
                for b in line_bytes:
                    if line_byte_count == 0:
                        output.write(':')
                    output.write(f'{b:02x} ')
                    line_byte_count += 1
                    if line_byte_count == 16:
                        output.write('\n')
                        line_byte_count = 0
            elif isinstance(lobj, AddressOrgLine):
                if line_byte_count != 0:
                    output.write('\n')
                    line_byte_count = 0
                output.write('{addr:0{width}x}\n'.format(addr=lobj.address, width=address_width))

        if line_byte_count != 0:
            output.write('\n')

        return output.getvalue()
