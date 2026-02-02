import importlib.resources as pkg_resources
import unittest

from bespokeasm.assembler.assembly_file import AssemblyFile
from bespokeasm.assembler.diagnostic_reporter import DiagnosticReporter
from bespokeasm.assembler.label_scope import GlobalLabelScope
from bespokeasm.assembler.label_scope.named_scope_manager import NamedScopeManager
from bespokeasm.assembler.line_identifier import LineIdentifier
from bespokeasm.assembler.memory_zone.manager import MemoryZoneManager
from bespokeasm.assembler.model import AssemblerModel
from bespokeasm.assembler.preprocessor import Preprocessor

from test import config_files
from test import test_code


class TestPreprocessorError(unittest.TestCase):
    def setUp(self):
        self.diagnostic_reporter = DiagnosticReporter()

    def _load_file(self, asm_filename: str):
        fp = pkg_resources.files(config_files).joinpath('test_compilation_control.yaml')
        isa_model = AssemblerModel(str(fp), 0, self.diagnostic_reporter)
        memzone_mngr = MemoryZoneManager(
            isa_model.address_size,
            isa_model.default_origin,
            isa_model.predefined_memory_zones,
        )
        label_scope = GlobalLabelScope(isa_model.registers)
        preprocessor = Preprocessor(diagnostic_reporter=self.diagnostic_reporter)
        named_scope_manager = NamedScopeManager(self.diagnostic_reporter)

        asm_fp = pkg_resources.files(test_code).joinpath(asm_filename)
        asm_obj = AssemblyFile(asm_fp, label_scope, named_scope_manager, named_scope_manager.diagnostic_reporter)

        return asm_obj.load_line_objects(
            isa_model,
            [],
            memzone_mngr,
            preprocessor,
            0,
        )

    def test_error_basic_raises_and_prints(self):
        asm_fp = pkg_resources.files(test_code).joinpath('test_preprocessor_error_basic.asm')
        line_id = LineIdentifier(1, str(asm_fp))
        with self.assertRaises(SystemExit) as ctx:
            self._load_file('test_preprocessor_error_basic.asm')
        msg = str(ctx.exception)
        expected_prefix = f'ERROR: {line_id} - '
        self.assertTrue(msg.startswith(expected_prefix), 'error prefix should include line info')
        self.assertIn('boom', msg, 'message should be included')

    def test_error_default_message(self):
        asm_fp = pkg_resources.files(test_code).joinpath('test_preprocessor_error_default.asm')
        line_id = LineIdentifier(1, str(asm_fp))
        with self.assertRaises(SystemExit) as ctx:
            self._load_file('test_preprocessor_error_default.asm')
        msg = str(ctx.exception)
        expected_prefix = f'ERROR: {line_id} - '
        self.assertTrue(msg.startswith(expected_prefix), 'error prefix should include line info')
        self.assertIn('encountered error directive', msg)

    def test_error_suppressed_in_false_condition(self):
        self._load_file('test_preprocessor_error_inactive.asm')


if __name__ == '__main__':
    unittest.main()
