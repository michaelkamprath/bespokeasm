from bespokeasm.assembler.line_object import LineObject
from bespokeasm.assembler.model import AssemblerModel
from bespokeasm.assembler.pretty_printer import PrettyPrinterBase
from bespokeasm.assembler.pretty_printer.intelhex import IntelHexPrettyPrinter
from bespokeasm.assembler.pretty_printer.listing import ListingPrettyPrinter
from bespokeasm.assembler.pretty_printer.minhex import MinHexPrettyPrinter


class PrettyPrinterFactory:

    @classmethod
    def getPrettyPrinter(
            cls,
            pretty_printer_type: str,
            line_objs:  list[LineObject],
            model: AssemblerModel,
            main_filename: str,
    ) -> PrettyPrinterBase:
        if pretty_printer_type == 'minhex':
            return MinHexPrettyPrinter(line_objs, model)
        elif pretty_printer_type == 'hex':
            return IntelHexPrettyPrinter(line_objs, model, False)
        elif pretty_printer_type == 'intel_hex':
            return IntelHexPrettyPrinter(line_objs, model, True)
        elif pretty_printer_type == 'listing':
            return ListingPrettyPrinter(line_objs, model, main_filename)
        raise NotImplementedError
