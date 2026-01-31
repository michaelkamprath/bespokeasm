import os
import unittest
from unittest.mock import patch

from bespokeasm.assembler.bytecode.word import Word
from bespokeasm.assembler.diagnostic_reporter import DiagnosticReporter
from bespokeasm.assembler.line_identifier import LineIdentifier
from bespokeasm.assembler.line_object import LineWithWords
from bespokeasm.assembler.line_object.directive_line.address import AddressOrgLine
from bespokeasm.assembler.memory_zone import MemoryZone
from bespokeasm.assembler.memory_zone.manager import MemoryZoneManager
from bespokeasm.assembler.model import AssemblerModel
from bespokeasm.assembler.pretty_printer.intelhex import IntelHexPrettyPrinter


class DummyLineWithWords(LineWithWords):
    def __init__(
        self, line_id, instruction, comment, memzone, word_size, word_segment_size,
        intra_word_endianness, multi_word_endianness, words, address
    ):
        super().__init__(
            line_id, instruction, comment, memzone, word_size, word_segment_size,
            intra_word_endianness, multi_word_endianness
        )
        self._words = words
        self._address = address

    def generate_words(self):
        pass

    @property
    def address(self):
        return self._address


class TestIntelHexPrettyPrinter(unittest.TestCase):
    def setUp(self):
        config_path = os.path.join(
            os.path.dirname(__file__), 'config_files', 'test_instruction_list_creation_isa.json'
        )
        self.diagnostic_reporter = DiagnosticReporter()
        self.model = AssemblerModel(config_path, 0, self.diagnostic_reporter)
        self.memzone = MemoryZone(4, 0, 15, 'GLOBAL')

    def test_init_word_size_error(self):
        model = AssemblerModel(
            os.path.join(
                os.path.dirname(__file__), 'config_files', 'test_instruction_list_creation_isa.json'
            ),
            0,
            self.diagnostic_reporter,
        )
        model._config['general']['word_size'] = 4
        with self.assertRaises(SystemExit):
            IntelHexPrettyPrinter([], model, True)

    def test_pretty_print_as_intel_hex(self):
        line_id1 = LineIdentifier(1, 'main.asm')
        line_id2 = LineIdentifier(2, 'main.asm')
        words1 = [Word(0x12, 8), Word(0x34, 8)]
        words2 = [Word(0x56, 8), Word(0x78, 8)]
        line1 = DummyLineWithWords(
            line_id1, 'data1', '', self.memzone, 8, 8, 'big', 'big', words1, 0x00
        )
        line2 = DummyLineWithWords(
            line_id2, 'data2', '', self.memzone, 8, 8, 'big', 'big', words2, 0x10
        )
        printer = IntelHexPrettyPrinter([line1, line2], self.model, True)
        output = printer.pretty_print().replace('\r\n', '\n').strip()
        expected = ':020000001234B8\n:02001000567820\n:00000001FF'
        self.assertEqual(output, expected)

    def test_pretty_print_as_hex(self):
        line_id1 = LineIdentifier(1, 'main.asm')
        line_id2 = LineIdentifier(2, 'main.asm')
        words1 = [Word(0x12, 8), Word(0x34, 8)]
        words2 = [Word(0x56, 8), Word(0x78, 8)]
        line1 = DummyLineWithWords(
            line_id1, 'data1', '', self.memzone, 8, 8, 'big', 'big', words1, 0x00
        )
        line2 = DummyLineWithWords(
            line_id2, 'data2', '', self.memzone, 8, 8, 'big', 'big', words2, 0x10
        )
        printer = IntelHexPrettyPrinter([line1, line2], self.model, False)
        output = printer.pretty_print().replace('\r\n', '\n').strip()
        expected = (
            '0000  12 34 -- -- -- -- -- -- -- -- -- -- -- -- -- --  |.4              |\n'
            '0010  56 78 -- -- -- -- -- -- -- -- -- -- -- -- -- --  |Vx              |'
        )
        self.assertEqual(output, expected)

    def test_pretty_print_edge_cases(self):
        printer = IntelHexPrettyPrinter([], self.model, True)
        output = printer.pretty_print().replace('\r\n', '\n').strip()
        self.assertEqual(output, ':00000001FF')
        line_id = LineIdentifier(1, 'main.asm')
        words = [Word(0x12, 8)]
        line = DummyLineWithWords(
            line_id, 'data', '', self.memzone, 8, 8, 'big', 'big', words, 0x00
        )
        line._is_muted = True
        printer = IntelHexPrettyPrinter([line], self.model, True)
        output = printer.pretty_print().replace('\r\n', '\n').strip()
        self.assertEqual(output, ':00000001FF')
        mzm = MemoryZoneManager(4, 0)
        org_line = AddressOrgLine(line_id, '.org', '', '0x20', 'GLOBAL', mzm)
        printer = IntelHexPrettyPrinter([org_line], self.model, True)
        output = printer.pretty_print().replace('\r\n', '\n').strip()
        self.assertEqual(output, ':00000001FF')

    def test_pretty_print_puts_called_for_words(self):
        class RecordingIntelHex:
            """Minimal IntelHex stand-in capturing puts/write calls."""
            def __init__(self):
                self.put_calls = []
                self.write_hex_file_called = False

            def puts(self, address, data):
                self.put_calls.append((address, data))

            def write_hex_file(self, output):
                self.write_hex_file_called = True
                output.write(':DONE\n')

            def dump(self, tofile):  # pragma: no cover - not used in this helper
                raise AssertionError('dump should not be called')

        line_id = LineIdentifier(1, 'main.asm')
        words = [Word(0xAA, 8), Word(0xBB, 8)]
        line = DummyLineWithWords(
            line_id, 'data', '', self.memzone, 8, 8, 'big', 'big', words, 0x20
        )
        stub_hex = RecordingIntelHex()
        with patch('bespokeasm.assembler.pretty_printer.intelhex.IntelHex', return_value=stub_hex):
            printer = IntelHexPrettyPrinter([line], self.model, True)
            output = printer.pretty_print()
        expected_data = Word.words_to_bytes(words).decode('latin-')
        # Ensure the printer feeds real instruction bytes to IntelHex and uses the hex writer path.
        self.assertEqual(stub_hex.put_calls, [(0x20, expected_data)])
        self.assertTrue(stub_hex.write_hex_file_called)
        self.assertEqual(output, ':DONE\n')

    def test_pretty_print_skips_muted_lines_and_uses_dump(self):
        class RecordingIntelHex:
            """IntelHex stub tracking whether dump was invoked."""
            def __init__(self):
                self.put_calls = []
                self.dump_called = False

            def puts(self, address, data):
                self.put_calls.append((address, data))

            def write_hex_file(self, output):  # pragma: no cover - not used in this helper
                raise AssertionError('write_hex_file should not be called')

            def dump(self, tofile):
                self.dump_called = True
                tofile.write('dumped\n')

        line_id = LineIdentifier(1, 'main.asm')
        words = [Word(0xCC, 8)]
        line = DummyLineWithWords(
            line_id, 'data', '', self.memzone, 8, 8, 'big', 'big', words, 0x30
        )
        line._is_muted = True
        org_line = AddressOrgLine(line_id, '.org', '', '0x40', 'GLOBAL', MemoryZoneManager(4, 0))
        stub_hex = RecordingIntelHex()
        with patch('bespokeasm.assembler.pretty_printer.intelhex.IntelHex', return_value=stub_hex):
            printer = IntelHexPrettyPrinter([line, org_line], self.model, False)
            output = printer.pretty_print()
        # Verify muted lines (and directives) skip byte emission while the dump fallback still produces output.
        self.assertEqual(stub_hex.put_calls, [])
        self.assertTrue(stub_hex.dump_called)
        self.assertEqual(output, 'dumped\n')


if __name__ == '__main__':
    unittest.main()
