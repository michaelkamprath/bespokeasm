import importlib.resources as pkg_resources
import os
import tempfile
import unittest

from bespokeasm.assembler.assembly_file import AssemblyFile
from bespokeasm.assembler.label_scope import GlobalLabelScope
from bespokeasm.assembler.memory_zone.manager import MemoryZoneManager
from bespokeasm.assembler.model import AssemblerModel
from bespokeasm.assembler.preprocessor import Preprocessor

from test import config_files


class TestConditionalInclude(unittest.TestCase):
    def setUp(self):
        # Use a simple test configuration
        fp = pkg_resources.files(config_files).joinpath('test_instructions_with_variants.yaml')
        self.isa_model = AssemblerModel(str(fp), 0)
        self.memzone_mngr = MemoryZoneManager(
            self.isa_model.address_size,
            self.isa_model.default_origin,
            self.isa_model.predefined_memory_zones,
        )
        self.global_scope = GlobalLabelScope(self.isa_model.registers)
        self.preprocessor = Preprocessor()

    def test_include_in_inactive_conditional_block_should_not_be_processed(self):
        """Test that #include directives inside inactive conditional blocks are not processed."""

        # Create temporary files for testing
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create an included file that would cause an error if processed
            included_file_content = """
; This file should not be processed when in an inactive conditional block
invalid_instruction_that_would_cause_error
"""
            included_file_path = os.path.join(temp_dir, 'included_file.asm')
            with open(included_file_path, 'w') as f:
                f.write(included_file_content)

            # Create main file with conditional include
            main_file_content = """
#define SHOULD_INCLUDE 0

#if SHOULD_INCLUDE
#include "included_file.asm"
#endif

nop ; This should work
"""
            main_file_path = os.path.join(temp_dir, 'main_file.asm')
            with open(main_file_path, 'w') as f:
                f.write(main_file_content)

            # Test that the assembly file loads without error
            # If #include is processed incorrectly, it would try to include the file
            # and fail on the invalid instruction
            asm_file = AssemblyFile(main_file_path, self.global_scope)
            include_paths = {temp_dir}

            # This should not raise an exception since the #include is in an inactive block
            line_objects = asm_file.load_line_objects(
                self.isa_model,
                include_paths,
                self.memzone_mngr,
                self.preprocessor,
                0  # log_verbosity
            )

            # The line objects should only contain the nop instruction and preprocessor directives
            # but not any content from the included file
            compilable_lines = [obj for obj in line_objects if obj.compilable]

            # Filter to only actual instructions (not preprocessor directives)
            instruction_lines = [obj for obj in compilable_lines
                                 if hasattr(obj, 'instruction') and
                                 not obj.instruction.startswith('#') and
                                 obj.instruction.strip() != '']

            # Should have exactly one instruction line: the nop instruction
            self.assertEqual(len(instruction_lines), 1)
            self.assertEqual(instruction_lines[0].instruction, 'nop')

    def test_include_in_active_conditional_block_should_be_processed(self):
        """Test that #include directives inside active conditional blocks are processed."""

        # Create temporary files for testing
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create an included file with valid content
            included_file_content = """
; This file should be processed when in an active conditional block
mov a, 1
"""
            included_file_path = os.path.join(temp_dir, 'included_file.asm')
            with open(included_file_path, 'w') as f:
                f.write(included_file_content)

            # Create main file with conditional include
            main_file_content = """
#define SHOULD_INCLUDE 1

#if SHOULD_INCLUDE
#include "included_file.asm"
#endif

nop ; This should also work
"""
            main_file_path = os.path.join(temp_dir, 'main_file.asm')
            with open(main_file_path, 'w') as f:
                f.write(main_file_content)

            # Test that the assembly file loads and includes the content
            asm_file = AssemblyFile(main_file_path, self.global_scope)
            include_paths = {temp_dir}

            line_objects = asm_file.load_line_objects(
                self.isa_model,
                include_paths,
                self.memzone_mngr,
                self.preprocessor,
                0  # log_verbosity
            )

            # The line objects should contain both the included mov instruction and the nop
            compilable_lines = [obj for obj in line_objects if obj.compilable]

            # Filter to only actual instructions (not preprocessor directives)
            instruction_lines = [obj for obj in compilable_lines
                                 if hasattr(obj, 'instruction') and
                                 not obj.instruction.startswith('#') and
                                 obj.instruction.strip() != '']

            # Should have exactly two instruction lines: mov and nop
            self.assertEqual(len(instruction_lines), 2)
            self.assertTrue(instruction_lines[0].instruction.startswith('mov'))
            self.assertEqual(instruction_lines[1].instruction, 'nop')

    def test_nested_conditional_include(self):
        """Test #include inside nested conditional blocks."""

        with tempfile.TemporaryDirectory() as temp_dir:
            # Create an included file
            included_file_content = """
add a, 1
"""
            included_file_path = os.path.join(temp_dir, 'nested_file.asm')
            with open(included_file_path, 'w') as f:
                f.write(included_file_content)

            # Create main file with nested conditionals
            main_file_content = """
#define OUTER_CONDITION 1
#define INNER_CONDITION 0

#if OUTER_CONDITION
    #if INNER_CONDITION
        #include "nested_file.asm"
    #endif
    mov a, 2
#endif

nop
"""
            main_file_path = os.path.join(temp_dir, 'main_file.asm')
            with open(main_file_path, 'w') as f:
                f.write(main_file_content)

            asm_file = AssemblyFile(main_file_path, self.global_scope)
            include_paths = {temp_dir}

            line_objects = asm_file.load_line_objects(
                self.isa_model,
                include_paths,
                self.memzone_mngr,
                self.preprocessor,
                0
            )

            compilable_lines = [obj for obj in line_objects if obj.compilable]

            # Filter to only actual instructions (not preprocessor directives)
            instruction_lines = [obj for obj in compilable_lines
                                 if hasattr(obj, 'instruction') and
                                 not obj.instruction.startswith('#') and
                                 obj.instruction.strip() != '']

            # Should have mov and nop, but not the add from the include (inner condition is false)
            self.assertEqual(len(instruction_lines), 2)
            self.assertTrue(instruction_lines[0].instruction.startswith('mov'))
            self.assertEqual(instruction_lines[1].instruction, 'nop')

    def test_recursive_include_protection(self):
        """Test that recursive includes are detected and cause an error."""

        with tempfile.TemporaryDirectory() as temp_dir:
            # Create file A that includes file B
            file_a_content = """
nop
#include "file_b.asm"
"""
            file_a_path = os.path.join(temp_dir, 'file_a.asm')
            with open(file_a_path, 'w') as f:
                f.write(file_a_content)

            # Create file B that includes file A (circular dependency)
            file_b_content = """
mov a, 1
#include "file_a.asm"
"""
            file_b_path = os.path.join(temp_dir, 'file_b.asm')
            with open(file_b_path, 'w') as f:
                f.write(file_b_content)

            # Test that attempting to load file A causes a sys.exit due to circular include
            asm_file = AssemblyFile(file_a_path, self.global_scope)
            include_paths = {temp_dir}

            with self.assertRaises(SystemExit) as cm:
                asm_file.load_line_objects(
                    self.isa_model,
                    include_paths,
                    self.memzone_mngr,
                    self.preprocessor,
                    0
                )

            # Verify the error message contains the expected text
            self.assertIn('assembly file included multiple times', str(cm.exception))

    def test_self_include_protection(self):
        """Test that a file including itself is detected and causes an error."""

        with tempfile.TemporaryDirectory() as temp_dir:
            # Create file that includes itself
            self_include_content = """
nop
#include "self_include.asm"
"""
            self_include_path = os.path.join(temp_dir, 'self_include.asm')
            with open(self_include_path, 'w') as f:
                f.write(self_include_content)

            # Test that attempting to load the file causes a sys.exit due to self-include
            asm_file = AssemblyFile(self_include_path, self.global_scope)
            include_paths = {temp_dir}

            with self.assertRaises(SystemExit) as cm:
                asm_file.load_line_objects(
                    self.isa_model,
                    include_paths,
                    self.memzone_mngr,
                    self.preprocessor,
                    0
                )

            # Verify the error message contains the expected text
            self.assertIn('assembly file included multiple times', str(cm.exception))


if __name__ == '__main__':
    unittest.main()
