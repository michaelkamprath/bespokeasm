import importlib.resources as pkg_resources
import unittest

from bespokeasm.assembler.bytecode.word import Word
from bespokeasm.assembler.label_scope import GlobalLabelScope
from bespokeasm.assembler.line_identifier import LineIdentifier
from bespokeasm.assembler.line_object.factory import LineOjectFactory
from bespokeasm.assembler.line_object.instruction_line import InstructionLine
from bespokeasm.assembler.memory_zone.manager import MemoryZoneManager
from bespokeasm.assembler.model import AssemblerModel
from bespokeasm.assembler.preprocessor import Preprocessor
from bespokeasm.assembler.pretty_printer.factory import PrettyPrinterFactory
from bespokeasm.assembler.pretty_printer.listing import ListingPrettyPrinter

from test import config_files


class TestPrettyPrinting(unittest.TestCase):

    def setUp(self):
        InstructionLine._INSTRUCTUION_EXTRACTION_PATTERN = None

    def tearDown(self):
        InstructionLine._INSTRUCTUION_EXTRACTION_PATTERN = None

    def test_listing_bytes_per_line(self):
        word_list = [
            Word(0x00, 8),
            Word(0x01, 8),
            Word(0x02, 8),
            Word(0x03, 8),
            Word(0x04, 8),
            Word(0x05, 8),
            Word(0x06, 8),
            Word(0x07, 8),
            Word(0x08, 8),
            Word(0x09, 8),
            Word(0x0a, 8),
            Word(0x0b, 8),
            Word(0x0c, 8),
            Word(0x0d, 8),
            Word(0x0e, 8),
            Word(0x0f, 8),
        ]
        self.assertEqual(
            ListingPrettyPrinter._generate_bytecode_line_string(
                word_list,
                6,
                8
            ),
            ['00 01 02 03 04 05 ', '06 07 08 09 0a 0b ', '0c 0d 0e 0f       '],
        )

        self.assertEqual(
            ListingPrettyPrinter._generate_bytecode_line_string(
                word_list,
                3,
                8,
            ),
            ['00 01 02 ', '03 04 05 ', '06 07 08 ', '09 0a 0b ', '0c 0d 0e ', '0f       '],
        )

        self.assertEqual(
            ListingPrettyPrinter._generate_bytecode_line_string(
                word_list,
                16,
                8,
            ),
            ['00 01 02 03 04 05 06 07 08 09 0a 0b 0c 0d 0e 0f '],
        )

    def test_listing_16bit_words(self):
        word_list = [
            Word(0x0000, 16), Word(0x0001, 16), Word(0x00a2, 16), Word(0x0b03, 16),
            Word(0x1234, 16), Word(0xabcd, 16), Word(0xffff, 16), Word(0x8000, 16),
        ]
        # words_per_str = 4
        self.assertEqual(
            ListingPrettyPrinter._generate_bytecode_line_string(
                word_list,
                4,
                16
            ),
            ['0000 0001 00a2 0b03 ', '1234 abcd ffff 8000 '],
        )
        # words_per_str = 2
        self.assertEqual(
            ListingPrettyPrinter._generate_bytecode_line_string(
                word_list,
                2,
                16
            ),
            ['0000 0001 ', '00a2 0b03 ', '1234 abcd ', 'ffff 8000 '],
        )
        # words_per_str = 1
        self.assertEqual(
            ListingPrettyPrinter._generate_bytecode_line_string(
                word_list,
                1,
                16
            ),
            ['0000 ', '0001 ', '00a2 ', '0b03 ', '1234 ', 'abcd ', 'ffff ', '8000 '],
        )
        # words_per_str = 8 (all in one line)
        self.assertEqual(
            ListingPrettyPrinter._generate_bytecode_line_string(
                word_list,
                8,
                16
            ),
            ['0000 0001 00a2 0b03 1234 abcd ffff 8000 '],
        )
        # words_per_str = 3 (not an even divisor of 8)
        self.assertEqual(
            ListingPrettyPrinter._generate_bytecode_line_string(
                word_list,
                3,
                16
            ),
            ['0000 0001 00a2 ', '0b03 1234 abcd ', 'ffff 8000      '],
        )

    def test_listing_prints_original_mnemonic(self):
        fp = pkg_resources.files(config_files).joinpath('test_instruction_aliases.yaml')
        isa_model = AssemblerModel(str(fp), 0)
        memzone_mngr = MemoryZoneManager(
            isa_model.address_size,
            isa_model.default_origin,
            isa_model.predefined_memory_zones if hasattr(isa_model, 'predefined_memory_zones') else [],
        )
        # Source lines using both root and alias mnemonics
        lines = [
            'jsr',      # root mnemonic
            'call',     # alias for jsr
            'jsr2',     # root mnemonic
            'call2',    # alias for jsr2
            'nop',      # control
        ]
        line_objs = []
        preprocessor = Preprocessor()
        label_scope = GlobalLabelScope(set())
        for i, line in enumerate(lines, 1):
            line_obj = LineOjectFactory.parse_line(
                line_id=LineIdentifier(i, f'test_listing_prints_original_mnemonic - {line}'),
                line_str=line,
                model=isa_model,
                label_scope=None,
                current_memzone=memzone_mngr.global_zone,
                memzone_manager=memzone_mngr,
                preprocessor=preprocessor,
                condition_stack=None,
                log_verbosity=0,
            )[0]
            line_obj.set_start_address(0x1000 + i)
            line_obj.label_scope = label_scope
            line_obj.generate_words()
            line_objs.append(line_obj)
        printer = PrettyPrinterFactory.getPrettyPrinter('listing', line_objs, isa_model, 'test.asm')
        output = printer.pretty_print()
        # Check that each original mnemonic appears in the output
        for mnemonic in lines:
            self.assertIn(mnemonic, output, f'Listing should show original mnemonic: {mnemonic}')
