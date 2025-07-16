import unittest
import importlib.resources as pkg_resources

from bespokeasm.assembler.bytecode.word import Word
from bespokeasm.assembler.engine import Assembler
from bespokeasm.assembler.line_identifier import LineIdentifier
from bespokeasm.assembler.line_object import LineObject, LineWithWords
from bespokeasm.assembler.line_object.factory import LineOjectFactory
from bespokeasm.assembler.line_object.label_line import LabelLine
from bespokeasm.assembler.memory_zone.manager import MemoryZoneManager
from bespokeasm.assembler.model import AssemblerModel
from bespokeasm.assembler.label_scope import GlobalLabelScope

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
