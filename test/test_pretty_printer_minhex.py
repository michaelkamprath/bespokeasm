import os
import unittest

from bespokeasm.assembler.bytecode.word import Word
from bespokeasm.assembler.diagnostic_reporter import DiagnosticReporter
from bespokeasm.assembler.line_identifier import LineIdentifier
from bespokeasm.assembler.line_object import LineWithWords
from bespokeasm.assembler.line_object.directive_line.address import AddressOrgLine
from bespokeasm.assembler.memory_zone import MemoryZone
from bespokeasm.assembler.memory_zone.manager import MemoryZoneManager
from bespokeasm.assembler.model import AssemblerModel
from bespokeasm.assembler.pretty_printer.minhex import MinHexPrettyPrinter


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


class TestMinHexPrettyPrinter(unittest.TestCase):
    def setUp(self):
        config_path = os.path.join(
            os.path.dirname(__file__), 'config_files', 'test_instruction_list_creation_isa.json'
        )
        self.diagnostic_reporter = DiagnosticReporter()
        self.model = AssemblerModel(config_path, 0, self.diagnostic_reporter)
        self.memzone = MemoryZone(4, 0, 15, 'GLOBAL')

    def test_init_word_size_error(self):
        # MinHexPrettyPrinter only supports 8-bit words; non-8 word sizes exit.
        self.model._config['general']['word_size'] = 4
        with self.assertRaises(SystemExit):
            MinHexPrettyPrinter([], self.model)

    def test_pretty_print_empty(self):
        printer = MinHexPrettyPrinter([], self.model)
        output = printer.pretty_print()
        self.assertEqual(output, '', 'empty input produces empty output')

    def test_pretty_print_basic_bytes(self):
        line_id = LineIdentifier(1, 'main.asm')
        words = [Word(0xDE, 8), Word(0xAD, 8), Word(0xBE, 8), Word(0xEF, 8)]
        line = DummyLineWithWords(
            line_id, 'data', '', self.memzone, 8, 8, 'big', 'big', words, 0x00
        )
        printer = MinHexPrettyPrinter([line], self.model)
        output = printer.pretty_print().replace('\r\n', '\n').strip()
        # Lines start with ':', each byte rendered as lowercase hex.
        self.assertTrue(output.startswith(':'), 'data row begins with colon prefix')
        normalized = ' '.join(output.split())
        self.assertEqual(normalized, ':de ad be ef')

    def test_pretty_print_wraps_after_16_bytes(self):
        line_id = LineIdentifier(1, 'main.asm')
        # 17 bytes -> first 16 on row 1, 17th on row 2.
        words = [Word(i, 8) for i in range(17)]
        line = DummyLineWithWords(
            line_id, 'data', '', self.memzone, 8, 8, 'big', 'big', words, 0x00
        )
        printer = MinHexPrettyPrinter([line], self.model)
        output = printer.pretty_print().replace('\r\n', '\n').strip()
        rows = [r.strip() for r in output.split('\n') if r.strip()]
        self.assertEqual(len(rows), 2, 'a 17-byte payload spans two rows')
        first_bytes = rows[0].lstrip(':').split()
        self.assertEqual(len(first_bytes), 16, 'first row has 16 bytes')
        self.assertEqual(first_bytes[0], '00')
        self.assertEqual(first_bytes[-1], '0f')
        second_bytes = rows[1].lstrip(':').split()
        self.assertEqual(second_bytes, ['10'], 'second row contains the 17th byte')

    def test_pretty_print_with_address_org(self):
        line_id = LineIdentifier(1, 'main.asm')
        words_a = [Word(0x12, 8), Word(0x34, 8)]
        line_a = DummyLineWithWords(
            line_id, 'data_a', '', self.memzone, 8, 8, 'big', 'big', words_a, 0x00
        )
        org_line = AddressOrgLine(line_id, '.org', '', '0x8', 'GLOBAL', MemoryZoneManager(4, 0))
        words_b = [Word(0x56, 8)]
        line_b = DummyLineWithWords(
            line_id, 'data_b', '', self.memzone, 8, 8, 'big', 'big', words_b, 0x08
        )
        printer = MinHexPrettyPrinter([line_a, org_line, line_b], self.model)
        output = printer.pretty_print().replace('\r\n', '\n').strip()
        rows = [r.strip() for r in output.split('\n') if r.strip()]
        # Row layout: data_a bytes, then the address marker, then data_b bytes.
        self.assertEqual(rows[0].lstrip(':').split(), ['12', '34'])
        # AddressOrgLine emits the address as hex; address_size=4 bits -> 1-char width.
        self.assertEqual(rows[1], '8', 'org line emits the new address')
        self.assertEqual(rows[2].lstrip(':').split(), ['56'])

    def test_pretty_print_skips_muted_lines(self):
        line_id = LineIdentifier(1, 'main.asm')
        words_visible = [Word(0xAA, 8)]
        words_muted = [Word(0xBB, 8)]
        visible = DummyLineWithWords(
            line_id, 'visible', '', self.memzone, 8, 8, 'big', 'big', words_visible, 0x00
        )
        muted = DummyLineWithWords(
            line_id, 'muted', '', self.memzone, 8, 8, 'big', 'big', words_muted, 0x01
        )
        muted._is_muted = True
        printer = MinHexPrettyPrinter([visible, muted], self.model)
        output = printer.pretty_print().replace('\r\n', '\n').strip()
        normalized = ' '.join(output.split())
        # 0xBB from the muted line must not appear.
        self.assertEqual(normalized, ':aa')

    def test_pretty_print_org_after_partial_row(self):
        # An org line in the middle of a partial row should flush the row before emitting the address.
        line_id = LineIdentifier(1, 'main.asm')
        words = [Word(0x01, 8), Word(0x02, 8)]
        line = DummyLineWithWords(
            line_id, 'data', '', self.memzone, 8, 8, 'big', 'big', words, 0x00
        )
        org_line = AddressOrgLine(line_id, '.org', '', '0xa', 'GLOBAL', MemoryZoneManager(4, 0))
        printer = MinHexPrettyPrinter([line, org_line], self.model)
        output = printer.pretty_print().replace('\r\n', '\n').strip()
        rows = [r.strip() for r in output.split('\n') if r.strip()]
        self.assertEqual(rows[0].lstrip(':').split(), ['01', '02'])
        self.assertEqual(rows[1], 'a', 'address marker follows the partial data row')


if __name__ == '__main__':
    unittest.main()
