import os
import tempfile
import unittest
from unittest.mock import Mock
from unittest.mock import patch

from bespokeasm.docsgen import DocumentationGenerator


class TestDocumentationGenerator(unittest.TestCase):

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.config_file = os.path.join(self.temp_dir, 'test-isa.yaml')

        # Create a minimal config file
        with open(self.config_file, 'w') as f:
            f.write("""
general:
  min_version: 0.5.0
  identifier:
    name: test-isa
    version: "1.0.0"
instructions:
  nop:
    bytecode:
      value: 0
      size: 8
""")

    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir)

    def test_init(self):
        """Test DocumentationGenerator initialization."""
        generator = DocumentationGenerator(self.config_file, is_verbose=1)

        self.assertEqual(generator._config_file_path, self.config_file)
        self.assertEqual(generator._verbose, 1)
        self.assertIsNone(generator._model)
        self.assertIsNone(generator._doc_model)

    def test_generate_default_output_path(self):
        """Test generation of default output path."""
        generator = DocumentationGenerator(self.config_file)

        output_path = generator._generate_default_output_path()
        expected_path = os.path.join(self.temp_dir, 'test-isa.md')

        self.assertEqual(output_path, expected_path)

    def test_generate_default_output_path_with_json(self):
        """Test generation of default output path with JSON config."""
        json_config = os.path.join(self.temp_dir, 'test-isa.json')
        generator = DocumentationGenerator(json_config)

        output_path = generator._generate_default_output_path()
        expected_path = os.path.join(self.temp_dir, 'test-isa.md')

        self.assertEqual(output_path, expected_path)

    @patch('bespokeasm.docsgen.AssemblerModel')
    @patch('bespokeasm.docsgen.DocumentationModel')
    @patch('bespokeasm.docsgen.MarkdownGenerator')
    def test_generate_markdown_documentation_success(self, mock_md_gen, mock_doc_model, mock_asm_model):
        """Test successful markdown documentation generation."""
        # Setup mocks
        mock_asm_instance = Mock()
        mock_asm_model.return_value = mock_asm_instance

        mock_doc_instance = Mock()
        mock_doc_model.return_value = mock_doc_instance

        mock_md_instance = Mock()
        mock_md_instance.generate.return_value = '# Test Documentation'
        mock_md_gen.return_value = mock_md_instance

        generator = DocumentationGenerator(self.config_file, is_verbose=1)

        with patch('click.echo') as mock_echo:
            output_path = generator.generate_markdown_documentation()

            # Verify output path
            expected_output = os.path.join(self.temp_dir, 'test-isa.md')
            self.assertEqual(output_path, expected_output)

            # Verify file was created
            self.assertTrue(os.path.exists(output_path))

            # Verify content
            with open(output_path) as f:
                content = f.read()
            self.assertEqual(content, '# Test Documentation')

            # Verify verbose output
            mock_echo.assert_any_call(f'Generating documentation from: {self.config_file}')
            mock_echo.assert_any_call(f'Output file: {expected_output}')
            mock_echo.assert_any_call(f'Documentation generated successfully: {expected_output}')

    @patch('bespokeasm.docsgen.AssemblerModel')
    def test_generate_markdown_documentation_with_custom_output(self, mock_asm_model):
        """Test markdown generation with custom output path."""
        mock_asm_instance = Mock()
        mock_asm_model.return_value = mock_asm_instance

        custom_output = os.path.join(self.temp_dir, 'custom', 'output.md')

        generator = DocumentationGenerator(self.config_file)

        with patch('bespokeasm.docsgen.DocumentationModel') as mock_doc_model, \
             patch('bespokeasm.docsgen.MarkdownGenerator') as mock_md_gen:

            mock_doc_instance = Mock()
            mock_doc_model.return_value = mock_doc_instance

            mock_md_instance = Mock()
            mock_md_instance.generate.return_value = '# Custom Output'
            mock_md_gen.return_value = mock_md_instance

            output_path = generator.generate_markdown_documentation(custom_output)

            # Verify output path
            self.assertEqual(output_path, custom_output)

            # Verify file was created (parent directories should be created)
            self.assertTrue(os.path.exists(custom_output))

            # Verify content
            with open(custom_output) as f:
                content = f.read()
            self.assertEqual(content, '# Custom Output')

    def test_load_isa_model_file_not_found(self):
        """Test handling of missing configuration file."""
        non_existent_file = os.path.join(self.temp_dir, 'missing.yaml')
        generator = DocumentationGenerator(non_existent_file)

        with self.assertRaises(SystemExit):
            generator.generate_markdown_documentation()

        # Should exit with error message about file not found
        # (The actual AssemblerModel will raise FileNotFoundError)

    @patch('bespokeasm.docsgen.AssemblerModel')
    def test_load_isa_model_invalid_config(self, mock_asm_model):
        """Test handling of invalid configuration file."""
        mock_asm_model.side_effect = Exception('Invalid YAML format')

        generator = DocumentationGenerator(self.config_file)

        with self.assertRaises(SystemExit):
            generator.generate_markdown_documentation()

    def test_write_output_file_permission_denied(self):
        """Test handling of permission denied when writing output."""
        generator = DocumentationGenerator(self.config_file)

        # Try to write to a file we can't write to
        if os.name != 'nt':  # Skip on Windows where permission handling is different
            read_only_file = os.path.join(self.temp_dir, 'readonly.md')

            # Create file and make it read-only
            with open(read_only_file, 'w') as f:
                f.write('test')
            os.chmod(read_only_file, 0o444)

            try:
                with self.assertRaises(SystemExit):
                    generator._write_output_file(read_only_file, 'new content')
            finally:
                # Clean up - restore write permission
                os.chmod(read_only_file, 0o644)

    def test_write_output_file_overwrite_warning(self):
        """Test warning when overwriting existing file."""
        generator = DocumentationGenerator(self.config_file, is_verbose=1)

        existing_file = os.path.join(self.temp_dir, 'existing.md')
        with open(existing_file, 'w') as f:
            f.write('existing content')

        with patch('click.echo') as mock_echo:
            generator._write_output_file(existing_file, 'new content')

            # Should warn about overwriting
            mock_echo.assert_called_with(f'Warning: Overwriting existing file: {existing_file}')

        # Verify content was overwritten
        with open(existing_file) as f:
            content = f.read()
        self.assertEqual(content, 'new content')

    @patch('bespokeasm.docsgen.AssemblerModel')
    @patch('bespokeasm.docsgen.DocumentationModel')
    @patch('bespokeasm.docsgen.MarkdownGenerator')
    def test_integration_with_real_output(self, mock_md_gen, mock_doc_model, mock_asm_model):
        """Test end-to-end integration with real file output."""
        # Setup realistic mocks
        mock_asm_instance = Mock()
        mock_asm_instance.isa_name = 'test-isa'
        mock_asm_model.return_value = mock_asm_instance

        mock_doc_instance = Mock()
        mock_doc_instance.isa_name = 'test-isa'
        mock_doc_instance.isa_description = 'Test ISA'
        mock_doc_model.return_value = mock_doc_instance

        # Generate realistic markdown content
        markdown_content = """# test-isa

Test ISA

## General Information

This is a test ISA for documentation generation.

# Instructions

## Arithmetic

### ADD : Add to accumulator

Adds the operand to the accumulator register.

#### Modifies

| Type | Target | Description | Details |
| --- | --- | --- | --- |
| Register | A | Result of addition |  |
| Flag | C | Set on overflow |  |
| Flag | Z | Set if result is zero |  |
"""

        mock_md_instance = Mock()
        mock_md_instance.generate.return_value = markdown_content
        mock_md_gen.return_value = mock_md_instance

        generator = DocumentationGenerator(self.config_file, is_verbose=0)
        output_path = generator.generate_markdown_documentation()

        # Verify file exists and has correct content
        self.assertTrue(os.path.exists(output_path))

        with open(output_path, encoding='utf-8') as f:
            content = f.read()

        self.assertEqual(content, markdown_content)

        # Verify the correct methods were called
        mock_asm_model.assert_called_once_with(self.config_file, 0)
        mock_doc_model.assert_called_once_with(mock_asm_instance, 0)
        mock_md_gen.assert_called_once_with(mock_doc_instance, 0)
        mock_md_instance.generate.assert_called_once()


if __name__ == '__main__':
    unittest.main()
