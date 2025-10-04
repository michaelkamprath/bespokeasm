import importlib.resources as pkg_resources
import os
import shutil
import tempfile
import unittest

from bespokeasm.assembler.assembly_file import AssemblyFile
from bespokeasm.assembler.label_scope import LabelScopeType
from bespokeasm.assembler.label_scope.named_scope_manager import NamedScopeManager
from bespokeasm.assembler.line_object.instruction_line import InstructionLine
from bespokeasm.assembler.memory_zone.manager import MemoryZoneManager
from bespokeasm.assembler.model import AssemblerModel
from bespokeasm.assembler.preprocessor import Preprocessor

from test import config_files


class TestNamedScopeIsolation(unittest.TestCase):
    """Test proper isolation of named scope labels - they should only be accessible when scope is active."""

    def setUp(self):
        # Reset instruction pattern cache for test isolation
        InstructionLine.reset_instruction_pattern_cache()

        self.config_file = str(pkg_resources.files(config_files).joinpath('test_instruction_operands.yaml'))
        self.test_code_dir = os.path.join(tempfile.gettempdir(), 'test_code')
        os.makedirs(self.test_code_dir, exist_ok=True)

        # Create the assembler model
        self.isa_model = AssemblerModel(self.config_file, 0)

        # Create named scope manager
        self.named_scope_manager = NamedScopeManager()

        # Create global label scope with named scope manager
        self.global_scope = self.isa_model.global_label_scope

        # Create memory zone manager
        self.memzone_manager = MemoryZoneManager(
            self.isa_model.address_size,
            self.isa_model.default_origin,
            self.isa_model.predefined_memory_zones,
        )

        # Create preprocessor
        self.preprocessor = Preprocessor(self.isa_model.predefined_symbols)

    def tearDown(self):
        # Clean up temporary directory and all its contents
        if os.path.exists(self.test_code_dir):
            shutil.rmtree(self.test_code_dir)

    def test_named_scope_labels_should_be_isolated_when_scope_inactive(self):
        """Test that labels with named scope prefixes are not accessible when scope is not active."""

        # This test replicates the mandelbrot bug:
        # 1. Library defines a scope and labels with that scope's prefix
        # 2. Main file does NOT activate the scope
        # 3. Main file should NOT be able to access the scope's labels

        main_content = '''
; Main file that does NOT use the mathlib16 scope
; This should fail to resolve ml16_signed_multiply

; Comment out the use-scope directive to replicate the bug
; #use-scope "mathlib16"

; Include the library that defines the scope and its labels FIRST
; so that the labels exist when we try to use them
#include "temp_isolated_mathlib.asm"

; Try to use a function from the mathlib16 scope - this should FAIL
main_function: .byte 42

; This should fail because mathlib16 scope is not active in this file
; ml16_signed_multiply is defined with "ml16_" prefix in library
; Use .2byte directive to reference the label - this should cause scope isolation error
jmp ml16_signed_multiply

ld a, b, c
'''

        library_content = '''
; Library file that defines named scope and labels with scope prefix
#create-scope "mathlib16" prefix="ml16_"
#use-scope "mathlib16"

; This label has the ml16_ prefix and should only be accessible
; when the mathlib16 scope is active
ml16_signed_multiply: .byte 200

; This is a global label and should always be accessible
global_math_function: .byte 100

; this is a file local symbol
_file_local_label: .byte 10
'''

        # Write both files
        main_file = os.path.join(self.test_code_dir, 'temp_isolation_main.asm')
        lib_file = os.path.join(self.test_code_dir, 'temp_isolated_mathlib.asm')

        with open(main_file, 'w') as f:
            f.write(main_content)
        with open(lib_file, 'w') as f:
            f.write(library_content)

        # Create assembly file
        asm_file = AssemblyFile(main_file, self.global_scope, self.named_scope_manager)

        # Load line objects
        include_paths = {self.test_code_dir}

        # This should FAIL because ml16_signed_multiply should not be resolvable
        # when the mathlib16 scope is not active
        line_objects = asm_file.load_line_objects(
                self.isa_model,
                include_paths,
                self.memzone_manager,
                self.preprocessor,
                2  # log_verbosity
            )
        print('DEBUG - load_line_objects completed successfully')

        # Verify that the mathlib16 scope was properly created and used
        mathlib_def = self.named_scope_manager.get_scope_definition('mathlib16')
        self.assertIsNotNone(mathlib_def)
        self.assertEqual(mathlib_def.prefix, 'ml16_')

        for lobj in line_objects:
            # look for the `jmp` instruction
            if isinstance(lobj, InstructionLine) and lobj.instruction == 'jmp ml16_signed_multiply':
                # assert label scope is local and there are no active named scopes
                self.assertEqual(lobj.label_scope.type, LabelScopeType.LOCAL)
                self.assertEqual(lobj.active_named_scopes, [])

    def test_named_scope_labels_should_be_accessible_when_scope_active(self):
        """Test that labels with named scope prefixes ARE accessible when scope is active."""

        main_content = '''
; Main file that DOES use the mathlib16 scope
; This should succeed in resolving ml16_signed_multiply

; Activate the scope
#use-scope "mathlib16"

; Try to use a function from the mathlib16 scope - this should SUCCEED
main_function:
    adi 42

    ; This should work because mathlib16 scope is active
    jmp ml16_signed_multiply    ; Should resolve successfully

    adi 100

; Include the library that defines the scope and its labels
#include "temp_accessible_mathlib.asm"

ld a, b, c
'''

        library_content = '''
; Library file that defines named scope and labels with scope prefix
#create-scope "mathlib16" prefix="ml16_"
#use-scope "mathlib16"

; This label has the ml16_ prefix and should be accessible
; when the mathlib16 scope is active
ml16_signed_multiply: .byte 200

; This is a global label and should always be accessible
global_math_function: .byte 100

; this is a file local symbol
_file_local_label: .byte 10
'''

        # Write both files
        main_file = os.path.join(self.test_code_dir, 'temp_accessible_main.asm')
        lib_file = os.path.join(self.test_code_dir, 'temp_accessible_mathlib.asm')

        with open(main_file, 'w') as f:
            f.write(main_content)
        with open(lib_file, 'w') as f:
            f.write(library_content)

        # Create assembly file
        asm_file = AssemblyFile(main_file, self.global_scope, self.named_scope_manager)

        # Load line objects
        include_paths = {self.test_code_dir}

        # This should SUCCEED because ml16_signed_multiply should be resolvable
        # when the mathlib16 scope is active
        line_objects = asm_file.load_line_objects(
            self.isa_model,
            include_paths,
            self.memzone_manager,
            self.preprocessor,
            0  # log_verbosity
        )

        # Verify that the mathlib16 scope was properly created and used
        mathlib_def = self.named_scope_manager.get_scope_definition('mathlib16')
        self.assertIsNotNone(mathlib_def)
        self.assertEqual(mathlib_def.prefix, 'ml16_')

        # Verify the scope is active in the main file
        for lobj in line_objects:
            # look for the `jmp` instruction
            if isinstance(lobj, InstructionLine) and lobj.instruction == 'jmp ml16_signed_multiply':
                # assert label scope is local and there are no active named scopes
                self.assertEqual(lobj.label_scope.type, LabelScopeType.LOCAL)
                self.assertEqual(lobj.active_named_scopes, ['mathlib16'])


if __name__ == '__main__':
    unittest.main()
