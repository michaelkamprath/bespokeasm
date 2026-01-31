import contextlib
import importlib.resources as pkg_resources
import io
import os
import tempfile
import unittest

from bespokeasm.assembler.engine import Assembler
from bespokeasm.assembler.line_object.instruction_line import InstructionLine

from test import config_files


class TestNamedScopeWarnings(unittest.TestCase):
    def setUp(self):
        InstructionLine.reset_instruction_pattern_cache()
        self.config_file = str(pkg_resources.files(config_files).joinpath('test_instruction_operands.yaml'))

    def test_warns_when_scope_not_defined_in_file_or_includes(self):
        asm_source = '\n'.join([
            '#use-scope "missing_scope"',
            'ld a, b, c',
        ])
        with tempfile.TemporaryDirectory() as temp_dir:
            asm_path = os.path.join(temp_dir, 'missing_scope.asm')
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

            output = stderr.getvalue()
            self.assertIn('WARNING:', output)
            self.assertIn('missing_scope', output)
            self.assertIn(f'file {asm_path}, line 1', output)

    def test_no_warning_when_scope_defined_in_include(self):
        main_source = '\n'.join([
            '#use-scope "libscope"',
            '#include "lib.asm"',
            'ld a, b, c',
        ])
        include_source = '\n'.join([
            '#create-scope "libscope" prefix="lib_"',
            'lib_value: .byte 1',
        ])
        with tempfile.TemporaryDirectory() as temp_dir:
            main_path = os.path.join(temp_dir, 'main.asm')
            include_path = os.path.join(temp_dir, 'lib.asm')
            with open(main_path, 'w') as handle:
                handle.write(main_source)
            with open(include_path, 'w') as handle:
                handle.write(include_source)

            assembler = Assembler(
                source_file=main_path,
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

            self.assertEqual('', stderr.getvalue())

    def test_warnings_as_errors_raises(self):
        asm_source = '\n'.join([
            '#use-scope "missing_scope"',
            'ld a, b, c',
        ])
        with tempfile.TemporaryDirectory() as temp_dir:
            asm_path = os.path.join(temp_dir, 'missing_scope.asm')
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
                warnings_as_errors=True,
            )

            with self.assertRaises(SystemExit) as ctx:
                assembler.assemble_bytecode()

            self.assertIn('ERROR:', str(ctx.exception))
            self.assertIn('missing_scope', str(ctx.exception))

    def test_warns_on_deactivate_inactive_scope(self):
        asm_source = '\n'.join([
            '#deactivate-scope "inactive_scope"',
            'ld a, b, c',
        ])
        with tempfile.TemporaryDirectory() as temp_dir:
            asm_path = os.path.join(temp_dir, 'deactivate_inactive.asm')
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

            output = stderr.getvalue()
            self.assertIn('WARNING:', output)
            self.assertIn('not active', output)
            self.assertIn('inactive_scope', output)

    def test_warns_on_duplicate_use_scope_no_change(self):
        asm_source = '\n'.join([
            '#create-scope "dup_scope" prefix="dup_"',
            '#deactivate-scope "dup_scope"',
            '#use-scope "dup_scope"',
            '#use-scope "dup_scope"',
            'ld a, b, c',
        ])
        with tempfile.TemporaryDirectory() as temp_dir:
            asm_path = os.path.join(temp_dir, 'duplicate_use_scope.asm')
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

            output = stderr.getvalue()
            self.assertIn('WARNING:', output)
            self.assertIn('already active', output)
            self.assertIn('dup_scope', output)


if __name__ == '__main__':
    unittest.main()
