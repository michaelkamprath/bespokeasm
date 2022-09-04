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
        with pkg_resources.path(config_files, 'test_memory_zones.yaml') as fp:
            isa_model = AssemblerModel(str(fp), 0)
        label_scope = GlobalLabelScope(isa_model.registers)
        memzone_manager = MemoryZoneManager(isa_model.address_size, isa_model.default_origin, isa_model.predefined_memory_zones)

        with pkg_resources.path(test_code, 'test_memory_zones.asm') as asm_fp:
            asm_obj = AssemblyFile(asm_fp, label_scope)

            line_objs = asm_obj.load_line_objects(
                isa_model,
                [],
                memzone_manager,
                3,
            )

        self.assertEqual(len(line_objs), 9, '9 code lines')
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