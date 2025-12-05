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
        self.operand_sets = self._parse_operand_sets_documentation()
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
            'registers': self._parse_registers_documentation(general_config),

            # Compatibility
            'min_version': general_config.get('min_version'),

            # Custom documentation elements
            'addressing_modes': self._parse_addressing_modes(doc_config.get('addressing_modes', {})),
            'flags': self._parse_flags(general_config.get('flags'), doc_config.get('flags')),
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

    def _parse_registers_documentation(self, general_config: dict[str, Any]) -> list[dict[str, Any]]:
        """
        Parse register documentation from general configuration.

        Args:
            general_config: General section of ISA configuration

        Returns:
            List of register documentation entries including name, description, details, and size.
        """
        registers_config = general_config.get('registers')
        if registers_config is None:
            return []

        register_docs: list[dict[str, Any]] = []

        if isinstance(registers_config, dict):
            for name, info in registers_config.items():
                if not isinstance(info, dict):
                    if self.verbose:
                        click.echo(f'Warning: Register "{name}" configuration should be a dictionary.')
                    info = {}

                title = info.get('title')
                description = info.get('description')
                details = info.get('details')

                # Backward compatibility: treat legacy description as title when title absent.
                if title is None and description is not None and 'title' not in info:
                    title = description
                    description = details
                    details = None

                register_docs.append({
                    'name': name,
                    'title': title,
                    'description': description,
                    'details': details,
                    'size': info.get('size')
                })
        else:
            try:
                iterator = iter(registers_config)
            except TypeError:
                if self.verbose:
                    click.echo('Warning: Invalid registers configuration; expected list or dict.')
                return []

            for name in iterator:
                register_docs.append({
                    'name': name,
                    'title': None,
                    'description': None,
                    'details': None,
                    'size': None
                })

        return register_docs

    def _parse_flags(
        self,
        primary_flags: Any,
        legacy_flags: Any
    ) -> list[dict[str, str]]:
        """
        Parse flags documentation.

        Args:
            primary_flags: Raw flags structure from the new configuration layout
            legacy_flags: Flags provided via the deprecated documentation subsection

        Returns:
            List of structured flag data
        """
        if primary_flags is None:
            flags_config = legacy_flags
        else:
            flags_config = primary_flags

        if flags_config is None:
            return []

        parsed_flags = []

        if isinstance(flags_config, dict):
            for symbol, data in flags_config.items():
                if not isinstance(data, dict):
                    if self.verbose:
                        click.echo(f'Warning: Invalid flag configuration for symbol "{symbol}". Expected a dictionary.')
                    data = {}
                name = data.get('name') or symbol
                parsed_flags.append({
                    'name': name,
                    'symbol': symbol,
                    'description': data.get('description', ''),
                    'details': data.get('details')
                })
        elif isinstance(flags_config, list):
            for flag_data in flags_config:
                if isinstance(flag_data, dict) and 'name' in flag_data:
                    parsed_flags.append({
                        'name': flag_data['name'],
                        'symbol': flag_data.get('symbol'),
                        'description': flag_data.get('description', ''),
                        'details': flag_data.get('details')
                    })
                elif self.verbose:
                    click.echo(f'Warning: Invalid flag format: {flag_data}')
        else:
            if self.verbose:
                click.echo('Warning: Flags configuration must be a dictionary or list.')

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

    def _parse_operand_sets_documentation(self) -> list[dict[str, Any]]:
        """
        Parse operand set documentation from the configuration.

        Returns:
            List of operand set documentation entries.
        """
        operand_sets_config = self._config.get('operand_sets', {})
        operand_set_docs: list[dict[str, Any]] = []

        for set_index, (set_name, set_config) in enumerate(operand_sets_config.items()):
            if not isinstance(set_config, dict):
                if self.verbose:
                    click.echo(f'Warning: Operand set "{set_name}" is not a dictionary.')
                continue

            doc_config = set_config.get('documentation') or {}
            operand_values = set_config.get('operand_values') or {}

            operands: list[dict[str, Any]] = []
            for operand_index, (operand_name, operand_config) in enumerate(operand_values.items()):
                if not isinstance(operand_config, dict):
                    if self.verbose:
                        click.echo(f'Warning: Operand "{operand_name}" in set "{set_name}" is not a dictionary.')
                    continue

                operand_doc = operand_config.get('documentation') or {}
                operand_type = operand_config.get('type', '')

                mode_from_doc = bool(operand_doc.get('mode'))
                mode = operand_doc.get('mode') or self._default_mode_from_type(operand_type)
                description = operand_doc.get('description')

                details = operand_doc.get('details')
                auto_details = self._derive_operand_auto_details(
                    operand_type,
                    operand_config,
                    bool(details)
                )
                if auto_details:
                    combined_details = []
                    if details:
                        combined_details.append(details)
                    combined_details.extend(auto_details)
                    details = '\n\n'.join(filter(None, combined_details))

                syntax = self._derive_operand_syntax(operand_name, operand_type, operand_config)

                operands.append({
                    'name': operand_name,
                    'title': operand_doc.get('title'),
                    'mode': mode,
                    'mode_from_doc': mode_from_doc,
                    'description': description,
                    'details': details,
                    'syntax': syntax,
                    'config_order': operand_index
                })

            # Apply operand_order if provided
            operand_order = doc_config.get('operand_order') or []
            if operand_order:
                # Map operand name to its order index
                order_lookup = {name: idx for idx, name in enumerate(operand_order)}
                max_index = len(order_lookup)

                def sort_key(entry: dict[str, Any]) -> tuple[int, int]:
                    return (
                        order_lookup.get(entry['name'], max_index + entry['config_order']),
                        entry['config_order']
                    )

                operands.sort(key=sort_key)

            documented = bool(doc_config)
            description = doc_config.get('description')
            details = doc_config.get('details')

            if not documented:
                description = None

            operand_set_docs.append({
                'key': set_name,
                'title': doc_config.get('title'),
                'category': doc_config.get('category'),
                'description': description,
                'details': details,
                'operands': operands,
                'documented': documented,
                'config_index': set_index
            })

        return operand_set_docs

    @staticmethod
    def _default_mode_from_type(operand_type: str | None) -> str | None:
        """Provide a fallback addressing mode label based on the operand type."""
        if operand_type is None:
            return None

        defaults = {
            'numeric': 'Immediate',
            'indirect_numeric': 'Indirect',
            'deferred_numeric': 'Deferred',
            'register': 'Register',
            'indexed_register': 'Indexed Register',
            'indirect_register': 'Indirect Register',
            'indirect_indexed_register': 'Indirect Indexed Register',
            'enumeration': 'Enumeration',
            'numeric_enumeration': 'Numeric Enumeration',
            'numeric_bytecode': 'Numeric Bytecode',
            'address': 'Address',
            'relative_address': 'Relative Address',
            'empty': 'No Operand'
        }

        return defaults.get(operand_type, operand_type.replace('_', ' ').title())

    @staticmethod
    def _get_decorator_symbol(decorator_config: dict[str, Any]) -> tuple[str, bool] | None:
        """Convert a decorator configuration into a symbol and prefix flag."""
        if not decorator_config or not isinstance(decorator_config, dict):
            return None

        decorator_type = decorator_config.get('type')
        if decorator_type is None:
            return None

        symbol_map = {
            'plus': '+',
            'plus_plus': '++',
            'minus': '-',
            'minus_minus': '--',
            'exclamation': '!',
            'at': '@'
        }

        symbol = symbol_map.get(decorator_type)
        if symbol is None:
            return None

        is_prefix = bool(decorator_config.get('is_prefix', False))
        return symbol, is_prefix

    def _derive_operand_syntax(
        self,
        operand_name: str,
        operand_type: str | None,
        operand_config: dict[str, Any]
    ) -> str:
        """Produce a syntax representation for an operand."""
        operand_type = operand_type or ''

        syntax: str
        if operand_type == 'numeric':
            syntax = 'numeric_expression'
        elif operand_type == 'indirect_numeric':
            syntax = '[numeric_expression]'
        elif operand_type == 'deferred_numeric':
            syntax = '[[numeric_expression]]'
        elif operand_type == 'register':
            register_label = operand_config.get('register')
            syntax = register_label if register_label else 'register_label'
        elif operand_type == 'indexed_register':
            register_label = operand_config.get('register', 'register_label')
            index_syntax = self._build_index_operand_syntax(operand_config)
            if index_syntax:
                syntax = f'{register_label} + {index_syntax}'
            else:
                syntax = f'{register_label} + offset_operand'
        elif operand_type == 'indirect_register':
            register_label = operand_config.get('register', 'register_label')
            offset_suffix = ' + offset' if operand_config.get('offset') else ''
            syntax = f'[{register_label}{offset_suffix}]'
        elif operand_type == 'indirect_indexed_register':
            register_label = operand_config.get('register', 'register_label')
            index_syntax = self._build_index_operand_syntax(operand_config)
            if not index_syntax:
                index_syntax = 'offset_operand'
            syntax = f'[{register_label} + {index_syntax}]'
        elif operand_type == 'enumeration':
            literal_tokens = self._collect_enumeration_literals(operand_config)
            if literal_tokens:
                syntax = ' | '.join(literal_tokens)
            else:
                syntax = operand_name
        elif operand_type == 'numeric_enumeration':
            syntax = 'integer'
        elif operand_type == 'numeric_bytecode':
            syntax = 'integer'
        elif operand_type == 'address':
            syntax = 'numeric_expression'
        elif operand_type == 'relative_address':
            use_curly = bool(operand_config.get('use_curly_braces', False))
            syntax = '{numeric_expression}' if use_curly else 'numeric_expression'
        elif operand_type == 'empty':
            syntax = ''
        else:
            syntax = operand_name

        decorator_info = self._get_decorator_symbol(operand_config.get('decorator'))
        if decorator_info:
            decorator_symbol, is_prefix = decorator_info
            if syntax:
                syntax = f'{decorator_symbol}{syntax}' if is_prefix else f'{syntax}{decorator_symbol}'
            else:
                syntax = decorator_symbol

        return syntax

    @staticmethod
    def _collect_enumeration_literals(operand_config: dict[str, Any]) -> list[str]:
        """Collect literal tokens from enumeration-style operand configurations."""
        literals: set[str] = set()

        for section in ('bytecode', 'argument'):
            section_config = operand_config.get(section)
            if not isinstance(section_config, dict):
                continue
            value_dict = section_config.get('value_dict')
            if isinstance(value_dict, dict):
                for key in value_dict.keys():
                    literals.add(str(key))

        return sorted(literals)

    def _build_index_operand_syntax(self, operand_config: dict[str, Any]) -> str | None:
        """Derive combined syntax for index operands."""
        index_operands = operand_config.get('index_operands')
        if not isinstance(index_operands, dict) or not index_operands:
            return None

        syntaxes: list[str] = []
        for idx_name, idx_config in index_operands.items():
            if not isinstance(idx_config, dict):
                continue
            idx_type = idx_config.get('type')
            if not idx_type:
                continue
            idx_syntax = self._derive_operand_syntax(idx_name, idx_type, idx_config)
            if idx_syntax:
                syntaxes.append(idx_syntax)

        if not syntaxes:
            return None

        # Preserve order while removing duplicates
        unique_syntaxes = list(dict.fromkeys(syntaxes))
        if len(unique_syntaxes) == 1:
            return unique_syntaxes[0]
        return f"({' | '.join(unique_syntaxes)})"

    @staticmethod
    def _derive_operand_auto_details(
        operand_type: str | None,
        operand_config: dict[str, Any],
        has_manual_details: bool
    ) -> list[str]:
        """Generate automatic detail notes for specific operand configurations."""
        notes: list[str] = []
        operand_type = operand_type or ''

        if operand_type == 'address':
            argument_config = operand_config.get('argument', {})
            if isinstance(argument_config, dict):
                memory_zone = argument_config.get('memory_zone')
                if memory_zone:
                    notes.append(f'Valid within `{memory_zone}` memory zone.')

                if argument_config.get('slice_lsb'):
                    notes.append('Uses only the least significant bits of the address value.')

                if argument_config.get('match_address_msb'):
                    notes.append('High address bits are taken from the current instruction address.')

        if operand_type == 'relative_address':
            if operand_config.get('use_curly_braces'):
                notes.append('Relative address operand uses curly brace notation.')

        if operand_type == 'numeric_bytecode':
            bytecode_config = operand_config.get('bytecode', {})
            if isinstance(bytecode_config, dict):
                min_value = bytecode_config.get('min')
                max_value = bytecode_config.get('max')
                if min_value is not None or max_value is not None:
                    if min_value is not None and max_value is not None:
                        notes.append(f'Allowed values: {min_value} to {max_value}.')
                    elif min_value is not None:
                        notes.append(f'Minimum value: {min_value}.')
                    elif max_value is not None:
                        notes.append(f'Maximum value: {max_value}.')

        if operand_type == 'numeric_enumeration' and not has_manual_details:
            literals = DocumentationModel._collect_enumeration_literals(operand_config)
            if literals:
                formatted = ', '.join(f'`{literal}`' for literal in literals)
                notes.append(f'Possible values: {formatted}.')

        return notes

    def _parse_instruction_documentation(self) -> dict[str, Any]:
        """
        Parse instruction documentation from the configuration.

        Returns:
            Dictionary mapping instruction names to their documentation
        """
        instructions_config = self._config.get('instructions', {})
        instruction_docs = {}
        categories = set()

        operand_sets_config = self._config.get('operand_sets', {})

        for instr_name, instr_config in instructions_config.items():
            doc_config = instr_config.get('documentation')
            if not isinstance(doc_config, dict):
                doc_config = {}

            documented = bool(doc_config)
            if documented:
                category = doc_config.get('category', 'Uncategorized')
            else:
                category = 'Uncategorized'

            categories.add(category)

            title = doc_config.get('title')
            if title is None and 'description' in doc_config:
                # Backward compatibility for legacy field name
                title = doc_config.get('description')

            versions = self._build_instruction_versions(
                instr_name,
                instr_config,
                operand_sets_config
            )

            instruction_docs[instr_name] = {
                'category': category,
                'title': title if documented else None,
                'description': doc_config.get('description') if documented else None,
                'details': doc_config.get('details') if documented else None,
                'modifies': self._parse_modifies(doc_config.get('modifies', [])) if documented else [],
                'examples': self._parse_examples(doc_config.get('examples', [])) if documented else [],
                'documented': documented,
                'versions': versions
            }

            if not documented and self.verbose >= 2:
                click.echo(f'No documentation found for instruction: {instr_name}')

        if self.verbose:
            documented_count = sum(
                1 for doc in instruction_docs.values()
                if doc.get('documented', False)
            )
            click.echo(
                f'Processed {len(instruction_docs)} instructions; '
                f'{documented_count} with documentation'
            )
            click.echo(f"Categories found: {', '.join(sorted(categories))}")

        return instruction_docs

    def _build_instruction_versions(
        self,
        mnemonic: str,
        instruction_config: dict[str, Any],
        operand_sets_config: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """
        Build the ordered list of operand signatures for an instruction across all variants.
        """
        version_sources: list[dict[str, Any] | None] = []

        if 'operands' in instruction_config or 'bytecode' in instruction_config:
            version_sources.append(instruction_config.get('operands'))

        variants = instruction_config.get('variants')
        if isinstance(variants, list):
            for variant in variants:
                if isinstance(variant, dict):
                    version_sources.append(variant.get('operands'))
                elif self.verbose:
                    click.echo(
                        f'Warning: Variant for instruction "{mnemonic}" is not a dictionary. Skipping operand extraction.'
                    )

        if not version_sources:
            # Ensure at least one version so the syntax block can be emitted even without operands.
            version_sources.append(None)

        versions: list[dict[str, Any]] = []
        for index, operands_config in enumerate(version_sources, start=1):
            signatures = self._build_instruction_signatures(
                operands_config,
                operand_sets_config
            )
            versions.append({
                'index': index,
                'signatures': signatures
            })

        return versions

    def _build_instruction_signatures(
        self,
        operands_config: dict[str, Any] | None,
        operand_sets_config: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """
        Derive the documented operand signatures for a given operands configuration.
        """
        config = operands_config if isinstance(operands_config, dict) else {}
        signatures: list[dict[str, Any]] = []

        specific_operands = config.get('specific_operands')
        if isinstance(specific_operands, dict):
            for specific_key, specific_config in specific_operands.items():
                operand_list = specific_config.get('list')
                if not isinstance(operand_list, dict):
                    if self.verbose:
                        click.echo(
                            f'Warning: specific_operands entry "{specific_key}" is missing a valid "list" dictionary.'
                        )
                    continue

                operands: list[dict[str, Any]] = []
                for operand_name, operand_definition in operand_list.items():
                    operand_info = operand_definition if isinstance(operand_definition, dict) else {}
                    operand_doc_raw = operand_info.get('documentation')
                    operand_doc = operand_doc_raw if isinstance(operand_doc_raw, dict) else {}
                    operand_type_value = operand_info.get('type')
                    operand_type = str(operand_type_value) if operand_type_value is not None else ''

                    operands.append({
                        'name': operand_name,
                        'type': operand_type,
                        'description': operand_doc.get('description'),
                        'details': operand_doc.get('details'),
                        'include_in_code': operand_type != 'empty'
                    })

                signatures.append({
                    'kind': 'specific',
                    'label': specific_key,
                    'operands': operands
                })

        operand_sets = config.get('operand_sets')
        if isinstance(operand_sets, dict):
            operand_set_names = operand_sets.get('list')
            if isinstance(operand_set_names, list) and operand_set_names:
                operands: list[dict[str, Any]] = []
                for set_name in operand_set_names:
                    if not isinstance(set_name, str):
                        if self.verbose:
                            click.echo(
                                'Warning: Operand set name encountered that is not a string. '
                                'Skipping in syntax documentation.'
                            )
                        continue

                    set_doc_config = operand_sets_config.get(set_name, {}) if operand_sets_config else {}
                    doc_config = set_doc_config.get('documentation') if isinstance(set_doc_config, dict) else None
                    if isinstance(doc_config, dict):
                        description = doc_config.get('description')
                        details = doc_config.get('details')
                    else:
                        description = None
                        details = None

                    operands.append({
                        'name': set_name,
                        'type': 'operand set',
                        'description': description,
                        'details': details,
                        'include_in_code': True
                    })

                if operands:
                    signatures.append({
                        'kind': 'operand_sets',
                        'label': None,
                        'operands': operands
                    })

        if not signatures:
            signatures.append({
                'kind': 'none',
                'label': None,
                'operands': []
            })

        return signatures

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
