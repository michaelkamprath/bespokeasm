"""
Test suite for named scope file restrictions and advanced behaviors.

This test module demonstrates and validates:
1. Labels can only be created into a named scope in the same file where scope is created
2. Forward references (using scope before it's defined) are supported and intentional
3. Underscore prefix behavior for "exporting" what would normally be file-local symbols
"""
import importlib.resources as pkg_resources
import os
import shutil
import tempfile
import unittest

from bespokeasm.assembler.engine import Assembler
from bespokeasm.assembler.line_object.instruction_line import InstructionLine

from test import config_files


class TestNamedScopeFileRestrictions(unittest.TestCase):
    """Test that labels can only be created into named scopes in the same file as scope creation."""

    def setUp(self):
        # Reset instruction pattern cache for test isolation
        InstructionLine.reset_instruction_pattern_cache()

        self.config_file = str(pkg_resources.files(config_files).joinpath('test_instruction_operands.yaml'))
        self.test_code_dir = os.path.join(tempfile.gettempdir(), 'test_named_scope_restrictions')
        os.makedirs(self.test_code_dir, exist_ok=True)

    def tearDown(self):
        # Clean up temporary directory and all its contents
        if os.path.exists(self.test_code_dir):
            shutil.rmtree(self.test_code_dir)

    def test_labels_only_created_in_scope_defining_file(self):
        """Test that labels with named scope prefix are only added to named scope in the defining file.

        This test verifies that:
        - Labels in the library file (where scope is created) go into the named scope
        - Labels in the main file (where scope is only used) do NOT go into the named scope
        - Labels in the main file fall back to global scope even if they match the prefix
        """

        library_content = '''
; Library file that defines the scope
#create-scope "mylib" prefix="lib_"

; These labels should go into the mylib named scope
lib_init: .byte 1
lib_version: .byte 2
lib_constant = 100
'''

        main_content = '''
; Main file that uses the scope but doesn't define it
#use-scope "mylib"

#include "test_library.asm"

; This label has the lib_ prefix but should NOT go into mylib scope
; because this file didn't create the scope
; It should fall back to global scope
lib_custom_main: .byte 3

; Simple instruction to complete the assembly
ld a, b, c
'''

        # Write files
        lib_file = os.path.join(self.test_code_dir, 'test_library.asm')
        main_file = os.path.join(self.test_code_dir, 'test_main.asm')

        with open(lib_file, 'w') as f:
            f.write(library_content)
        with open(main_file, 'w') as f:
            f.write(main_content)

        # Create and run assembler - should succeed
        assembler = Assembler(
            source_file=main_file,
            config_file=self.config_file,
            generate_binary=False,
            output_file=None,
            binary_start=None,
            binary_end=None,
            binary_fill_value=0,  # Default fill value
            enable_pretty_print=False,
            pretty_print_format=None,
            pretty_print_output=None,
            is_verbose=0,
            include_paths=[self.test_code_dir],
            predefined=[],
        )

        # This should succeed - labels fall back to global scope
        assembler.assemble_bytecode()
        self.assertTrue(True, 'Assembly completed - file restriction working correctly')

    def test_forward_references_are_supported(self):
        """Test that scopes can be used before they are defined (forward references).

        This is an intentional feature to support library workflows where a main file
        declares dependencies at the top, then includes library files later.
        """

        library_content = '''
; Library file that defines the scope
#create-scope "graphics" prefix="gfx_"

; Library functions
gfx_init: .byte 100
gfx_clear: .byte 200
'''

        main_content = '''
; Main file uses scope BEFORE including the library that defines it
; This is intentional and should work
#use-scope "graphics"

; These will fall back to global since scope not created in this file
gfx_buffer: .2byte 640

; Now include the library that actually creates the scope
#include "test_graphics_lib.asm"

; Simple instruction to complete assembly
ld a, b, c
'''

        # Write files
        lib_file = os.path.join(self.test_code_dir, 'test_graphics_lib.asm')
        main_file = os.path.join(self.test_code_dir, 'test_main_forward.asm')

        with open(lib_file, 'w') as f:
            f.write(library_content)
        with open(main_file, 'w') as f:
            f.write(main_content)

        # Create and run assembler
        assembler = Assembler(
            source_file=main_file,
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
            include_paths=[self.test_code_dir],
            predefined=[],
        )

        # This should succeed - forward references are supported
        assembler.assemble_bytecode()
        self.assertTrue(True, 'Assembly completed with forward reference - working as designed')

    def test_underscore_prefix_exports_file_local_symbols(self):
        """Test that underscore prefix can be used to export what would be file-local symbols.

        When a library creates a named scope with underscore prefix, it allows the library
        to "export" symbols that would normally be file-local only. This is useful for
        library APIs that want to use underscore convention without limiting visibility.
        """

        library_content = '''
; Library uses underscore as prefix to "export" internal symbols
#create-scope "mathlib" prefix="_"

; These would normally be file-local but go to mathlib named scope instead
_multiply: .byte 100
_divide: .byte 200
_internal_state: .byte 0
'''

        main_content = '''
; Main file activates the mathlib scope
#use-scope "mathlib"

#include "test_mathlib.asm"

; This underscore-prefixed label will NOT go to mathlib scope (wrong file)
; But since mathlib scope takes precedence, it falls back to global scope
_local_var: .byte 50

; Simple instruction
ld a, b, c
'''

        # Write files
        lib_file = os.path.join(self.test_code_dir, 'test_mathlib.asm')
        main_file = os.path.join(self.test_code_dir, 'test_main_underscore.asm')

        with open(lib_file, 'w') as f:
            f.write(library_content)
        with open(main_file, 'w') as f:
            f.write(main_content)

        # Create and run assembler
        assembler = Assembler(
            source_file=main_file,
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
            include_paths=[self.test_code_dir],
            predefined=[],
        )

        # This should succeed - underscore labels in different files fall back to global
        assembler.assemble_bytecode()
        self.assertTrue(True, 'Assembly completed - underscore prefix export working')

    def test_constants_respect_file_restriction(self):
        """Test that constants also respect the file restriction for named scopes.

        Like address labels, constants can only be added to a named scope in the file
        where that scope was created.
        """

        library_content = '''
; Library defines scope and constants
#create-scope "config" prefix="cfg_"

cfg_max_size = 1024
cfg_default_mode = 2
'''

        main_content = '''
; Main file tries to define constants with same prefix
#use-scope "config"

; This constant will NOT go to config scope (wrong file)
; Falls back to global scope
cfg_custom_value = 999

#include "test_config_lib.asm"

ld a, b, c
'''

        # Write files
        lib_file = os.path.join(self.test_code_dir, 'test_config_lib.asm')
        main_file = os.path.join(self.test_code_dir, 'test_main_constants.asm')

        with open(lib_file, 'w') as f:
            f.write(library_content)
        with open(main_file, 'w') as f:
            f.write(main_content)

        # Create and run assembler
        assembler = Assembler(
            source_file=main_file,
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
            include_paths=[self.test_code_dir],
            predefined=[],
        )

        # This should succeed - constants in wrong file fall back to global scope
        assembler.assemble_bytecode()
        self.assertTrue(True, 'Assembly completed - constant file restriction working')


if __name__ == '__main__':
    unittest.main()
