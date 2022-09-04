import unittest
import importlib.resources as pkg_resources

from test import config_files
from test import test_code

from bespokeasm.assembler.memory_zone import MemoryZone
from bespokeasm.assembler.memory_zone.manager import MemoryZoneManager
from bespokeasm.assembler.model import AssemblerModel
from bespokeasm.assembler.label_scope import GlobalLabelScope
from bespokeasm.assembler.assembly_file import AssemblyFile


class TestMemoryZones(unittest.TestCase):
    def setUp(self):
        pass

    def test_memory_zone_obj(self):
        z1 = MemoryZone(16, 0, 0x7FFF, 'test_zone_1')
        self.assertEqual(z1.current_address, 0, 'starting address should be zero')
        self.assertEqual(z1.end, 0x7FFF, 'end address should be correct')

    def test_memory_zone_creation(self):
        with pkg_resources.path(config_files, 'test_instruction_macros.yaml') as fp:
            isa_model = AssemblerModel(str(fp), 0)
        label_scope = GlobalLabelScope(isa_model.registers)
        memzone_manager = MemoryZoneManager(isa_model.address_size, isa_model.default_origin)

        with pkg_resources.path(test_code, 'test_memory_zones.asm') as asm_fp:
            asm_obj = AssemblyFile(asm_fp, label_scope)

            line_objs = asm_obj.load_line_objects(
                isa_model,
                [],
                memzone_manager,
                3,
            )

        self.assertEqual(len(line_objs), 8, 'Eight code lines')
        self.assertIsNotNone(memzone_manager.zone('variables'), 'variables memory zone should exist')
        self.assertEqual(memzone_manager.zone('variables').start, 0x3000, 'memory zone starts at $3000')
        self.assertEqual(memzone_manager.zone('variables').end, 0x47FF, 'memory zone starts at $3000')
        self.assertEqual(line_objs[-1].memory_zone, memzone_manager.global_zone, 'last line is in Global memory zone')
        self.assertEqual(line_objs[3].memory_zone, memzone_manager.zone('variables'), 'byte is in variables memory zone')

