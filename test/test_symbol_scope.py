import importlib.resources as pkg_resources
import os
import tempfile
import unittest
from collections import defaultdict

from bespokeasm.assembler.assembly_file import AssemblyFile
from bespokeasm.assembler.diagnostic_reporter import DiagnosticReporter
from bespokeasm.assembler.engine import Assembler
from bespokeasm.assembler.line_identifier import LineIdentifier
from bespokeasm.assembler.line_object import LineObject
from bespokeasm.assembler.line_object.instruction_line import InstructionLine
from bespokeasm.assembler.memory_zone.manager import MemoryZoneManager
from bespokeasm.assembler.model import AssemblerModel
from bespokeasm.assembler.preprocessor import Preprocessor
from bespokeasm.assembler.symbol_scope import GlobalSymbolScope
from bespokeasm.assembler.symbol_scope import SymbolScope
from bespokeasm.assembler.symbol_scope import SymbolScopeType
from bespokeasm.assembler.symbol_scope.flow_symbols import CounterCoordinate
from bespokeasm.assembler.symbol_scope.named_scope_manager import NamedScopeManager

from test import config_files
from test import test_code


class TestSymbolScope(unittest.TestCase):
    def setUp(self):
        InstructionLine._INSTRUCTUION_EXTRACTION_PATTERN = None
        self.diagnostic_reporter = DiagnosticReporter()

    def test_single_layer_scope(self):
        ls1 = GlobalSymbolScope(set())

        ls1.set_label_value('test1', 12, 777)
        ls1.set_label_value('test2', 42, 888)

        self.assertEqual(ls1.get_label_value('test1', 1), 12)
        self.assertEqual(ls1.get_label_value('test2', 2), 42)
        self.assertIsNone(ls1.get_label_value('undef', 3), 'should not find undefined label')

        with self.assertRaises(SystemExit, msg='label cannot be defined multiple times'):
            ls1.set_label_value('test1', 666, 1234)

    def test_symbol_kinds_share_duplicate_definition_namespace(self):
        line_id = LineIdentifier(1, 'symbols.asm')
        coordinate = CounterCoordinate(
            label='slot',
            value=0,
            counter_name='stack',
            counter_instance_id=0,
            declared_offset=1,
            line_id=line_id,
        )
        coordinate_first = GlobalSymbolScope(set())
        coordinate_first.set_counter_coordinate(coordinate)
        with self.assertRaises(SystemExit, msg='label cannot shadow a coordinate'):
            coordinate_first.set_label_value('slot', 1, line_id)

        label_first = GlobalSymbolScope(set())
        label_first.set_label_value('slot', 1, line_id)
        with self.assertRaises(ValueError, msg='coordinate cannot shadow a label'):
            label_first.set_counter_coordinate(coordinate)

    def test_multilayer_scopes(self):
        ls1 = GlobalSymbolScope(set())
        ls2 = SymbolScope(SymbolScopeType.FILE, ls1, 'mycode.py')
        ls3 = SymbolScope(SymbolScopeType.LOCAL, ls2, 'my_label')
        ls4 = SymbolScope(SymbolScopeType.LOCAL, ls2, 'your_label')

        ls3.set_label_value('global1', 12, 1)
        ls3.set_label_value('_file1', 24, 2)
        ls3.set_label_value('.local1', 44, 3)
        ls4.set_label_value('global2', 13, 4)
        ls4.set_label_value('_file2', 14, 5)
        ls4.set_label_value('.local2', 88, 6)
        ls2.set_label_value('_file3', 66, 7)
        ls1.set_label_value('_required_global', 77, 8, scope=SymbolScopeType.GLOBAL)

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
        global_scope = GlobalSymbolScope({'a', 'b'})
        file_scope = SymbolScope(SymbolScopeType.FILE, global_scope, 'mycode.py')
        local_scope = SymbolScope(SymbolScopeType.LOCAL, file_scope, 'my_label')
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
        isa_model = AssemblerModel(str(fp), 0, self.diagnostic_reporter)
        symbol_scope = GlobalSymbolScope(isa_model.registers)
        memzone_manager = MemoryZoneManager(
            isa_model.address_size,
            isa_model.default_origin,
            isa_model.predefined_memory_zones
        )
        preprocessor = Preprocessor(diagnostic_reporter=self.diagnostic_reporter)
        named_scope_manager = NamedScopeManager(self.diagnostic_reporter)
        asm_fp = pkg_resources.files(test_code).joinpath('test_line_object_scope_assignment.asm')
        asm_obj = AssemblyFile(asm_fp, symbol_scope, named_scope_manager, named_scope_manager.diagnostic_reporter)

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
        symbol_scope_dict: dict[SymbolScopeType, set[SymbolScope]] = defaultdict(set)
        for lo in line_objs:
            symbol_scope_dict[lo.symbol_scope.type].add(lo.symbol_scope)
        self.assertEqual(len(symbol_scope_dict[SymbolScopeType.GLOBAL]), 0, '0 global label scope assigned to lines')
        self.assertEqual(len(symbol_scope_dict[SymbolScopeType.FILE]), 1, '1 file label scope')
        self.assertEqual(len(symbol_scope_dict[SymbolScopeType.LOCAL]), 3, '3 local label scopes')
        # validate each line's label scope
        self.assertEqual(line_objs[0].symbol_scope.type, SymbolScopeType.FILE)
        self.assertEqual(line_objs[1].symbol_scope.type, SymbolScopeType.FILE)
        self.assertEqual(line_objs[2].symbol_scope.type, SymbolScopeType.LOCAL)
        self.assertEqual(line_objs[2].symbol_scope.reference, 'label1')
        self.assertEqual(line_objs[3].symbol_scope.type, SymbolScopeType.LOCAL)
        self.assertEqual(line_objs[3].symbol_scope.reference, 'label1')
        self.assertEqual(line_objs[4].symbol_scope.type, SymbolScopeType.LOCAL)
        self.assertEqual(line_objs[4].symbol_scope.reference, 'label1')
        self.assertEqual(line_objs[5].symbol_scope.type, SymbolScopeType.LOCAL)
        self.assertEqual(line_objs[5].symbol_scope.reference, 'label2')
        self.assertEqual(line_objs[6].symbol_scope.type, SymbolScopeType.LOCAL)
        self.assertEqual(line_objs[6].symbol_scope.reference, 'label2')
        self.assertEqual(line_objs[7].symbol_scope.type, SymbolScopeType.FILE, '.org should reset label scope to FILE')
        self.assertEqual(line_objs[8].symbol_scope.type, SymbolScopeType.FILE)
        self.assertEqual(line_objs[9].symbol_scope.type, SymbolScopeType.LOCAL)
        self.assertEqual(line_objs[9].symbol_scope.reference, 'label3')
        self.assertEqual(line_objs[10].symbol_scope.type, SymbolScopeType.LOCAL)
        self.assertEqual(line_objs[10].symbol_scope.reference, 'label3')
        self.assertEqual(line_objs[11].symbol_scope.type, SymbolScopeType.FILE, '.memzone should reset label scope to FILE')
        self.assertEqual(line_objs[12].symbol_scope.type, SymbolScopeType.FILE)

    def test_local_label_before_any_non_local_is_error(self):
        """Doc: Labels > Label Scope > Local - locals cannot appear before first non-local label."""
        fp = pkg_resources.files(config_files).joinpath('test_instruction_operands.yaml')
        config_path = str(fp)
        asm_source = '\n'.join([
            '.local_only:',
            '  .byte 1',
        ])
        with tempfile.TemporaryDirectory() as temp_dir:
            asm_path = os.path.join(temp_dir, 'locals_first.asm')
            with open(asm_path, 'w') as handle:
                handle.write(asm_source)

            assembler = Assembler(
                source_file=asm_path,
                config_file=config_path,
                generate_binary=False,
                output_file=None,
                binary_start=None,
                binary_end=None,
                binary_fill_value=0,
                enable_pretty_print=False,
                pretty_print_format=None,
                pretty_print_output=None,
                is_verbose=0,
                include_paths=[temp_dir],
                predefined=[],
            )
            with self.assertRaises(SystemExit) as ctx:
                assembler.assemble_bytecode()
            self.assertIn('low of scope', str(ctx.exception))

    def test_local_label_after_org_is_error(self):
        """Doc: Labels > Label Scope > Local - locals cannot appear between .org and next non-local label."""
        fp = pkg_resources.files(config_files).joinpath('test_instruction_operands.yaml')
        config_path = str(fp)
        asm_source = '\n'.join([
            'start:',
            '  .byte 1',
            '.org $10',
            '.local_after_org:',
            '  .byte 2',
            'next:',
            '  .byte 3',
        ])
        with tempfile.TemporaryDirectory() as temp_dir:
            asm_path = os.path.join(temp_dir, 'locals_after_org.asm')
            with open(asm_path, 'w') as handle:
                handle.write(asm_source)

            assembler = Assembler(
                source_file=asm_path,
                config_file=config_path,
                generate_binary=False,
                output_file=None,
                binary_start=None,
                binary_end=None,
                binary_fill_value=0,
                enable_pretty_print=False,
                pretty_print_format=None,
                pretty_print_output=None,
                is_verbose=0,
                include_paths=[temp_dir],
                predefined=[],
            )
            with self.assertRaises(SystemExit) as ctx:
                assembler.assemble_bytecode()
            self.assertIn('low of scope', str(ctx.exception))
