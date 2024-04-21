import io

from intelhex import IntelHex

from bespokeasm.assembler.line_object import LineWithBytes, LineObject
from bespokeasm.assembler.model import AssemblerModel
from bespokeasm.assembler.pretty_printer import PrettyPrinterBase
from bespokeasm.assembler.line_object.directive_line.address import AddressOrgLine


class IntelHexPrettyPrinter(PrettyPrinterBase):
    def __init__(self, line_objs:  list[LineObject], model: AssemblerModel, as_intel_hex: bool) -> None:
        super().__init__(line_objs, model)
        self._intel_hex = IntelHex()
        self._as_intel_hex = as_intel_hex

    def pretty_print(self) -> str:
        output = io.StringIO()
        for lobj in self.line_objects:
            if isinstance(lobj, LineWithBytes) and not lobj.is_muted:
                line_bytes = lobj.get_bytes().decode(encoding='latin-')
                self._intel_hex.puts(lobj.address, line_bytes)

            elif isinstance(lobj, AddressOrgLine):
                pass

        if self._as_intel_hex:
            self._intel_hex.write_hex_file(output)
        else:
            self._intel_hex.dump(tofile=output)

        return output.getvalue()
