import contextlib
import importlib.resources as pkg_resources
import io
import os
import tempfile
import unittest

from bespokeasm.assembler.engine import Assembler
from bespokeasm.assembler.line_object.instruction_line import InstructionLine

from test import config_files


class TestGeneralWarnings(unittest.TestCase):
    def setUp(self):
        InstructionLine.reset_instruction_pattern_cache()
        self.config_file = str(pkg_resources.files(config_files).joinpath('test_instruction_operands.yaml'))

    def _run_assembler(self, temp_dir: str, asm_source: str) -> str:
        asm_path = os.path.join(temp_dir, 'test.asm')
        with open(asm_path, 'w') as handle:
            handle.write(asm_source)

        assembler = Assembler(
            source_file=asm_path,
            config_file=self.config_file,
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

        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            assembler.assemble_bytecode()
        return stderr.getvalue()

    def test_warns_on_unmute_without_active_mute(self):
        asm_source = '\n'.join([
            '#unmute',
            'ld a, b, c',
        ])
        with tempfile.TemporaryDirectory() as temp_dir:
            output = self._run_assembler(temp_dir, asm_source)
            self.assertIn('#unmute has no effect', output)

    def test_warns_on_unbalanced_mute_at_eof(self):
        asm_source = '\n'.join([
            '#mute',
            'ld a, b, c',
        ])
        with tempfile.TemporaryDirectory() as temp_dir:
            output = self._run_assembler(temp_dir, asm_source)
            self.assertIn('File ended while muted', output)

    def test_warns_on_org_without_memzone_in_non_global(self):
        asm_source = '\n'.join([
            '#create_memzone zone1 $200 $2FF',
            '.memzone zone1',
            '.org $10',
            'ld a, b, c',
        ])
        with tempfile.TemporaryDirectory() as temp_dir:
            output = self._run_assembler(temp_dir, asm_source)
            self.assertIn('.org without a memzone name uses an absolute address', output)
            self.assertIn('zone1', output)

    def test_warns_on_zerountil_noop(self):
        asm_source = '\n'.join([
            '.org $10',
            '.zerountil $0',
            'ld a, b, c',
        ])
        with tempfile.TemporaryDirectory() as temp_dir:
            output = self._run_assembler(temp_dir, asm_source)
            self.assertIn('.zerountil target address is before the current address', output)

    def test_warns_on_data_truncation(self):
        asm_source = '\n'.join([
            '.byte $1FF',
            'ld a, b, c',
        ])
        with tempfile.TemporaryDirectory() as temp_dir:
            output = self._run_assembler(temp_dir, asm_source)
            self.assertIn('Data value', output)
            self.assertIn('truncated', output)


if __name__ == '__main__':
    unittest.main()
