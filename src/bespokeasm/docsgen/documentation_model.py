from typing import Any

import click
from bespokeasm.assembler.model import AssemblerModel


class DocumentationModel:
    """
    Parses and structures documentation data from ISA configuration files.
    """

    def __init__(self, isa_model: AssemblerModel, verbose: int = 0):
        """
        Initialize the documentation model.

        Args:
            isa_model: The loaded ISA assembler model
            verbose: Verbosity level for logging
        """
        self.isa_model = isa_model
        self.verbose = verbose
        self._config = isa_model._config

        # Parse documentation sections
        self.general_docs = self._parse_general_documentation()
        self.instruction_docs = self._parse_instruction_documentation()

    @property
    def isa_name(self) -> str:
        """Get the ISA name from the configuration."""
        return self.isa_model.isa_name

    @property
    def isa_description(self) -> str | None:
        """Get the ISA description from general documentation."""
        return self.general_docs.get('description')

    @property
    def isa_identifier_name(self) -> str | None:
        """Get the ISA identifier name from general configuration."""
        return self.general_docs.get('isa_name')

    def _parse_general_documentation(self) -> dict[str, Any]:
        """
        Parse general documentation from the configuration.
        This includes both the general config fields and the documentation subsection.

        Returns:
            Dictionary containing all general section data
        """
        general_config = self._config.get('general', {})
        doc_config = general_config.get('documentation', {})

        if not general_config and self.verbose:
            click.echo('No general section found in configuration')

        # Parse identifier information
        identifier = general_config.get('identifier', {})

        # Parse hardware architecture details
        hardware = {
            'address_size': general_config.get('address_size'),
            'word_size': general_config.get('word_size', 8),
            'word_segment_size': general_config.get('word_segment_size'),  # defaults to word_size if not specified
            'page_size': general_config.get('page_size', 1),
            'origin': general_config.get('origin', 0)
        }

        # Handle word_segment_size default
        if hardware['word_segment_size'] is None:
            hardware['word_segment_size'] = hardware['word_size']

        # Parse endianness configuration
        endianness = {
            'multi_word_endianness': general_config.get('multi_word_endianness', 'big'),
            'intra_word_endianness': general_config.get('intra_word_endianness', 'big'),
            'deprecated_endian': general_config.get('endian')  # deprecated field
        }

        # Parse string and data handling
        string_config = {
            'cstr_terminator': general_config.get('cstr_terminator', 0),
            'allow_embedded_strings': general_config.get('allow_embedded_strings', False),
            'string_byte_packing': general_config.get('string_byte_packing', False),
            'string_byte_packing_fill': general_config.get('string_byte_packing_fill', 0)
        }

        return {
            # ISA Overview
            'isa_name': identifier.get('name'),
            'isa_version': identifier.get('version'),
            'file_extension': identifier.get('extension', 'asm'),
            'description': doc_config.get('description'),
            'details': doc_config.get('details'),

            # Hardware architecture
            'hardware': hardware,

            # Endianness
            'endianness': endianness,

            # String and data handling
            'string_config': string_config,

            # Register set
            'registers': general_config.get('registers', []),

            # Compatibility
            'min_version': general_config.get('min_version'),

            # Custom documentation elements
            'addressing_modes': self._parse_addressing_modes(doc_config.get('addressing_modes', {})),
            'flags': self._parse_flags(doc_config.get('flags', [])),
            'examples': self._parse_examples(doc_config.get('examples', []))
        }

    def _parse_addressing_modes(self, addressing_modes: dict[str, Any]) -> list[dict[str, str]]:
        """
        Parse addressing modes documentation.

        Args:
            addressing_modes: Raw addressing modes from config

        Returns:
            List of structured addressing mode data
        """
        modes = []
        for name, data in addressing_modes.items():
            if isinstance(data, dict):
                modes.append({
                    'name': name,
                    'description': data.get('description', ''),
                    'details': data.get('details')
                })
            elif self.verbose:
                click.echo(f"Warning: Invalid addressing mode format for '{name}'")

        return modes

    def _parse_flags(self, flags: list[dict[str, Any]]) -> list[dict[str, str]]:
        """
        Parse flags documentation.

        Args:
            flags: Raw flags list from config

        Returns:
            List of structured flag data
        """
        parsed_flags = []
        for flag_data in flags:
            if isinstance(flag_data, dict) and 'name' in flag_data:
                parsed_flags.append({
                    'name': flag_data['name'],
                    'symbol': flag_data.get('symbol'),
                    'description': flag_data.get('description', ''),
                    'details': flag_data.get('details')
                })
            elif self.verbose:
                click.echo(f'Warning: Invalid flag format: {flag_data}')

        return parsed_flags

    def _parse_examples(self, examples: list[dict[str, Any]]) -> list[dict[str, str]]:
        """
        Parse general examples documentation.

        Args:
            examples: Raw examples list from config

        Returns:
            List of structured example data
        """
        parsed_examples = []
        for example in examples:
            if isinstance(example, dict) and 'code' in example:
                parsed_examples.append({
                    'description': example.get('description', ''),
                    'details': example.get('details'),
                    'code': example['code']
                })
            elif self.verbose:
                click.echo(f'Warning: Invalid example format: {example}')

        return parsed_examples

    def _parse_instruction_documentation(self) -> dict[str, Any]:
        """
        Parse instruction documentation from the configuration.

        Returns:
            Dictionary mapping instruction names to their documentation
        """
        instructions_config = self._config.get('instructions', {})
        instruction_docs = {}
        categories = set()

        for instr_name, instr_config in instructions_config.items():
            doc_config = instr_config.get('documentation', {})

            if doc_config:
                category = doc_config.get('category', 'Uncategorized')
                categories.add(category)

                instruction_docs[instr_name] = {
                    'category': category,
                    'description': doc_config.get('description'),
                    'details': doc_config.get('details'),
                    'modifies': self._parse_modifies(doc_config.get('modifies', [])),
                    'examples': self._parse_examples(doc_config.get('examples', []))
                }
            elif self.verbose >= 2:
                click.echo(f'No documentation found for instruction: {instr_name}')

        if self.verbose:
            click.echo(f'Found documentation for {len(instruction_docs)} instructions')
            click.echo(f"Categories found: {', '.join(sorted(categories))}")

        return instruction_docs

    def _parse_modifies(self, modifies: list[dict[str, Any]]) -> list[dict[str, str]]:
        """
        Parse modifies documentation for instructions.

        Args:
            modifies: Raw modifies list from config

        Returns:
            List of structured modifies data
        """
        parsed_modifies = []
        for modify in modifies:
            if isinstance(modify, dict):
                # Each modify entry should have exactly one of: register, memory, flag
                modify_entry = {
                    'type': None,
                    'target': None,
                    'description': modify.get('description', ''),
                    'details': modify.get('details')
                }

                if 'register' in modify:
                    modify_entry['type'] = 'register'
                    modify_entry['target'] = modify['register']
                elif 'memory' in modify:
                    modify_entry['type'] = 'memory'
                    modify_entry['target'] = modify['memory']
                elif 'flag' in modify:
                    modify_entry['type'] = 'flag'
                    modify_entry['target'] = modify['flag']
                else:
                    if self.verbose:
                        click.echo(f'Warning: Invalid modifies entry (no register/memory/flag): {modify}')
                    continue

                parsed_modifies.append(modify_entry)
            elif self.verbose:
                click.echo(f'Warning: Invalid modifies format: {modify}')

        return parsed_modifies

    def get_instructions_by_category(self) -> dict[str, list[str]]:
        """
        Get instructions organized by category.

        Returns:
            Dictionary mapping category names to lists of instruction names
        """
        categories = {}
        for instr_name, instr_doc in self.instruction_docs.items():
            category = instr_doc['category']
            if category not in categories:
                categories[category] = []
            categories[category].append(instr_name)

        # Sort instruction names within each category
        for category in categories:
            categories[category].sort()

        return categories
