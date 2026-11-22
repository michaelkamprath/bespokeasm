"""Built-in output formats, implemented in Python by the pretty printers."""
from __future__ import annotations

from bespokeasm.assembler.output_format.base import OutputFormat
from bespokeasm.assembler.output_format.base import RenderContext

BUILTIN_FORMAT_DESCRIPTIONS = {
    'listing': 'Source listing with addresses and assembled bytes.',
    'hex': 'Text hex dump of the assembled bytes.',
    'intel_hex': 'Intel HEX records.',
    'symbols': 'Every label and constant, with annotations, as JSON.',
}
BUILTIN_FORMAT_NAMES = tuple(BUILTIN_FORMAT_DESCRIPTIONS)


class PrinterFormat(OutputFormat):
    """A built-in format backed by a ``PrettyPrinterFactory`` printer."""

    def __init__(self, name: str) -> None:
        super().__init__(name, BUILTIN_FORMAT_DESCRIPTIONS[name], is_builtin=True)

    def render(self, context: RenderContext) -> str:
        from bespokeasm.assembler.pretty_printer.factory import PrettyPrinterFactory

        printer = PrettyPrinterFactory.getPrettyPrinter(
            self.name,
            context.line_objects,
            context.model,
            context.source_file,
            export_model=context.export_model,
            source_line_objects=context.source_line_objects,
        )
        return printer.pretty_print()


BUILTIN_FORMATS: dict[str, OutputFormat] = {name: PrinterFormat(name) for name in BUILTIN_FORMAT_NAMES}
