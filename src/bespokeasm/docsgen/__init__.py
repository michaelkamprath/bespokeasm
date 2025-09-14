import sys
from pathlib import Path

import click
from bespokeasm.assembler.model import AssemblerModel

from .documentation_model import DocumentationModel
from .markdown_generator import MarkdownGenerator


class DocumentationGenerator:
    """
    Generates documentation for instruction set architectures from configuration files.
    """

    def __init__(self, config_file_path: str, is_verbose: int = 0):
        """
        Initialize the documentation generator.

        Args:
            config_file_path: Path to the ISA configuration file
            is_verbose: Verbosity level (0=quiet, 1=normal, 2+=debug)
        """
        self._config_file_path = config_file_path
        self._verbose = is_verbose
        self._model = None
        self._doc_model = None

    def generate_markdown_documentation(self, output_file_path: str | None = None) -> str:
        """
        Generate markdown documentation from the ISA configuration.

        Args:
            output_file_path: Path where to write the markdown file. If None,
                            will use the config file path with .md extension.

        Returns:
            The path to the generated documentation file.

        Raises:
            SystemExit: If there are errors in configuration loading or file writing
        """
        # Load and validate the ISA configuration
        self._load_isa_model()

        # Determine output file path
        if output_file_path is None:
            output_file_path = self._generate_default_output_path()

        if self._verbose:
            click.echo(f'Generating documentation from: {self._config_file_path}')
            click.echo(f'Output file: {output_file_path}')

        # Parse documentation from the configuration
        self._doc_model = DocumentationModel(self._model, self._verbose)

        # Generate markdown content
        markdown_generator = MarkdownGenerator(self._doc_model, self._verbose)
        markdown_content = markdown_generator.generate()

        # Write to file
        self._write_output_file(output_file_path, markdown_content)

        if self._verbose:
            click.echo(f'Documentation generated successfully: {output_file_path}')

        return output_file_path

    def _load_isa_model(self) -> None:
        """Load and validate the ISA configuration model."""
        try:
            self._model = AssemblerModel(self._config_file_path, self._verbose)
        except FileNotFoundError:
            sys.exit(f'ERROR: Configuration file not found: {self._config_file_path}')
        except Exception as e:
            sys.exit(f'ERROR: Failed to load configuration file: {e}')

    def _generate_default_output_path(self) -> str:
        """Generate the default output file path by replacing extension with .md"""
        config_path = Path(self._config_file_path)
        return str(config_path.with_suffix('.md'))

    def _write_output_file(self, output_path: str, content: str) -> None:
        """
        Write the markdown content to the output file.

        Args:
            output_path: Path to the output file
            content: Markdown content to write
        """
        try:
            # Create parent directories if they don't exist
            output_file = Path(output_path)
            output_file.parent.mkdir(parents=True, exist_ok=True)

            # Check if file exists and warn
            if output_file.exists() and self._verbose:
                click.echo(f'Warning: Overwriting existing file: {output_path}')

            # Write the content
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(content)

        except PermissionError:
            sys.exit(f'ERROR: Permission denied writing to: {output_path}')
        except OSError as e:
            sys.exit(f'ERROR: Failed to write output file: {e}')
