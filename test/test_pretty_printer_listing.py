import json
import os
import tempfile
import unittest

from bespokeasm.assembler.bytecode.word import Word
from bespokeasm.assembler.line_identifier import LineIdentifier
from bespokeasm.assembler.line_object import LineObject
from bespokeasm.assembler.line_object import LineWithWords
from bespokeasm.assembler.memory_zone import MemoryZone
from bespokeasm.assembler.model import AssemblerModel
from bespokeasm.assembler.pretty_printer.listing import ListingPrettyPrinter


class DummyLineWithWords(LineWithWords):
    def __init__(
        self, line_id, instruction, comment, memzone, word_size, word_segment_size,
        intra_word_endianness, multi_word_endianness, words
    ):
        super().__init__(
            line_id, instruction, comment, memzone, word_size, word_segment_size,
            intra_word_endianness, multi_word_endianness
        )
        self._words = words

    def generate_words(self):
        pass


class TestListingPrettyPrinter(unittest.TestCase):
    def setUp(self):
        config_path = os.path.join(
            os.path.dirname(__file__), 'config_files', 'test_instruction_list_creation_isa.json'
        )
        self.model = AssemblerModel(config_path, 0)
        self.memzone = MemoryZone(4, 0, 15, 'GLOBAL')

    def test_pretty_print_basic_ordered(self):
        line_id = LineIdentifier(1, 'main.asm')
        line = LineObject(line_id, 'lda $1', 'test comment', self.memzone)
        line.set_start_address(0x0)
        printer = ListingPrettyPrinter([line], self.model, 'main.asm')
        output = printer.pretty_print()
        lines = [line for line in output.splitlines() if line.strip()]
        data_lines = [line for line in lines if 'lda $1' in line]
        self.assertTrue(data_lines, f'No data line found in output: {output}')
        data_line = data_lines[0]
        self.assertTrue(data_line.startswith('    1 | 0 |'))
        self.assertTrue(data_line.rstrip().endswith('| test comment'))
        header_idx = [i for i, line in enumerate(lines) if 'line' in line and 'comment' in line][0]
        data_idx = lines.index(data_line)
        self.assertLess(header_idx, data_idx)

    def test_pretty_print_multiple_files_ordered(self):
        line1 = LineObject(LineIdentifier(1, 'main.asm'), 'lda $1', 'main file', self.memzone)
        line1.set_start_address(0x0)
        line2 = LineObject(LineIdentifier(2, 'other.asm'), 'hlt', 'other file', self.memzone)
        line2.set_start_address(0x1)
        printer = ListingPrettyPrinter([line2, line1], self.model, 'main.asm')
        output = printer.pretty_print()
        lines = [line for line in output.splitlines() if line.strip()]
        main_idx = [i for i, line in enumerate(lines) if 'File: main.asm' in line][0]
        other_idx = [i for i, line in enumerate(lines) if 'File: other.asm' in line][0]
        self.assertLess(main_idx, other_idx)
        main_data = [line for line in lines if 'main file' in line][0]
        other_data = [line for line in lines if 'other file' in line][0]
        self.assertTrue(main_data.startswith('    1 | 0 |'))
        self.assertTrue(other_data.startswith('    2 | 1 |'))

    def test_pretty_print_machine_code_multiline(self):
        line_id = LineIdentifier(1, 'main.asm')
        words = [Word(i, 8) for i in range(8)]
        line = DummyLineWithWords(
            line_id, 'add $2', 'machine code', self.memzone, 8, 8, 'big', 'big', words
        )
        line.set_start_address(0x0)
        printer = ListingPrettyPrinter([line], self.model, 'main.asm')
        output = printer.pretty_print()
        lines = [line for line in output.splitlines() if line.strip()]
        data_lines = [
            line for line in lines if 'add $2' in line or (
                line.strip().startswith('0') and '|' in line and 'add $2' not in line
            )
        ]
        self.assertTrue(data_lines[0].startswith('    1 | 0 |'))
        self.assertIn('00 01 02 03 04 05', data_lines[0])
        self.assertIn('add $2', data_lines[0])
        self.assertIn('machine code', data_lines[0])
        cont_line = [
            line for line in lines
            if line.strip().startswith('|') and 'add $2' not in line and 'machine code' not in line
        ]
        self.assertTrue(any('06 07' in line for line in cont_line))

    def test_pretty_print_header_variations(self):
        def make_config(address_size, word_size):
            config = {
                'description': 'header test',
                'general': {
                    'address_size': address_size,
                    'endian': 'big',
                    'registers': [],
                    'min_version': '0.5.0',
                    'string_byte_packing': False,
                    'string_byte_packing_fill': 0,
                },
                'instructions': {'nop': {'bytecode': {'size': 4, 'value': 0}}},
                'operand_sets': {},
                'registers': []
            }
            if word_size != 8:
                config['general']['word_size'] = word_size
            return config
        for addr_size, word_size in [(4, 8), (8, 8), (16, 8), (8, 16)]:
            with tempfile.NamedTemporaryFile('w+', suffix='.json', delete=False) as tf:
                json.dump(make_config(addr_size, word_size), tf)
                tf.flush()
                model = AssemblerModel(tf.name, 0)
                memzone = MemoryZone(addr_size, 0, 2 ** addr_size - 1, 'GLOBAL')
                line_id = LineIdentifier(1, 'main.asm')
                line = LineObject(line_id, 'nop', 'header test', memzone)
                line.set_start_address(0x0)
                printer = ListingPrettyPrinter([line], model, 'main.asm')
                output = printer.pretty_print()
                lines = [line for line in output.splitlines() if line.strip()]
                header_line = [
                    line for line in lines if 'line' in line and 'comment' in line
                ][0]
                if addr_size == 4:
                    self.assertIn('a', header_line)
                elif addr_size == 8:
                    self.assertIn('a', header_line)
                elif addr_size == 16:
                    self.assertIn('addr', header_line)
                else:
                    self.assertIn('a', header_line)
                if word_size == 8:
                    self.assertTrue(
                        any(h in header_line for h in ['bytes', 'b', 'machine code'])
                    )
                else:
                    self.assertTrue(any(h in header_line for h in ['words', 'w']))
                os.unlink(tf.name)

    def test_generate_bytecode_line_string(self):
        words = [Word(i, 8) for i in range(7)]
        result = ListingPrettyPrinter._generate_bytecode_line_string(words, 6, 8)
        self.assertEqual(len(result), 2)
        self.assertTrue(result[0].startswith('00 01 02 03 04 05'))
        self.assertTrue(result[1].strip().startswith('06'))
        words = [Word(i, 8) for i in range(12)]
        result = ListingPrettyPrinter._generate_bytecode_line_string(words, 6, 8)
        self.assertEqual(len(result), 2)
        self.assertTrue(result[0].startswith('00 01 02 03 04 05'))
        self.assertTrue(result[1].startswith('06 07 08 09 0a 0b'))
        result = ListingPrettyPrinter._generate_bytecode_line_string([], 6, 8)
        self.assertEqual(result, [])


if __name__ == '__main__':
    unittest.main()
