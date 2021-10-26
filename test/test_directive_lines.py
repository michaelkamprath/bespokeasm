import sys
import unittest

from bespokeasm.assembler.label_scope import LabelScope, LabelScopeType
from bespokeasm.assembler.line_object.directive_line import DirectiveLine, AddressOrgLine, FillDataLine, FillUntilDataLine

class TestDirectiveLines(unittest.TestCase):
    def test_org_directive(self):
        o1 = DirectiveLine.factory(1234, '.org $100', 'set address to 0=x100', 'big')
        self.assertIsInstance(o1, AddressOrgLine)
        self.assertEqual(o1.address, 256)
        o1.set_start_address(512)
        self.assertEqual(o1.address, 256, '.org address values cannot be directly set')
        self.assertEqual(o1.byte_size, 0, '.org directives have 0 bytes')

        o2 = DirectiveLine.factory(5678, '.org 1024', 'set address to 1024', 'big')
        self.assertIsInstance(o2, AddressOrgLine)
        self.assertEqual(o2.address, 1024)

        o3 = DirectiveLine.factory(1357, '.org b100000000000', 'set address to 2048', 'big')
        self.assertIsInstance(o3, AddressOrgLine)
        self.assertEqual(o3.address, 2048)

        o4 = DirectiveLine.factory(1357, '.org 0xFFFF', 'set address to 54K', 'big')
        self.assertIsInstance(o4, AddressOrgLine)
        self.assertEqual(o4.address, 65535)

        with self.assertRaises(SystemExit, msg='non-numeric address should fail'):
            o5 = DirectiveLine.factory(1357, '.org a_label', 'set address to a label', 'big')

    def test_fill_directive(self):
        o1 = DirectiveLine.factory(1234, ' .fill 32, $77', 'fill with luck sevens', 'big')
        self.assertIsInstance(o1, FillDataLine)
        self.assertEqual(o1.byte_size, 32, 'has 32 bytes')
        self.assertEqual(o1.get_bytes(), bytearray([0x77]*32), '32 double 7s')

        o2 = DirectiveLine.factory(1234, ' .fill 0xFF, 0x2211', 'snake eyes', 'big')
        self.assertIsInstance(o2, FillDataLine)
        self.assertEqual(o2.byte_size, 255, 'has 255 bytes')
        self.assertEqual(o2.get_bytes(), bytearray([0x11]*255), 'truncated values')

        o3 = DirectiveLine.factory(1234, '.zero b100000000', 'zipity doo dah', 'big')
        self.assertIsInstance(o3, FillDataLine)
        self.assertEqual(o3.byte_size, 256, 'has 256 bytes')
        self.assertEqual(o3.get_bytes(), bytearray([0]*256), 'truncated values')

    def test_filluntil_directive(self):
        label_values = LabelScope(LabelScopeType.GLOBAL, None, 'global')
        label_values.set_label_value('my_label', 0x80, 1)

        o1 = DirectiveLine.factory(1234, ' .zerountil $100', 'fill with nothing', 'big')
        self.assertIsInstance(o1, FillUntilDataLine)
        o1.set_start_address(0x42)
        o1.label_scope = label_values
        self.assertEqual(o1.byte_size, (0x100-0x42+1), 'must have the right number of bytes')
        o1.generate_bytes()
        self.assertEqual(o1.get_bytes(), bytearray([0]*(0x100-0x42+1)), 'must have all the bytes')

        # test fill until current address
        o2 = DirectiveLine.factory(1234, '.zerountil 0xF', 'them zeros', 'big')
        self.assertIsInstance(o2, FillUntilDataLine)
        o2.set_start_address(0xF)
        o2.label_scope = label_values
        self.assertEqual(o2.byte_size, 1, 'must have the right number of bytes')
        o2.generate_bytes()
        self.assertEqual(o2.get_bytes(), bytearray([0]*1), 'must have all the bytes')

if __name__ == '__main__':
    unittest.main()