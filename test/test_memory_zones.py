import importlib.resources as pkg_resources
import os
import tempfile
import unittest

from bespokeasm.assembler.assembly_file import AssemblyFile
from bespokeasm.assembler.diagnostic_reporter import DiagnosticReporter
from bespokeasm.assembler.label_scope import GlobalLabelScope
from bespokeasm.assembler.label_scope.named_scope_manager import NamedScopeManager
from bespokeasm.assembler.line_object.instruction_line import InstructionLine
from bespokeasm.assembler.memory_zone import MemoryZone
from bespokeasm.assembler.memory_zone.manager import MemoryZoneManager
from bespokeasm.assembler.model import AssemblerModel
from bespokeasm.assembler.preprocessor import Preprocessor

from test import config_files
from test import test_code


class TestMemoryZones(unittest.TestCase):
    def setUp(self):
        InstructionLine.reset_instruction_pattern_cache()
        self.diagnostic_reporter = DiagnosticReporter()

    def test_memory_zone_obj(self):
        z1 = MemoryZone(16, 0, 0x7FFF, 'test_zone_1')
        self.assertEqual(z1.current_address, 0, 'starting address should be zero')
        self.assertEqual(z1.end, 0x7FFF, 'end address should be correct')

    def test_memory_zone_creation(self):
        fp = pkg_resources.files(config_files).joinpath('test_memory_zones.yaml')
        isa_model = AssemblerModel(str(fp), 0, self.diagnostic_reporter)
        label_scope = GlobalLabelScope(isa_model.registers)
        memzone_manager = MemoryZoneManager(
            isa_model.address_size,
            isa_model.default_origin,
            isa_model.predefined_memory_zones
        )
        preprocessor = Preprocessor(diagnostic_reporter=self.diagnostic_reporter)
        named_scope_manager = NamedScopeManager(self.diagnostic_reporter)
        self.assertEqual(memzone_manager.global_zone.start, 0x0100, 'global zone starts at $0100')
        self.assertEqual(memzone_manager.global_zone.end, 0xDFFF, 'global zone ends at $DFFF')

        asm_fp = pkg_resources.files(test_code).joinpath('test_memory_zones.asm')
        asm_obj = AssemblyFile(asm_fp, label_scope, named_scope_manager, named_scope_manager.diagnostic_reporter)

        line_objs = asm_obj.load_line_objects(
            isa_model,
            [],
            memzone_manager,
            preprocessor,
            3,
        )

        self.assertEqual(len(line_objs), 10, '10 code lines')
        self.assertIsNotNone(memzone_manager.zone('variables'), 'variables memory zone should exist')
        self.assertEqual(memzone_manager.zone('variables').start, 0x3000, 'memory zone starts at $3000')
        self.assertEqual(memzone_manager.zone('variables').end, 0x47FF, 'memory zone starts at $3000')
        self.assertEqual(line_objs[-1].memory_zone, memzone_manager.global_zone, 'last line is in Global memory zone')
        self.assertEqual(line_objs[4].memory_zone, memzone_manager.zone('variables'), 'byte is in variables memory zone')

        # test predefined zones
        self.assertIsNotNone(memzone_manager.zone('predefined_zone'), 'predefined_zone memory zone should exist')
        self.assertEqual(memzone_manager.zone('predefined_zone').start, 0x2000, 'memory zone starts at $2000')
        self.assertEqual(memzone_manager.zone('predefined_zone').end, 0x2FFF, 'memory zone starts at $2fff')
        # note that the current address property of the memory zone isn't updated yet because AssemblyFile
        # does not set the line object addresses.
        self.assertEqual(memzone_manager.zone('predefined_zone').current_address, 0x2000, 'current address')

    def test_invalid_memory_zones(self):
        fp = pkg_resources.files(config_files).joinpath('test_memory_zones.yaml')
        isa_model = AssemblerModel(str(fp), 0, self.diagnostic_reporter)
        memzone_manager = MemoryZoneManager(
            isa_model.address_size,
            isa_model.default_origin,
            isa_model.predefined_memory_zones
        )

        with self.assertRaises(ValueError, msg='Zone start must be in GLOBAL'):
            memzone_manager.create_zone(16, 0, 0x3000, 'invalid_start')

        with self.assertRaises(ValueError, msg='Zone end must be in GLOBAL'):
            memzone_manager.create_zone(16, 0x1000, 0xF000, 'invalid_end')

        with self.assertRaises(ValueError, msg='Zone end must be greater than zone start'):
            memzone_manager.create_zone(16, 0x2000, 0x1000, 'inverted')

    def test_include_resets_memzone_to_global(self):
        """Doc: Memory Zones > Memory Zone Scope - included files compile into GLOBAL and caller memzone resumes."""
        fp = pkg_resources.files(config_files).joinpath('test_memory_zones.yaml')
        isa_model = AssemblerModel(str(fp), 0, self.diagnostic_reporter)
        label_scope = GlobalLabelScope(isa_model.registers)
        memzone_manager = MemoryZoneManager(
            isa_model.address_size,
            isa_model.default_origin,
            isa_model.predefined_memory_zones
        )
        preprocessor = Preprocessor(diagnostic_reporter=self.diagnostic_reporter)
        named_scope_manager = NamedScopeManager(self.diagnostic_reporter)

        main_source = '\n'.join([
            '#create_memzone variables $3000 $47FF',
            '.memzone variables',
            'main_label: .byte 1',
            '#include "included.asm"',
            'after_include: .byte 2',
        ])
        include_source = 'included_label: .byte 3\n'

        with tempfile.TemporaryDirectory() as temp_dir:
            main_path = os.path.join(temp_dir, 'main.asm')
            include_path = os.path.join(temp_dir, 'included.asm')
            with open(main_path, 'w') as handle:
                handle.write(main_source)
            with open(include_path, 'w') as handle:
                handle.write(include_source)

            asm_obj = AssemblyFile(main_path, label_scope, named_scope_manager, named_scope_manager.diagnostic_reporter)
            line_objs = asm_obj.load_line_objects(
                isa_model,
                {temp_dir},
                memzone_manager,
                preprocessor,
                0,
            )

            included_lines = [lo for lo in line_objs if lo.line_id.filename == include_path]
            self.assertTrue(included_lines, 'included file should produce line objects')
            for lobj in included_lines:
                self.assertEqual(
                    lobj.memory_zone,
                    memzone_manager.global_zone,
                    'included file should default to GLOBAL memory zone',
                )

            after_include_lines = [
                lo for lo in line_objs
                if lo.line_id.filename == main_path and lo.line_id.line_num == 5
            ]
            self.assertEqual(len(after_include_lines), 2, 'main file line after include should exist')
            for lobj in after_include_lines:
                self.assertEqual(
                    lobj.memory_zone,
                    memzone_manager.zone('variables'),
                    'caller memzone should remain active after include',
                )
