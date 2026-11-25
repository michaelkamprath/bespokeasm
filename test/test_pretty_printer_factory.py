import os
import unittest

from bespokeasm.assembler.diagnostic_reporter import DiagnosticReporter
from bespokeasm.assembler.model import AssemblerModel
from bespokeasm.assembler.pretty_printer.factory import PrettyPrinterFactory
from bespokeasm.assembler.pretty_printer.listing import ListingPrettyPrinter
from bespokeasm.assembler.pretty_printer.symbols import SymbolsPrettyPrinter


class TestPrettyPrinterFactory(unittest.TestCase):
    def setUp(self):
        config_path = os.path.join(
            os.path.dirname(__file__), 'config_files', 'test_instruction_list_creation_isa.json'
        )
        self.diagnostic_reporter = DiagnosticReporter()
        self.model = AssemblerModel(config_path, 0, self.diagnostic_reporter)

    def test_defined_formats_have_no_printer(self):
        """'minhex' is a Minimal CPU config format; 'hex' and 'intel_hex' are defined built-ins."""
        for name in ('minhex', 'hex', 'intel_hex'):
            with self.subTest(name=name), self.assertRaises(NotImplementedError):
                PrettyPrinterFactory.getPrettyPrinter(name, [], self.model, 'main.asm')

    def test_returns_listing(self):
        """'listing' dispatches to the Listing printer (annotated source view)."""
        printer = PrettyPrinterFactory.getPrettyPrinter('listing', [], self.model, 'main.asm')
        self.assertIsInstance(printer, ListingPrettyPrinter)

    def test_returns_symbols(self):
        """'symbols' dispatches to the JSON symbol-table printer."""
        printer = PrettyPrinterFactory.getPrettyPrinter('symbols', [], self.model, 'main.asm')
        self.assertIsInstance(printer, SymbolsPrettyPrinter)

    def test_unknown_type_raises(self):
        """Unknown printer-type strings raise NotImplementedError (not silent fallback)."""
        with self.assertRaises(NotImplementedError):
            PrettyPrinterFactory.getPrettyPrinter('not-a-real-type', [], self.model, 'main.asm')


if __name__ == '__main__':
    unittest.main()
