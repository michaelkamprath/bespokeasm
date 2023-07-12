from collections import defaultdict
import unittest
import importlib.resources as pkg_resources
from bespokeasm.assembler.assembly_file import AssemblyFile
from bespokeasm.assembler.line_object import LineObject
from bespokeasm.assembler.line_object.instruction_line import InstructionLine

from test import config_files
from test import test_code

from bespokeasm.assembler.label_scope import LabelScope, LabelScopeType, GlobalLabelScope
from bespokeasm.assembler.line_identifier import LineIdentifier
from bespokeasm.assembler.memory_zone.manager import MemoryZoneManager
from bespokeasm.assembler.model import AssemblerModel
from bespokeasm.assembler.preprocessor import Preprocessor


class TestLabelScope(unittest.TestCase):
    def setUp(self):
        InstructionLine._INSTRUCTUION_EXTRACTION_PATTERN = None

    def test_single_layer_scope(self):
        ls1 = GlobalLabelScope(set())

        ls1.set_label_value('test1', 12, 777)
        ls1.set_label_value('test2', 42, 888)

        self.assertEqual(ls1.get_label_value('test1', 1), 12)
        self.assertEqual(ls1.get_label_value('test2', 2), 42)
        self.assertIsNone(ls1.get_label_value('undef', 3), 'should not find undefined label')

        with self.assertRaises(SystemExit, msg='label cannot be defined multiple times'):
            ls1.set_label_value('test1', 666, 1234)

    def test_multilayer_scopes(self):
        ls1 = GlobalLabelScope(set())
        ls2 = LabelScope(LabelScopeType.FILE, ls1, 'mycode.py')
        ls3 = LabelScope(LabelScopeType.LOCAL, ls2, 'my_label')
        ls4 = LabelScope(LabelScopeType.LOCAL, ls2, 'your_label')

        ls3.set_label_value('global1', 12, 1)
        ls3.set_label_value('_file1', 24, 2)
        ls3.set_label_value('.local1', 44, 3)
        ls4.set_label_value('global2', 13, 4)
        ls4.set_label_value('_file2', 14, 5)
        ls4.set_label_value('.local2', 88, 6)
        ls2.set_label_value('_file3', 66, 7)
        ls1.set_label_value('_required_global', 77, 8, scope=LabelScopeType.GLOBAL)

        self.assertEqual(ls3.get_label_value('global1', 1), 12)
        self.assertEqual(ls2.get_label_value('global1', 2), 12)
        self.assertEqual(ls1.get_label_value('global1', 3), 12)

        self.assertEqual(ls3.get_label_value('_file1', 4), 24)
        self.assertEqual(ls2.get_label_value('_file1', 5), 24)
        self.assertIsNone(ls1.get_label_value('_file1', 6), msg='label not at global scope')

        self.assertEqual(ls3.get_label_value('.local1', 7), 44)
        self.assertIsNone(ls2.get_label_value('.local1', 8), msg='label not at file scope')
        self.assertIsNone(ls1.get_label_value('.local1', 9), msg='label not at global scope')
        self.assertIsNone(ls3.get_label_value('.local2', 10), msg='label not this local scope')

        self.assertEqual(ls4.get_label_value('global1', 11), 12, 'global value vailable at other locals')
        self.assertEqual(ls4.get_label_value('_file1', 12), 24, 'file value vailable at other locals')
        self.assertEqual(ls3.get_label_value('_file2', 13), 14, 'file value vailable at other locals')

        self.assertEqual(
            ls1.get_label_value(
                '_required_global',
                LineIdentifier(14, 'test_multilayer_scopes')
            ),
            77,
            'global scope value'
        )
        self.assertEqual(
            ls3.get_label_value(
                '_required_global',
                LineIdentifier(15, 'test_multilayer_scopes')
            ),
            77,
            'global scope value'
        )

    def test_illegal_labels(self):
        global_scope = GlobalLabelScope({'a', 'b'})
        file_scope = LabelScope(LabelScopeType.FILE, global_scope, 'mycode.py')
        local_scope = LabelScope(LabelScopeType.LOCAL, file_scope, 'my_label')
        lineid = LineIdentifier(42, 'test_illegal_labels')

        local_scope.set_label_value('var1', 12, lineid)
        self.assertEqual(local_scope.get_label_value('var1', lineid), 12)

        # keywords as substrings are OK
        local_scope.set_label_value('zerountilnow', 13, lineid)
        self.assertEqual(local_scope.get_label_value('zerountilnow', lineid), 13)

        with self.assertRaises(SystemExit, msg='register labels cannot have values'):
            local_scope.get_label_value('a', 101)

        with self.assertRaises(SystemExit, msg='labels cannot be system keywords - local'):
            local_scope.set_label_value('.cstr', 666, lineid)
        with self.assertRaises(SystemExit, msg='labels cannot be system keywords - file'):
            file_scope.set_label_value('_cstr', 666, lineid)
        with self.assertRaises(SystemExit, msg='labels cannot be system keywords - file with local label'):
            file_scope.set_label_value('.cstr', 666, lineid)
        with self.assertRaises(SystemExit, msg='labels cannot be system keywords - file with local label'):
            local_scope.set_label_value('zero', 666, lineid)

    def test_line_object_scope_assignment(self):
        fp = pkg_resources.files(config_files).joinpath('test_memory_zones.yaml')
        isa_model = AssemblerModel(str(fp), 0)
        label_scope = GlobalLabelScope(isa_model.registers)
        memzone_manager = MemoryZoneManager(
            isa_model.address_size,
            isa_model.default_origin,
            isa_model.predefined_memory_zones
        )
        preprocessor = Preprocessor()

        asm_fp = pkg_resources.files(test_code).joinpath('test_line_object_scope_assignment.asm')
        asm_obj = AssemblyFile(asm_fp, label_scope)

        try:
            line_objs: list[LineObject] = asm_obj.load_line_objects(
                isa_model,
                [],
                memzone_manager,
                preprocessor,
                3,
            )
        except SystemExit:
            print(isa_model)
            print(f'  instructions = {isa_model.instructions}')
            raise

        # ensure file was assembled as expected
        self.assertEqual(len(line_objs), 13, '13 code lines')
        # the memzone manager should have created memzone
        self.assertIsNotNone(memzone_manager.zone('zone1'), 'zone1 memory zone should exist')
        # label scope should have 1 file and 3 local scopes assigned to lines
        label_scope_dict: dict[LabelScopeType, set[LabelScope]] = defaultdict(set)
        for lo in line_objs:
            label_scope_dict[lo.label_scope.type].add(lo.label_scope)
        self.assertEqual(len(label_scope_dict[LabelScopeType.GLOBAL]), 0, '0 global label scope assigned to lines')
        self.assertEqual(len(label_scope_dict[LabelScopeType.FILE]), 1, '1 file label scope')
        self.assertEqual(len(label_scope_dict[LabelScopeType.LOCAL]), 3, '3 local label scopes')
        # validate each line's label scope
        self.assertEqual(line_objs[0].label_scope.type, LabelScopeType.FILE)
        self.assertEqual(line_objs[1].label_scope.type, LabelScopeType.FILE)
        self.assertEqual(line_objs[2].label_scope.type, LabelScopeType.LOCAL)
        self.assertEqual(line_objs[2].label_scope.reference, 'label1')
        self.assertEqual(line_objs[3].label_scope.type, LabelScopeType.LOCAL)
        self.assertEqual(line_objs[3].label_scope.reference, 'label1')
        self.assertEqual(line_objs[4].label_scope.type, LabelScopeType.LOCAL)
        self.assertEqual(line_objs[4].label_scope.reference, 'label1')
        self.assertEqual(line_objs[5].label_scope.type, LabelScopeType.LOCAL)
        self.assertEqual(line_objs[5].label_scope.reference, 'label2')
        self.assertEqual(line_objs[6].label_scope.type, LabelScopeType.LOCAL)
        self.assertEqual(line_objs[6].label_scope.reference, 'label2')
        self.assertEqual(line_objs[7].label_scope.type, LabelScopeType.FILE, '.org should reset label scope to FILE')
        self.assertEqual(line_objs[8].label_scope.type, LabelScopeType.FILE)
        self.assertEqual(line_objs[9].label_scope.type, LabelScopeType.LOCAL)
        self.assertEqual(line_objs[9].label_scope.reference, 'label3')
        self.assertEqual(line_objs[10].label_scope.type, LabelScopeType.LOCAL)
        self.assertEqual(line_objs[10].label_scope.reference, 'label3')
        self.assertEqual(line_objs[11].label_scope.type, LabelScopeType.FILE, '.memzone should reset label scope to FILE')
        self.assertEqual(line_objs[12].label_scope.type, LabelScopeType.FILE)
