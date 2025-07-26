import io
import sys

from bespokeasm.assembler.bytecode.word import Word
from bespokeasm.assembler.line_object import LineObject
from bespokeasm.assembler.line_object import LineWithWords
from bespokeasm.assembler.line_object.directive_line.address import AddressOrgLine
from bespokeasm.assembler.model import AssemblerModel
from bespokeasm.assembler.pretty_printer import PrettyPrinterBase
from intelhex import IntelHex


class IntelHexPrettyPrinter(PrettyPrinterBase):
    def __init__(self, line_objs:  list[LineObject], model: AssemblerModel, as_intel_hex: bool) -> None:
        super().__init__(line_objs, model)
        if model.word_size != 8:
            sys.exit(f'ERROR - {"Intel " if as_intel_hex else ""}Hex Pretty '
                     f'Printer only supports 8-bit words')
        self._intel_hex = IntelHex()
        self._as_intel_hex = as_intel_hex

    def pretty_print(self) -> str:
        output = io.StringIO()
        for lobj in self.line_objects:
            if isinstance(lobj, LineWithWords) and not lobj.is_muted:
                line_bytes = Word.words_to_bytes(lobj.get_words()).decode(encoding='latin-')
                self._intel_hex.puts(lobj.address, line_bytes)

            elif isinstance(lobj, AddressOrgLine):
                pass

        if self._as_intel_hex:
            self._intel_hex.write_hex_file(output)
        else:
            self._intel_hex.dump(tofile=output)

        return output.getvalue()
