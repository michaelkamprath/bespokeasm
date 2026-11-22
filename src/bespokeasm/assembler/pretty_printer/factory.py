from bespokeasm.assembler.annotations.model import ExportModel
from bespokeasm.assembler.line_object import LineObject
from bespokeasm.assembler.model import AssemblerModel
from bespokeasm.assembler.pretty_printer import PrettyPrinterBase
from bespokeasm.assembler.pretty_printer.intelhex import IntelHexPrettyPrinter
from bespokeasm.assembler.pretty_printer.listing import ListingPrettyPrinter
from bespokeasm.assembler.pretty_printer.symbols import SymbolsPrettyPrinter


class PrettyPrinterFactory:
    """Constructs a `PrettyPrinterBase` subclass keyed by string name.

    Recognized type strings:
      - 'hex'       -> IntelHexPrettyPrinter (text dump mode)
      - 'intel_hex' -> IntelHexPrettyPrinter (Intel HEX file mode)
      - 'listing'   -> ListingPrettyPrinter
      - 'symbols'   -> SymbolsPrettyPrinter (every label and constant as JSON)

    Any other value raises `NotImplementedError`.
    """

    @classmethod
    def getPrettyPrinter(
            cls,
            pretty_printer_type: str,
            line_objs:  list[LineObject],
            model: AssemblerModel,
            main_filename: str,
            export_model: ExportModel | None = None,
            source_line_objects: list[LineObject] | None = None,
    ) -> PrettyPrinterBase:
        """Build the printer for a type name.

        ``line_objs`` are the compilable lines in address order. ``source_line_objects``
        are all parsed lines in source order, and ``export_model`` holds the annotated
        symbols; printers that do not need them ignore them.
        """
        if pretty_printer_type == 'hex':
            return IntelHexPrettyPrinter(line_objs, model, False)
        elif pretty_printer_type == 'intel_hex':
            return IntelHexPrettyPrinter(line_objs, model, True)
        elif pretty_printer_type == 'listing':
            return ListingPrettyPrinter(line_objs, model, main_filename, export_model)
        elif pretty_printer_type == 'symbols':
            return SymbolsPrettyPrinter(line_objs, model, main_filename, export_model, source_line_objects)
        raise NotImplementedError
