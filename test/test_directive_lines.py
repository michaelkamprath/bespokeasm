import unittest
import importlib.resources as pkg_resources
import copy

from test import config_files

from bespokeasm.assembler.label_scope import GlobalLabelScope
from bespokeasm.assembler.label_scope import LabelScope, LabelScopeType
from bespokeasm.assembler.line_object import LineObject
from bespokeasm.assembler.line_object.directive_line.fill_data import FillDataLine, FillUntilDataLine
from bespokeasm.assembler.line_object.directive_line.factory import DirectiveLine
from bespokeasm.assembler.line_object.directive_line.address import AddressOrgLine
from bespokeasm.assembler.line_object.directive_line.page_align import PageAlignLine
from bespokeasm.assembler.line_object import LineWithBytes
from bespokeasm.assembler.model import AssemblerModel
from bespokeasm.assembler.memory_zone.manager import MemoryZoneManager
from bespokeasm.assembler.line_identifier import LineIdentifier


class TestDirectiveLines(unittest.TestCase):
    memory_zone_manager = None
    memzone = None
    isa_model = None

    @classmethod
    def setUpClass(cls):
        fp = pkg_resources.files(config_files).joinpath('test_instruction_list_creation_isa.json')
        TestDirectiveLines.isa_model = AssemblerModel(str(fp), 0)
        cls.memory_zone_manager = MemoryZoneManager(
            TestDirectiveLines.isa_model.address_size,
            TestDirectiveLines.isa_model.default_origin,
        )
        cls.memzone = cls.memory_zone_manager.global_zone
        cls.memory_zone_manager.create_zone(4, 2, 15, 'zone1')
        cls.memory_zone_manager.create_zone(4, 4, 8, 'zone2')

    def test_org_directive(self):
        label_values = GlobalLabelScope(['a', 'b', 'sp', 'mar'])
        label_values.set_label_value('a_const', 12, 1)

        o1 = DirectiveLine.factory(
            1234,
            '.org $1',
            'set address to 0=x100',
            TestDirectiveLines.isa_model.endian,
            TestDirectiveLines.memzone,
            TestDirectiveLines.memory_zone_manager,
            TestDirectiveLines.isa_model,
        )
        self.assertIsInstance(o1, AddressOrgLine)
        self.assertEqual(o1.address, 1)
        o1.set_start_address(10)
        self.assertEqual(o1.address, 1, '.org address values cannot be directly set')
        self.assertEqual(o1.byte_size, 0, '.org directives have 0 bytes')

        o2 = DirectiveLine.factory(
            5678,
            '.org 8',
            'set address to 1024',
            TestDirectiveLines.isa_model.endian,
            TestDirectiveLines.memzone,
            TestDirectiveLines.memory_zone_manager,
            TestDirectiveLines.isa_model,
        )
        self.assertIsInstance(o2, AddressOrgLine)
        self.assertEqual(o2.address, 8)

        o3 = DirectiveLine.factory(
            1357,
            '.org b000000000100',
            'set address to 2048',
            TestDirectiveLines.isa_model.endian,
            TestDirectiveLines.memzone,
            TestDirectiveLines.memory_zone_manager,
            TestDirectiveLines.isa_model,
        )
        self.assertIsInstance(o3, AddressOrgLine)
        self.assertEqual(o3.address, 4)

        o4 = DirectiveLine.factory(
            1357,
            '.org 0x000F',
            'set address to 54K',
            TestDirectiveLines.isa_model.endian,
            TestDirectiveLines.memzone,
            TestDirectiveLines.memory_zone_manager,
            TestDirectiveLines.isa_model,
        )
        self.assertIsInstance(o4, AddressOrgLine)
        self.assertEqual(o4.address, 15)

        o5 = DirectiveLine.factory(
            1357,
            '.org a_const',
            'set address to a label',
            TestDirectiveLines.isa_model.endian,
            TestDirectiveLines.memzone,
            TestDirectiveLines.memory_zone_manager,
            TestDirectiveLines.isa_model,
        )
        o5.label_scope = label_values
        self.assertIsInstance(o5, AddressOrgLine)
        self.assertEqual(o5.address, 12)

        with self.assertRaises(SystemExit, msg='register address should fail'):
            e1 = DirectiveLine.factory(
                1357,
                '.org sp',
                'set address to a register',
                TestDirectiveLines.isa_model.endian,
                TestDirectiveLines.memzone,
                TestDirectiveLines.memory_zone_manager,
                TestDirectiveLines.isa_model,
            )
            e1.label_scope = label_values
            e1.address

        # test with memory zones
        o6 = DirectiveLine.factory(
            1357,
            '.org a_const "zone1"',
            'set address to a label',
            TestDirectiveLines.isa_model.endian,
            TestDirectiveLines.memzone,
            TestDirectiveLines.memory_zone_manager,
            TestDirectiveLines.isa_model,
        )
        o6.label_scope = label_values
        self.assertIsInstance(o6, AddressOrgLine)
        self.assertEqual(o6.address, 14)

        o7 = DirectiveLine.factory(
            1357,
            '.org a_const/2 + 5 "zone2"',
            'set address to a label',
            TestDirectiveLines.isa_model.endian,
            TestDirectiveLines.memzone,
            TestDirectiveLines.memory_zone_manager,
            TestDirectiveLines.isa_model,
        )
        o7.label_scope = label_values
        self.assertIsInstance(o7, AddressOrgLine)
        self.assertEqual(o7.address, 15)

    def test_fill_directive(self):

        label_values = GlobalLabelScope(['a', 'b', 'sp', 'mar'])
        label_values.set_label_value('forty', 40, 1)
        label_values.set_label_value('eff', 0x0F, 1)
        label_values.set_label_value('high_de', 0xde00, 1)
        label_values.set_label_value('MAX_N', 20, 1)

        o1 = DirectiveLine.factory(
            1234,
            ' .fill 32, $77',
            'fill with luck sevens',
            TestDirectiveLines.isa_model.endian,
            TestDirectiveLines.memzone,
            TestDirectiveLines.memory_zone_manager,
            TestDirectiveLines.isa_model,
        )
        self.assertIsInstance(o1, FillDataLine)
        o1.label_scope = label_values
        self.assertEqual(o1.byte_size, 32, 'has 32 bytes')
        o1.generate_bytes()
        self.assertEqual(o1.get_bytes(), bytearray([0x77]*32), '32 double 7s')

        o2 = DirectiveLine.factory(
            1234,
            ' .fill 0xFF, 0x2211',
            'snake eyes',
            TestDirectiveLines.isa_model.endian,
            TestDirectiveLines.memzone,
            TestDirectiveLines.memory_zone_manager,
            TestDirectiveLines.isa_model,
        )
        self.assertIsInstance(o2, FillDataLine)
        o2.label_scope = label_values
        self.assertEqual(o2.byte_size, 255, 'has 255 bytes')
        o2.generate_bytes()
        self.assertEqual(o2.get_bytes(), bytearray([0x11]*255), 'truncated values')

        o2b = DirectiveLine.factory(
            1234,
            ' .fill 8*MAX_N + 1, eff|$A0',
            'snake eyes',
            TestDirectiveLines.isa_model.endian,
            TestDirectiveLines.memzone,
            TestDirectiveLines.memory_zone_manager,
            TestDirectiveLines.isa_model,
        )
        self.assertIsInstance(o2b, FillDataLine)
        o2b.label_scope = label_values
        self.assertEqual(o2b.byte_size, 161, 'has 161 bytes')
        o2b.generate_bytes()
        self.assertEqual(o2b.get_bytes(), bytearray([0xAF]*161), 'complex expression in directive arguments')

        o3 = DirectiveLine.factory(
            1234,
            '.zero b000000100',
            'zipity doo dah',
            TestDirectiveLines.isa_model.endian,
            TestDirectiveLines.memzone,
            TestDirectiveLines.memory_zone_manager,
            TestDirectiveLines.isa_model,
        )
        self.assertIsInstance(o3, FillDataLine)
        o3.label_scope = label_values
        self.assertEqual(o3.byte_size, 4, 'has 4 bytes')
        o3.generate_bytes()
        self.assertEqual(o3.get_bytes(), bytearray([0]*4), 'truncated values')

        # test with constants
        o4 = DirectiveLine.factory(
            1234,
            '.zero forty',
            'constants in directives',
            TestDirectiveLines.isa_model.endian,
            TestDirectiveLines.memzone,
            TestDirectiveLines.memory_zone_manager,
            TestDirectiveLines.isa_model,
        )
        self.assertIsInstance(o4, FillDataLine)
        o4.label_scope = label_values
        self.assertEqual(o4.byte_size, 40, 'has 40 bytes')
        o4.generate_bytes()
        self.assertEqual(list(o4.get_bytes()), [0]*40, 'truncated values')

        o5 = DirectiveLine.factory(
            1234,
            '.fill eff, forty',
            'constants in directives',
            TestDirectiveLines.isa_model.endian,
            TestDirectiveLines.memzone,
            TestDirectiveLines.memory_zone_manager,
            TestDirectiveLines.isa_model,
        )
        self.assertIsInstance(o5, FillDataLine)
        o5.label_scope = label_values
        self.assertEqual(o5.byte_size, 15, 'has 15 bytes')
        o5.generate_bytes()
        self.assertEqual(list(o5.get_bytes()), [40]*15, 'truncated values')

        o6 = DirectiveLine.factory(
            1234,
            '.fill eff+eff, forty+2',
            'constants in directives',
            TestDirectiveLines.isa_model.endian,
            TestDirectiveLines.memzone,
            TestDirectiveLines.memory_zone_manager,
            TestDirectiveLines.isa_model,
        )
        self.assertIsInstance(o6, FillDataLine)
        o6.label_scope = label_values
        self.assertEqual(o6.byte_size, 30, 'has 30 bytes')
        o6.generate_bytes()
        self.assertEqual(list(o6.get_bytes()), [42]*30, 'truncated values')

        o6 = DirectiveLine.factory(
            1234,
            '.zero forty+2',
            'constants in directives',
            TestDirectiveLines.isa_model.endian,
            TestDirectiveLines.memzone,
            TestDirectiveLines.memory_zone_manager,
            TestDirectiveLines.isa_model,
        )
        self.assertIsInstance(o6, FillDataLine)
        o6.label_scope = label_values
        self.assertEqual(o6.byte_size, 42, 'has 42 bytes')
        o6.generate_bytes()
        self.assertEqual(list(o6.get_bytes()), [0]*42, 'truncated values')

        o7 = DirectiveLine.factory(
            1234,
            '.zero 8*(MAX_N+1)',
            'constants in directives',
            TestDirectiveLines.isa_model.endian,
            TestDirectiveLines.memzone,
            TestDirectiveLines.memory_zone_manager,
            TestDirectiveLines.isa_model,
        )
        self.assertIsInstance(o7, FillDataLine)
        o7.label_scope = label_values
        self.assertEqual(o7.byte_size, 168, 'has 168 bytes')
        o7.generate_bytes()
        self.assertEqual(list(o7.get_bytes()), [0]*168, 'truncated values')

    def test_filluntil_directive(self):
        label_values = LabelScope(LabelScopeType.GLOBAL, None, 'global')
        label_values.set_label_value('my_label', 0x80, 1)

        o1 = DirectiveLine.factory(
            1234,
            ' .zerountil $100',
            'fill with nothing',
            TestDirectiveLines.isa_model.endian,
            TestDirectiveLines.memzone,
            TestDirectiveLines.memory_zone_manager,
            TestDirectiveLines.isa_model,
        )
        self.assertIsInstance(o1, FillUntilDataLine)
        o1.set_start_address(0x42)
        o1.label_scope = label_values
        self.assertEqual(o1.byte_size, (0x100-0x42+1), 'must have the right number of bytes')
        o1.generate_bytes()
        self.assertEqual(o1.get_bytes(), bytearray([0]*(0x100-0x42+1)), 'must have all the bytes')

        # test fill until current address
        o2 = DirectiveLine.factory(
            1234,
            '.zerountil 0xF',
            'them zeros',
            TestDirectiveLines.isa_model.endian,
            TestDirectiveLines.memzone,
            TestDirectiveLines.memory_zone_manager,
            TestDirectiveLines.isa_model,
        )
        self.assertIsInstance(o2, FillUntilDataLine)
        o2.set_start_address(0xF)
        o2.label_scope = label_values
        self.assertEqual(o2.byte_size, 1, 'must have the right number of bytes')
        o2.generate_bytes()
        self.assertEqual(o2.get_bytes(), bytearray([0]*1), 'must have all the bytes')

        o3 = DirectiveLine.factory(
            1234,
            '.zerountil my_label+$f',
            'them zeros',
            TestDirectiveLines.isa_model.endian,
            TestDirectiveLines.memzone,
            TestDirectiveLines.memory_zone_manager,
            TestDirectiveLines.isa_model,
        )
        self.assertIsInstance(o3, FillUntilDataLine)
        o3.set_start_address(0xF)
        o3.label_scope = label_values
        self.assertEqual(o3.byte_size, 0x81, 'must have the right number of bytes')
        o3.generate_bytes()
        self.assertEqual(list(o3.get_bytes()), [0]*0x81, 'must have all the bytes')

    def test_cstr_directive(self):
        label_values = LabelScope(LabelScopeType.GLOBAL, None, 'global')
        label_values.set_label_value('my_label', 0x80, 1)
        local_isa_model = copy.deepcopy(TestDirectiveLines.isa_model)

        local_isa_model._config['general']['cstr_terminator'] = 0
        t1: LineObject = DirectiveLine.factory(
            1234,
            '.cstr "this is a test"',
            'that str',
            TestDirectiveLines.isa_model.endian,
            TestDirectiveLines.memzone,
            TestDirectiveLines.memory_zone_manager,
            local_isa_model
        )
        self.assertIsInstance(t1, LineWithBytes)
        t1.set_start_address(0xF)
        t1.label_scope = label_values
        self.assertEqual(t1.byte_size, 15, 'must have the right number of bytes')
        t1.generate_bytes()
        self.assertEqual(list(t1.get_bytes())[-1], 0, 'terminating character must match')

        local_isa_model._config['general']['cstr_terminator'] = 3
        t2 = DirectiveLine.factory(
            1234,
            '.cstr "this is a test"',
            'that str',
            TestDirectiveLines.isa_model.endian,
            TestDirectiveLines.memzone,
            TestDirectiveLines.memory_zone_manager,
            local_isa_model
        )
        self.assertIsInstance(t1, LineWithBytes)
        t2.set_start_address(0xF)
        t2.label_scope = label_values
        self.assertEqual(t2.byte_size, 15, 'must have the right number of bytes')
        t2.generate_bytes()
        self.assertEqual(list(t2.get_bytes())[-1], 3, 'terminating character must match')

    def test_page_align_line(self):
        t1: LineObject = DirectiveLine.factory(
            1234,
            '.align',
            'page align',
            TestDirectiveLines.isa_model.endian,
            TestDirectiveLines.memzone,
            TestDirectiveLines.memory_zone_manager,
            TestDirectiveLines.isa_model
        )
        self.assertIsInstance(t1, PageAlignLine)
        t1.set_start_address(3)
        self.assertEqual(t1.address, 3)

        t2: LineObject = DirectiveLine.factory(
            1234,
            '.align 4',
            'page align',
            TestDirectiveLines.isa_model.endian,
            TestDirectiveLines.memzone,
            TestDirectiveLines.memory_zone_manager,
            TestDirectiveLines.isa_model
        )
        self.assertIsInstance(t2, PageAlignLine)
        t2.set_start_address(3)
        self.assertEqual(t2.address, 4)

        local_isa_model = copy.deepcopy(TestDirectiveLines.isa_model)
        local_isa_model._config['general']['page_size'] = 8
        t3: LineObject = DirectiveLine.factory(
            1234,
            '.align',
            'page align',
            TestDirectiveLines.isa_model.endian,
            TestDirectiveLines.memzone,
            TestDirectiveLines.memory_zone_manager,
            local_isa_model
        )
        self.assertIsInstance(t3, PageAlignLine)
        t3.set_start_address(3)
        self.assertEqual(t3.address, 8)

        # test using an expression for the page size
        label_values = GlobalLabelScope(['a', 'b', 'sp', 'mar'])
        label_values.set_label_value('eight', 8, LineIdentifier(1))
        t4: LineObject = DirectiveLine.factory(
            1234,
            '.align (eight >> 1)',
            'page align',
            TestDirectiveLines.isa_model.endian,
            TestDirectiveLines.memzone,
            TestDirectiveLines.memory_zone_manager,
            local_isa_model
        )
        t4.label_scope = label_values
        self.assertIsInstance(t4, PageAlignLine)
        t4.set_start_address(3)
        self.assertEqual(t4.address, 4)


if __name__ == '__main__':
    unittest.main()
