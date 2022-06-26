import unittest
import importlib.resources as pkg_resources

from test import config_files

from bespokeasm.assembler.label_scope import GlobalLabelScope
from bespokeasm.assembler.label_scope import LabelScope, LabelScopeType
from bespokeasm.assembler.line_object.directive_line import DirectiveLine, AddressOrgLine, FillDataLine, FillUntilDataLine
from bespokeasm.assembler.model import AssemblerModel

class TestDirectiveLines(unittest.TestCase):

    isa_model = None
    @classmethod
    def setUpClass(cls):
        with pkg_resources.path(config_files, 'test_instruction_list_creation_isa.json') as fp:
            TestDirectiveLines.isa_model = AssemblerModel(str(fp), 0)

    def test_org_directive(self):
        label_values = GlobalLabelScope(['a', 'b', 'sp', 'mar'])
        label_values.set_label_value('a_const', 40, 1)

        o1 = DirectiveLine.factory(1234, '.org $100', 'set address to 0=x100', TestDirectiveLines.isa_model)
        self.assertIsInstance(o1, AddressOrgLine)
        self.assertEqual(o1.address, 256)
        o1.set_start_address(512)
        self.assertEqual(o1.address, 256, '.org address values cannot be directly set')
        self.assertEqual(o1.byte_size, 0, '.org directives have 0 bytes')

        o2 = DirectiveLine.factory(5678, '.org 1024', 'set address to 1024', TestDirectiveLines.isa_model)
        self.assertIsInstance(o2, AddressOrgLine)
        self.assertEqual(o2.address, 1024)

        o3 = DirectiveLine.factory(1357, '.org b100000000000', 'set address to 2048', TestDirectiveLines.isa_model)
        self.assertIsInstance(o3, AddressOrgLine)
        self.assertEqual(o3.address, 2048)

        o4 = DirectiveLine.factory(1357, '.org 0xFFFF', 'set address to 54K', TestDirectiveLines.isa_model)
        self.assertIsInstance(o4, AddressOrgLine)
        self.assertEqual(o4.address, 65535)

        o5 = DirectiveLine.factory(1357, '.org a_const', 'set address to a label', TestDirectiveLines.isa_model)
        o5.label_scope = label_values
        self.assertIsInstance(o5, AddressOrgLine)
        self.assertEqual(o5.address, 40)

        with self.assertRaises(SystemExit, msg='register address should fail'):
            e1 = DirectiveLine.factory(1357, '.org sp', 'set address to a register', TestDirectiveLines.isa_model)
            e1.label_scope = label_values
            e1.address

    def test_fill_directive(self):

        label_values = GlobalLabelScope(['a', 'b', 'sp', 'mar'])
        label_values.set_label_value('forty', 40, 1)
        label_values.set_label_value('eff', 0x0F, 1)
        label_values.set_label_value('high_de', 0xde00, 1)
        label_values.set_label_value('MAX_N', 20, 1)

        o1 = DirectiveLine.factory(1234, ' .fill 32, $77', 'fill with luck sevens', TestDirectiveLines.isa_model)
        self.assertIsInstance(o1, FillDataLine)
        o1.label_scope = label_values
        self.assertEqual(o1.byte_size, 32, 'has 32 bytes')
        o1.generate_bytes()
        self.assertEqual(o1.get_bytes(), bytearray([0x77]*32), '32 double 7s')

        o2 = DirectiveLine.factory(1234, ' .fill 0xFF, 0x2211', 'snake eyes', TestDirectiveLines.isa_model)
        self.assertIsInstance(o2, FillDataLine)
        o2.label_scope = label_values
        self.assertEqual(o2.byte_size, 255, 'has 255 bytes')
        o2.generate_bytes()
        self.assertEqual(o2.get_bytes(), bytearray([0x11]*255), 'truncated values')

        o2b = DirectiveLine.factory(1234, ' .fill 8*MAX_N + 1, eff|$A0', 'snake eyes', TestDirectiveLines.isa_model)
        self.assertIsInstance(o2b, FillDataLine)
        o2b.label_scope = label_values
        self.assertEqual(o2b.byte_size, 161, 'has 161 bytes')
        o2b.generate_bytes()
        self.assertEqual(o2b.get_bytes(), bytearray([0xAF]*161), 'complex expression in directive arguments')


        o3 = DirectiveLine.factory(1234, '.zero b100000000', 'zipity doo dah', TestDirectiveLines.isa_model)
        self.assertIsInstance(o3, FillDataLine)
        o3.label_scope = label_values
        self.assertEqual(o3.byte_size, 256, 'has 256 bytes')
        o3.generate_bytes()
        self.assertEqual(o3.get_bytes(), bytearray([0]*256), 'truncated values')

        # test with constants
        o4 = DirectiveLine.factory(1234, '.zero forty', 'constants in directives', TestDirectiveLines.isa_model)
        self.assertIsInstance(o4, FillDataLine)
        o4.label_scope = label_values
        self.assertEqual(o4.byte_size, 40, 'has 40 bytes')
        o4.generate_bytes()
        self.assertEqual(list(o4.get_bytes()), [0]*40, 'truncated values')

        o5 = DirectiveLine.factory(1234, '.fill eff, forty', 'constants in directives', TestDirectiveLines.isa_model)
        self.assertIsInstance(o5, FillDataLine)
        o5.label_scope = label_values
        self.assertEqual(o5.byte_size, 15, 'has 15 bytes')
        o5.generate_bytes()
        self.assertEqual(list(o5.get_bytes()), [40]*15, 'truncated values')

        o6 = DirectiveLine.factory(1234, '.fill eff+eff, forty+2', 'constants in directives', TestDirectiveLines.isa_model)
        self.assertIsInstance(o6, FillDataLine)
        o6.label_scope = label_values
        self.assertEqual(o6.byte_size, 30, 'has 30 bytes')
        o6.generate_bytes()
        self.assertEqual(list(o6.get_bytes()), [42]*30, 'truncated values')

        o6 = DirectiveLine.factory(1234, '.zero forty+2', 'constants in directives', TestDirectiveLines.isa_model)
        self.assertIsInstance(o6, FillDataLine)
        o6.label_scope = label_values
        self.assertEqual(o6.byte_size, 42, 'has 42 bytes')
        o6.generate_bytes()
        self.assertEqual(list(o6.get_bytes()), [0]*42, 'truncated values')

        o7 = DirectiveLine.factory(1234, '.zero 8*(MAX_N+1)', 'constants in directives', TestDirectiveLines.isa_model)
        self.assertIsInstance(o7, FillDataLine)
        o7.label_scope = label_values
        self.assertEqual(o7.byte_size, 168, 'has 168 bytes')
        o7.generate_bytes()
        self.assertEqual(list(o7.get_bytes()), [0]*168, 'truncated values')

    def test_filluntil_directive(self):
        label_values = LabelScope(LabelScopeType.GLOBAL, None, 'global')
        label_values.set_label_value('my_label', 0x80, 1)

        o1 = DirectiveLine.factory(1234, ' .zerountil $100', 'fill with nothing', TestDirectiveLines.isa_model)
        self.assertIsInstance(o1, FillUntilDataLine)
        o1.set_start_address(0x42)
        o1.label_scope = label_values
        self.assertEqual(o1.byte_size, (0x100-0x42+1), 'must have the right number of bytes')
        o1.generate_bytes()
        self.assertEqual(o1.get_bytes(), bytearray([0]*(0x100-0x42+1)), 'must have all the bytes')

        # test fill until current address
        o2 = DirectiveLine.factory(1234, '.zerountil 0xF', 'them zeros', TestDirectiveLines.isa_model)
        self.assertIsInstance(o2, FillUntilDataLine)
        o2.set_start_address(0xF)
        o2.label_scope = label_values
        self.assertEqual(o2.byte_size, 1, 'must have the right number of bytes')
        o2.generate_bytes()
        self.assertEqual(o2.get_bytes(), bytearray([0]*1), 'must have all the bytes')

        o3 = DirectiveLine.factory(1234, '.zerountil my_label+$f', 'them zeros', TestDirectiveLines.isa_model)
        self.assertIsInstance(o3, FillUntilDataLine)
        o3.set_start_address(0xF)
        o3.label_scope = label_values
        self.assertEqual(o3.byte_size, 0x81, 'must have the right number of bytes')
        o3.generate_bytes()
        self.assertEqual(list(o3.get_bytes()), [0]*0x81, 'must have all the bytes')


if __name__ == '__main__':
    unittest.main()
