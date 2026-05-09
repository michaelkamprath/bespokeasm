import os
import unittest

from bespokeasm.assembler.diagnostic_reporter import DiagnosticReporter
from bespokeasm.assembler.model import AssemblerModel
from bespokeasm.assembler.pretty_printer.factory import PrettyPrinterFactory
from bespokeasm.assembler.pretty_printer.intelhex import IntelHexPrettyPrinter
from bespokeasm.assembler.pretty_printer.listing import ListingPrettyPrinter
from bespokeasm.assembler.pretty_printer.minhex import MinHexPrettyPrinter


class TestPrettyPrinterFactory(unittest.TestCase):
    def setUp(self):
        config_path = os.path.join(
            os.path.dirname(__file__), 'config_files', 'test_instruction_list_creation_isa.json'
        )
        self.diagnostic_reporter = DiagnosticReporter()
        self.model = AssemblerModel(config_path, 0, self.diagnostic_reporter)

    def test_returns_minhex(self):
        printer = PrettyPrinterFactory.getPrettyPrinter('minhex', [], self.model, 'main.asm')
        self.assertIsInstance(printer, MinHexPrettyPrinter)

    def test_returns_hex(self):
        printer = PrettyPrinterFactory.getPrettyPrinter('hex', [], self.model, 'main.asm')
        self.assertIsInstance(printer, IntelHexPrettyPrinter)

    def test_returns_intel_hex(self):
        printer = PrettyPrinterFactory.getPrettyPrinter('intel_hex', [], self.model, 'main.asm')
        self.assertIsInstance(printer, IntelHexPrettyPrinter)

    def test_returns_listing(self):
        printer = PrettyPrinterFactory.getPrettyPrinter('listing', [], self.model, 'main.asm')
        self.assertIsInstance(printer, ListingPrettyPrinter)

    def test_unknown_type_raises(self):
        with self.assertRaises(NotImplementedError):
            PrettyPrinterFactory.getPrettyPrinter('not-a-real-type', [], self.model, 'main.asm')


if __name__ == '__main__':
    unittest.main()
