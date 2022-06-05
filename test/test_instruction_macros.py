import unittest
import importlib.resources as pkg_resources

from test import config_files

from bespokeasm.assembler.label_scope import GlobalLabelScope, LabelScope, LabelScopeType
from bespokeasm.assembler.model import AssemblerModel
from bespokeasm.assembler.line_object.instruction_line import InstructionLine
from bespokeasm.assembler.line_identifier import LineIdentifier

class TestInstructionMacros(unittest.TestCase):
    label_values = None

    @classmethod
    def setUpClass(cls):
        global_scope = GlobalLabelScope(set())
        global_scope.set_label_value('var1', 0x4589, 1)
        global_scope.set_label_value('my_val', 8, 2)
        global_scope.set_label_value('the_two', 2, 3)
        local_scope = LabelScope(LabelScopeType.LOCAL, global_scope, 'TestInstructionParsing')
        local_scope.set_label_value('.local_var', 10, 3)
        cls.label_values = local_scope

    def test_macro_parsing_numeric_args(self):
        with pkg_resources.path(config_files, 'test_instruction_macros.yaml') as fp:
            isa_model = AssemblerModel(str(fp), 0)

        line_id = LineIdentifier(1, 'test_macro_parsing')

        ins0 = InstructionLine.factory(line_id, 'push2 $1234', 'some comment!', isa_model)
        ins0.set_start_address(1212)
        self.assertIsInstance(ins0, InstructionLine)
        self.assertEqual(ins0.byte_size, 4, 'has 4 bytes')
        ins0.label_scope = TestInstructionMacros.label_values
        ins0.generate_bytes()
        self.assertEqual(list(ins0.get_bytes()), [0x0F, 0x12, 0x0F, 0x34], 'instruction bytes should match')

        ins1 = InstructionLine.factory(line_id, 'mov2 [$2000],[$1234]', 'some comment!', isa_model)
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

        ins2 = InstructionLine.factory(line_id, 'add16 [$1234], $5678', 'some comment!', isa_model)
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

        ins3 = InstructionLine.factory(line_id, 'add16 [$1234], [var1+7]', 'some comment!', isa_model)
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