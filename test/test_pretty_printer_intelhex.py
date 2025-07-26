import os
import unittest

from bespokeasm.assembler.bytecode.word import Word
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
        self.model = AssemblerModel(config_path, 0)
        self.memzone = MemoryZone(4, 0, 15, 'GLOBAL')

    def test_init_word_size_error(self):
        model = AssemblerModel(
            os.path.join(
                os.path.dirname(__file__), 'config_files', 'test_instruction_list_creation_isa.json'
            ),
            0
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


if __name__ == '__main__':
    unittest.main()
