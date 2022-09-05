import unittest
import importlib.resources as pkg_resources

from test import config_files

from bespokeasm.assembler.label_scope import LabelScope, LabelScopeType
from bespokeasm.assembler.model import AssemblerModel
from bespokeasm.assembler.line_object.instruction_line import InstructionLine
from bespokeasm.assembler.line_identifier import LineIdentifier
from bespokeasm.assembler.memory_zone.manager import MemoryZoneManager


class TestInstructionMacros(unittest.TestCase):
    label_values = None
    isa_model = None
    memory_zone_manager = None
    memzone = None

    @classmethod
    def setUpClass(cls):
        with pkg_resources.path(config_files, 'test_instruction_macros.yaml') as fp:
            cls.isa_model = AssemblerModel(str(fp), 0)

        global_scope = cls.isa_model.global_label_scope
        global_scope.set_label_value('var1', 0x4589, 1)
        global_scope.set_label_value('my_val', 8, 2)
        global_scope.set_label_value('the_two', 2, 3)
        local_scope = LabelScope(LabelScopeType.LOCAL, global_scope, 'TestInstructionParsing')
        local_scope.set_label_value('.local_var', 10, 3)
        cls.label_values = local_scope
        cls.memory_zone_manager = MemoryZoneManager(
            TestInstructionMacros.isa_model.address_size,
            TestInstructionMacros.isa_model.default_origin,
        )
        cls.memzone = cls.memory_zone_manager.global_zone

    def test_macro_parsing_numeric_args(self):
        isa_model = self.isa_model
        memzone = self.memzone

        line_id = LineIdentifier(1, 'test_macro_parsing_numeric_args')

        ins0 = InstructionLine.factory(line_id, 'push2 $1234', 'some comment!', isa_model, memzone)
        ins0.set_start_address(1212)
        self.assertIsInstance(ins0, InstructionLine)
        self.assertEqual(ins0.byte_size, 4, 'has 4 bytes')
        ins0.label_scope = TestInstructionMacros.label_values
        ins0.generate_bytes()
        self.assertEqual(list(ins0.get_bytes()), [0x0F, 0x12, 0x0F, 0x34], 'instruction bytes should match')

        ins1 = InstructionLine.factory(line_id, 'mov2 [$2000],[$1234]', 'some comment!', isa_model, memzone)
        ins1.set_start_address(1212)
        self.assertIsInstance(ins1, InstructionLine)
        self.assertEqual(ins1.byte_size, 10, 'has 10 bytes')
        ins1.label_scope = TestInstructionMacros.label_values
        ins1.generate_bytes()
        self.assertEqual(
            list(ins1.get_bytes()),
            [0b01110110, 0, 0x20, 0x34, 0x12, 0b01110110, 1, 0x20, 0x35, 0x12],
            'instruction bytes should match'
        )

        ins2 = InstructionLine.factory(line_id, 'add16 [$1234], $5678', 'some comment!', isa_model, memzone)
        ins2.set_start_address(1212)
        self.assertIsInstance(ins2, InstructionLine)
        self.assertEqual(ins2.byte_size, 16, 'has 16 bytes')
        ins2.label_scope = TestInstructionMacros.label_values
        ins2.generate_bytes()
        self.assertEqual(
            list(ins2.get_bytes()),
            [
                0b01000110, 0x34, 0x12,
                0b00010111, 0x78,
                0b01110000, 0x34, 0x12,
                0b01000110, 0x35, 0x12,
                0b00011111, 0x56,
                0b01110000, 0x35, 0x12,
            ],
            'instruction bytes should match'
        )

        ins3 = InstructionLine.factory(line_id, 'add16 [$1234], [var1+7]', 'some comment!', isa_model, memzone)
        ins3.set_start_address(1212)
        self.assertIsInstance(ins3, InstructionLine)
        self.assertEqual(ins3.byte_size, 18, 'has 18 bytes')
        ins3.label_scope = TestInstructionMacros.label_values
        ins3.generate_bytes()
        self.assertEqual(
            list(ins3.get_bytes()),
            [
                0b01000110, 0x34, 0x12,
                0b00010110, 0x90, 0x45,
                0b01110000, 0x34, 0x12,
                0b01000110, 0x35, 0x12,
                0b00011110, 0x91, 0x45,
                0b01110000, 0x35, 0x12,
            ],
            'instruction bytes should match'
        )

    def test_macro_parsing_registers(self):
        isa_model = self.isa_model
        memzone = self.memzone

        line_id = LineIdentifier(1, 'test_macro_parsing_registers')

        ins4 = InstructionLine.factory(line_id, 'push2 [ij + 4]', 'some comment!', isa_model, memzone)
        ins4.set_start_address(1212)
        self.assertIsInstance(ins4, InstructionLine)
        self.assertEqual(ins4.byte_size, 4, 'has 4 bytes')
        ins4.label_scope = TestInstructionMacros.label_values
        ins4.generate_bytes()
        self.assertEqual(
            list(ins4.get_bytes()),
            [
                0b00001100, 5,
                0b00001100, 4,
            ],
            'instruction bytes should match'
        )

        ins5 = InstructionLine.factory(line_id, 'push2 [sp + 8]', 'some comment!', isa_model, memzone)
        ins5.set_start_address(1212)
        self.assertIsInstance(ins5, InstructionLine)
        self.assertEqual(ins5.byte_size, 4, 'has 4 bytes')
        ins5.label_scope = TestInstructionMacros.label_values
        ins5.generate_bytes()
        self.assertEqual(
            list(ins5.get_bytes()),
            [
                0b00001101, 9,
                0b00001101, 9,
            ],
            'instruction bytes should match'
        )

    def test_macro_parsing_operands(self):
        isa_model = self.isa_model
        memzone = self.memzone

        line_id = LineIdentifier(1, 'test_macro_parsing_operands')

        ins1 = InstructionLine.factory(line_id, 'swap a,j', 'some comment!', isa_model, memzone)
        ins1.set_start_address(1212)
        self.assertIsInstance(ins1, InstructionLine)
        self.assertEqual(ins1.byte_size, 3, 'has 3 bytes')
        ins1.label_scope = TestInstructionMacros.label_values
        ins1.generate_bytes()
        self.assertEqual(
            list(ins1.get_bytes()),
            [
                0b00001000,
                0b01000011,
                0b00000011,
            ],
            'instruction bytes should match'
        )

        ins2 = InstructionLine.factory(line_id, 'swap i,j', 'some comment!', isa_model, memzone)
        ins2.set_start_address(1212)
        self.assertIsInstance(ins2, InstructionLine)
        self.assertEqual(ins2.byte_size, 3, 'has 3 bytes')
        ins2.label_scope = TestInstructionMacros.label_values
        ins2.generate_bytes()
        self.assertEqual(
            list(ins2.get_bytes()),
            [
                0b00001010,
                0b01010011,
                0b00000011,
            ],
            'instruction bytes should match'
        )

        ins3 = InstructionLine.factory(line_id, 'swap a,[ij + 4]', 'some comment!', isa_model, memzone)
        ins3.set_start_address(1212)
        self.assertIsInstance(ins3, InstructionLine)
        self.assertEqual(ins3.byte_size, 5, 'has 5 bytes')
        ins3.label_scope = TestInstructionMacros.label_values
        ins3.generate_bytes()
        self.assertEqual(
            list(ins3.get_bytes()),
            [
                0b00001000,
                0b01000100, 4,
                0b00000100, 4,
            ],
            'instruction bytes should match'
        )

        ins4 = InstructionLine.factory(line_id, 'swap [sp+10],[ij + 4]', 'some comment!', isa_model, memzone)
        ins4.set_start_address(1212)
        self.assertIsInstance(ins4, InstructionLine)
        self.assertEqual(ins4.byte_size, 7, 'has 7 bytes')
        ins4.label_scope = TestInstructionMacros.label_values
        ins4.generate_bytes()
        self.assertEqual(
            list(ins4.get_bytes()),
            [
                0b00001101, 10,
                0b01101100, 11, 4,
                0b00000100, 4,
            ],
            'instruction bytes should match'
        )

        ins5 = InstructionLine.factory(line_id, 'swap [sp+10],[sp+predefined_value1]', 'some comment!', isa_model, memzone)
        ins5.set_start_address(1212)
        self.assertIsInstance(ins5, InstructionLine)
        self.assertEqual(ins5.byte_size, 7, 'has 7 bytes')
        ins5.label_scope = TestInstructionMacros.label_values
        ins5.generate_bytes()
        self.assertEqual(
            list(ins5.get_bytes()),
            [
                0b00001101, 10,
                0b01101101, 11, 21,
                0b00000101, 21,
            ],
            'instruction bytes should match'
        )

        ins6 = InstructionLine.factory(line_id, 'mov2 [$8008],$1234', 'some comment!', isa_model, memzone)
        ins6.set_start_address(1212)
        self.assertIsInstance(ins6, InstructionLine)
        self.assertEqual(ins6.byte_size, 8, 'has 8 bytes')
        ins6.label_scope = TestInstructionMacros.label_values
        ins6.generate_bytes()
        self.assertEqual(
            list(ins6.get_bytes()),
            [
                0b01110111, 0x08, 0x80, 0x34,
                0b01110111, 0x09, 0x80, 0x12,
            ],
            'instruction bytes should match'
        )
