import importlib.resources as pkg_resources
import os
import tempfile
import unittest

from bespokeasm.assembler.assembly_file import AssemblyFile
from bespokeasm.assembler.diagnostic_reporter import DiagnosticReporter
from bespokeasm.assembler.label_scope import GlobalLabelScope
from bespokeasm.assembler.label_scope.named_scope_manager import NamedScopeManager
from bespokeasm.assembler.line_object.instruction_line import InstructionLine
from bespokeasm.assembler.memory_zone.manager import MemoryZoneManager
from bespokeasm.assembler.model import AssemblerModel
from bespokeasm.assembler.preprocessor import Preprocessor

from test import config_files


class TestIncludePaths(unittest.TestCase):
    def setUp(self) -> None:
        InstructionLine.reset_instruction_pattern_cache()
        fp = pkg_resources.files(config_files).joinpath('test_instructions_with_variants.yaml')
        self.diagnostic_reporter = DiagnosticReporter()
        self.isa_model = AssemblerModel(str(fp), 0, self.diagnostic_reporter)
        self.named_scope_manager = NamedScopeManager(self.diagnostic_reporter)
        self.memzone_mngr = MemoryZoneManager(
            self.isa_model.address_size,
            self.isa_model.default_origin,
            self.isa_model.predefined_memory_zones,
        )
        self.global_scope = GlobalLabelScope(self.isa_model.registers)
        self.preprocessor = Preprocessor(diagnostic_reporter=self.diagnostic_reporter)

    def _load_line_objects(self, filename: str, include_paths: set[str]):
        asm_file = AssemblyFile(
            filename,
            self.global_scope,
            self.named_scope_manager,
            self.named_scope_manager.diagnostic_reporter,
        )
        return asm_file.load_line_objects(
            self.isa_model,
            include_paths,
            self.memzone_mngr,
            self.preprocessor,
            0,
        )

    def test_includes_resolve_relative_to_including_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            common_dir = os.path.join(temp_dir, 'common')
            os.makedirs(common_dir, exist_ok=True)

            memlib_path = os.path.join(common_dir, 'memlib.asm')
            with open(memlib_path, 'w') as handle:
                handle.write('nop\n')

            mathlib_path = os.path.join(common_dir, 'mathlib.asm')
            with open(mathlib_path, 'w') as handle:
                handle.write('#include "memlib.asm"\nmov a, 1\n')

            main_path = os.path.join(temp_dir, 'main.asm')
            with open(main_path, 'w') as handle:
                handle.write('#include "common/mathlib.asm"\n')

            line_objects = self._load_line_objects(main_path, {temp_dir})
            memlib_lines = [lo for lo in line_objects if lo.line_id.filename == memlib_path]
            self.assertTrue(memlib_lines, 'include should resolve to the current file directory')

    def test_includes_accept_dot_and_dotdot_segments(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            common_dir = os.path.join(temp_dir, 'common')
            shared_dir = os.path.join(temp_dir, 'shared')
            os.makedirs(common_dir, exist_ok=True)
            os.makedirs(shared_dir, exist_ok=True)

            util_path = os.path.join(shared_dir, 'util.asm')
            with open(util_path, 'w') as handle:
                handle.write('mov a, 1\n')

            mathlib_path = os.path.join(common_dir, 'mathlib.asm')
            with open(mathlib_path, 'w') as handle:
                handle.write('#include "../shared/./util.asm"\n')

            main_path = os.path.join(temp_dir, 'main.asm')
            with open(main_path, 'w') as handle:
                handle.write('#include "common/mathlib.asm"\n')

            line_objects = self._load_line_objects(main_path, {temp_dir})
            util_lines = [lo for lo in line_objects if lo.line_id.filename == util_path]
            self.assertTrue(util_lines, 'include should accept ../ and ./ segments')

    def test_includes_resolve_from_include_paths(self):
        with tempfile.TemporaryDirectory() as temp_dir, tempfile.TemporaryDirectory() as include_dir:
            lib_path = os.path.join(include_dir, 'lib.asm')
            with open(lib_path, 'w') as handle:
                handle.write('nop\n')

            main_path = os.path.join(temp_dir, 'main.asm')
            with open(main_path, 'w') as handle:
                handle.write('#include "lib.asm"\n')

            line_objects = self._load_line_objects(main_path, {include_dir})
            lib_lines = [lo for lo in line_objects if lo.line_id.filename == lib_path]
            self.assertTrue(lib_lines, 'include should resolve using include search paths')
