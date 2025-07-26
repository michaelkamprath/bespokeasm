import importlib.resources as pkg_resources
import unittest

from bespokeasm.assembler.bytecode.word import Word
from bespokeasm.assembler.engine import Assembler
from bespokeasm.assembler.label_scope import GlobalLabelScope
from bespokeasm.assembler.line_identifier import LineIdentifier
from bespokeasm.assembler.line_object import LineObject
from bespokeasm.assembler.line_object import LineWithWords
from bespokeasm.assembler.line_object.factory import LineOjectFactory
from bespokeasm.assembler.line_object.label_line import LabelLine
from bespokeasm.assembler.memory_zone.manager import MemoryZoneManager
from bespokeasm.assembler.model import AssemblerModel
from bespokeasm.assembler.preprocessor import Preprocessor
from bespokeasm.assembler.preprocessor.condition_stack import ConditionStack

from test import config_files


class TestAssemblerEngine(unittest.TestCase):
    def test_generate_bytes_from_line_objects_8bit_words(self):
        fp = pkg_resources.files(config_files).joinpath('test_instructions_with_variants.yaml')
        isa_model = AssemblerModel(str(fp), 0)
        memzone_mngr = MemoryZoneManager(
            isa_model.address_size,
            isa_model.default_origin,
            isa_model.predefined_memory_zones,
        )

        label_values = GlobalLabelScope(isa_model.registers)
        label_values.set_label_value('a_const', 40, 1)
        preprocessor = Preprocessor()
        condition_stack = ConditionStack()
        line_objects: list[LineObject] = []

        # this should generate the following bytes: 0x00
        line_objects.extend(
            LineOjectFactory.parse_line(
                LineIdentifier(0, 'test_generate_bytes_from_line_objects_8bit_words'),
                'nop ; do nothing',
                isa_model,
                label_values,
                memzone_mngr.global_zone,
                memzone_mngr,
                preprocessor,
                condition_stack,
                0,
            )
        )

        # this should generate the following bytes: 0x88
        line_objects.extend(
            LineOjectFactory.parse_line(
                LineIdentifier(1, 'test_generate_bytes_from_line_objects_8bit_words'),
                'the_byte: .byte 0x88 ; label and instruction',
                isa_model,
                label_values,
                memzone_mngr.global_zone,
                memzone_mngr,
                preprocessor,
                condition_stack,
                0,
            )
        )

        # this should generate the following bytes: 0b01000110 0x01 0x00
        # assuming the address of the_byte is 0x0001 (16-bit address space)
        line_objects.extend(
            LineOjectFactory.parse_line(
                LineIdentifier(2, 'test_generate_bytes_from_line_objects_8bit_words'),
                'the_instr: mov a, [the_byte] ; label and instruction',
                isa_model,
                label_values,
                memzone_mngr.global_zone,
                memzone_mngr,
                preprocessor,
                condition_stack,
                0,
            )
        )

        # "assemble" the line objects to a dictionary
        line_dict: dict[int, LineObject] = {}
        for lobj in line_objects:
            lobj.set_start_address(lobj.memory_zone.current_address)
            lobj.memory_zone.current_address = lobj.address + lobj.word_count
            lobj.label_scope = label_values
            if isinstance(lobj, LabelLine) and not lobj.is_constant:
                lobj.label_scope.set_label_value(lobj.get_label(), lobj.get_value(), lobj.line_id)
            line_dict[lobj.address] = lobj

        line_objects.sort(key=lambda x: x.address)
        max_generated_address = line_objects[-1].address

        for lobj in line_objects:
            if isinstance(lobj, LineWithWords):
                lobj.generate_words()
        # generate the bytecode
        bytecode = Assembler._generate_bytes(
            line_dict,
            max_generated_address,
            Word(0, 8, 8, 'big'),
            memzone_mngr.global_zone.start,
            None,
            2,
        )

        # now see if the right bytes were generated
        self.assertEqual(
            bytecode,
            bytearray([0, 0x88, 0b01000110, 1, 0]),
            'the bytecode should match',
        )

    def test_generate_bytes_from_line_objects_16bit_words(self):
        fp = pkg_resources.files(config_files).joinpath('test_16bit_data_words.yaml')
        isa_model = AssemblerModel(str(fp), 0)
        memzone_mngr = MemoryZoneManager(
            isa_model.address_size,
            isa_model.default_origin,
            isa_model.predefined_memory_zones,
        )

        label_values = GlobalLabelScope(isa_model.registers)
        label_values.set_label_value('a_const', 40, 1)
        preprocessor = Preprocessor()
        condition_stack = ConditionStack()
        line_objects: list[LineObject] = []

        line_objects.extend(
            LineOjectFactory.parse_line(
                LineIdentifier(0, 'test_generate_bytes_from_line_objects_16bit_words'),
                'nop ; do nothing',
                isa_model,
                label_values,
                memzone_mngr.global_zone,
                memzone_mngr,
                preprocessor,
                condition_stack,
                0,
            )
        )

        line_objects.extend(
            LineOjectFactory.parse_line(
                LineIdentifier(0, 'test_generate_bytes_from_line_objects_16bit_words'),
                'mov [$1234], [$8899] ; move it',
                isa_model,
                label_values,
                memzone_mngr.global_zone,
                memzone_mngr,
                preprocessor,
                condition_stack,
                0,
            )
        )

        line_objects.extend(
            LineOjectFactory.parse_line(
                LineIdentifier(0, 'test_generate_bytes_from_line_objects_16bit_words'),
                'my_label: push [$1234] ; push it real good',
                isa_model,
                label_values,
                memzone_mngr.global_zone,
                memzone_mngr,
                preprocessor,
                condition_stack,
                0,
            )
        )

        line_objects.extend(
            LineOjectFactory.parse_line(
                LineIdentifier(0, 'test_generate_bytes_from_line_objects_16bit_words'),
                'jmp my_label ; get out of here',
                isa_model,
                label_values,
                memzone_mngr.global_zone,
                memzone_mngr,
                preprocessor,
                condition_stack,
                0,
            )
        )

        # "assemble" the line objects to a dictionary
        line_dict: dict[int, LineObject] = {}
        for lobj in line_objects:
            lobj.set_start_address(lobj.memory_zone.current_address)
            lobj.memory_zone.current_address = lobj.address + lobj.word_count
            lobj.label_scope = label_values
            if isinstance(lobj, LabelLine) and not lobj.is_constant:
                lobj.label_scope.set_label_value(lobj.get_label(), lobj.get_value(), lobj.line_id)
            line_dict[lobj.address] = lobj

        line_objects.sort(key=lambda x: x.address)
        max_generated_address = line_objects[-1].address
        for lobj in line_objects:
            if isinstance(lobj, LineWithWords):
                lobj.generate_words()
        # generate the bytecode
        bytecode = Assembler._generate_bytes(
            line_dict,
            max_generated_address,
            Word(0, 16, 16, 'big'),
            memzone_mngr.global_zone.start,
            None,
            2,
        )

        # now see if the right bytes were generated
        self.assertEqual(
            bytecode,
            bytearray([
                0, 0,  # address 0
                8, 0x22, 0x88, 0x99, 0x12, 0x34,  # address 1, 2, 3
                0x04, 0x02, 0x12, 0x34,  # address 4, 5
                0x80, 0x01, 0x00, 0x04,  # address 6, 7
            ]),
            'the bytecode should match',
        )

    def test_generate_bytes_from_line_objects_4bit_words(self):
        # Simulate a 4-bit word ISA: two 4-bit words should be packed into one byte
        class DummyLineWithWords(LineWithWords):
            def __init__(self, address, words):
                self._address = address
                self._words = words
                self._memory_zone = type('mz', (), {'current_address': address})
                self._line_id = f'line_{address}'
                self.is_muted = False

            def get_words(self):
                return self._words

            @property
            def word_count(self):
                return len(self._words)

            @property
            def compilable(self):
                return True
        # Create two lines, each with two 4-bit words
        line1 = DummyLineWithWords(0, [Word(0xA, 4, 4), Word(0xB, 4, 4)])  # 0xA, 0xB
        line2 = DummyLineWithWords(2, [Word(0xC, 4, 4), Word(0xD, 4, 4)])  # 0xC, 0xD
        line_dict = {0: line1, 2: line2}
        max_generated_address = 2
        fill_word = Word(0x0, 4, 4)
        # Should produce: 0xAB, 0xCD
        bytecode = Assembler._generate_bytes(
            line_dict,
            max_generated_address,
            fill_word,
            0,
            None,
            2,
        )
        self.assertEqual(bytecode, bytearray([0xAB, 0xCD]), '4-bit words should be packed into bytes correctly')

    def test_generate_bytes_from_line_objects_4bit_words_with_fill(self):
        # Simulate a 4-bit word ISA with a gap, so fill_word is used and must be packed
        class DummyLineWithWords(LineWithWords):
            def __init__(self, address, words):
                self._address = address
                self._words = words
                self._memory_zone = type('mz', (), {'current_address': address})
                self._line_id = f'line_{address}'
                self.is_muted = False

            def get_words(self):
                return self._words

            @property
            def word_count(self):
                return len(self._words)

            @property
            def compilable(self):
                return True
        # Address 0: 0xA, Address 2: 0xB (address 1 missing, should be filled)
        line1 = DummyLineWithWords(0, [Word(0xA, 4, 4)])
        line2 = DummyLineWithWords(2, [Word(0xB, 4, 4)])
        line_dict = {0: line1, 2: line2}
        max_generated_address = 2
        fill_word = Word(0xF, 4, 4)  # Use 0xF as fill
        # Should produce: 0xAF (0xA from addr 0, 0xF fill for addr 1), 0xB0 (0xB from addr 2, 0x0 fill for addr 3)
        bytecode = Assembler._generate_bytes(
            line_dict,
            max_generated_address,
            fill_word,
            0,
            None,
            2,
        )
        self.assertEqual(bytecode, bytearray([0xAF, 0xB0]), 'fill_word should be packed with real words correctly')
