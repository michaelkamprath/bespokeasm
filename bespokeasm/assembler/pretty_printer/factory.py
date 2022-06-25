from bespokeasm.assembler.pretty_printer import PrettyPrinterBase
from bespokeasm.assembler.pretty_printer.source_details import SourceDetailsPrettyPrinter
from bespokeasm.assembler.line_object import LineObject
from bespokeasm.assembler.model import AssemblerModel

class PrettyPrinterFactory:

    @classmethod
    def getPrettyPrinter(cls, pretty_printer_type: str, line_objs:  list[LineObject], model: AssemblerModel) -> PrettyPrinterBase:
        if pretty_printer_type == 'source_details':
            return SourceDetailsPrettyPrinter(line_objs, model)
        raise NotImplementedError