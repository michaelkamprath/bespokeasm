from typing import Any

import click

from .documentation_model import DocumentationModel


class MarkdownGenerator:
    """
    Generates markdown documentation from parsed documentation data.
    """

    def __init__(self, doc_model: DocumentationModel, verbose: int = 0):
        """
        Initialize the markdown generator.

        Args:
            doc_model: The parsed documentation model
            verbose: Verbosity level for logging
        """
        self.doc_model = doc_model
        self.verbose = verbose

    def generate(self) -> str:
        """
        Generate the complete markdown documentation.

        Returns:
            The complete markdown content as a string
        """
        sections = []

        # Document header
        sections.append(self._generate_header())

        # General information section
        if self._has_general_documentation():
            sections.append(self._generate_general_section())

        # Operand sets section
        if getattr(self.doc_model, 'operand_sets', None):
            operand_sets_section = self._generate_operand_sets_section()
            if operand_sets_section:
                sections.append(operand_sets_section)

        # Instructions section
        if self.doc_model.instruction_docs:
            sections.append(self._generate_instructions_section())
        elif self.verbose:
            click.echo('Warning: No instruction documentation found')

        return '\n\n'.join(filter(None, sections))

    def _optimize_table_columns(
        self,
        headers: list[str],
        rows: list[list[str]]
    ) -> tuple[list[str], list[list[str]], list[int]]:
        """
        Optimize table columns by removing columns that are empty for all rows.

        Args:
            headers: List of column headers
            rows: List of rows, where each row is a list of cell values

        Returns:
            Tuple of (optimized_headers, optimized_rows)
        """
        if not rows or not headers:
            return headers, rows, list(range(len(headers)))

        # Determine which columns have any non-empty content
        columns_to_keep = []
        for col_idx, header in enumerate(headers):
            has_content = False
            for row in rows:
                if col_idx < len(row):
                    cell_value = row[col_idx]
                    # Consider a cell empty if it's None, empty string, or only whitespace
                    if cell_value is not None and str(cell_value).strip():
                        has_content = True
                        break
            columns_to_keep.append(has_content)

        # Filter headers and rows to keep only non-empty columns
        keep_indices = [i for i in range(len(headers)) if columns_to_keep[i]]
        optimized_headers = [headers[i] for i in keep_indices]
        optimized_rows = []
        for row in rows:
            optimized_row = [row[i] if i < len(row) else '' for i in keep_indices]
            optimized_rows.append(optimized_row)

        return optimized_headers, optimized_rows, keep_indices

    def _generate_markdown_table(
        self,
        headers: list[str],
        rows: list[list[str]],
        column_alignments: list[str | None] | None = None
    ) -> str:
        """
        Generate a markdown table with column optimization.

        Args:
            headers: List of column headers
            rows: List of rows, where each row is a list of cell values

        Returns:
            Formatted markdown table string
        """
        # Optimize columns
        opt_headers, opt_rows, keep_indices = self._optimize_table_columns(headers, rows)

        if not opt_headers or not opt_rows:
            return ''

        # Generate table
        table_lines = []

        # Header row
        header_line = '| ' + ' | '.join(opt_headers) + ' |'
        table_lines.append(header_line)

        # Separator row
        alignments = []
        if column_alignments:
            for idx in keep_indices:
                if idx < len(column_alignments):
                    alignments.append(column_alignments[idx])
                else:
                    alignments.append(None)
        separator_line = \
            '| ' + ' | '.join(
                self._get_alignment_marker(alignment)
                for alignment in self._pad_alignments(
                    alignments,
                    len(opt_headers)
                )
            ) + ' |'
        table_lines.append(separator_line)

        # Data rows
        for row in opt_rows:
            # Ensure row has same number of columns as headers, pad with empty strings if needed
            padded_row = row + [''] * (len(opt_headers) - len(row))
            row_line = '| ' + ' | '.join(padded_row) + ' |'
            table_lines.append(row_line)

        return '\n'.join(table_lines)

    @staticmethod
    def _pad_alignments(alignments: list[str | None], size: int) -> list[str | None]:
        """Ensure the alignments list matches the number of columns."""
        if not alignments:
            return [None] * size

        padded = list(alignments)
        if len(padded) < size:
            padded.extend([None] * (size - len(padded)))
        elif len(padded) > size:
            padded = padded[:size]
        return padded

    @staticmethod
    def _get_alignment_marker(alignment: str | None) -> str:
        """Convert alignment keywords into markdown separator markers."""
        if alignment == 'left':
            return ':--'
        if alignment == 'right':
            return '--:'
        if alignment == 'center':
            return ':-:'
        return '---'

    def _generate_attribute_table(self, category: str, rows: list[tuple[str, str]]) -> str:
        """Generate a two-column attribute/value table with left alignment."""
        if not rows:
            return ''

        lines: list[str] = []
        for label, value in rows:
            if value is None:
                continue
            value_str = str(value).strip()
            if not value_str:
                continue
            if not lines:
                # Initialize header and alignment rows once we know we have data
                lines.append(f'| {category} Attribute | Value |')
                lines.append('|:--|:--|')
            lines.append(f'| **{label}** | {value_str} |')

        return '\n'.join(lines)

    def _generate_header(self) -> str:
        """Generate the document header."""
        # Use identifier name if available and is a string, otherwise fall back to isa_name
        isa_name = self.doc_model.isa_name
        if (self.doc_model.isa_identifier_name and
                isinstance(self.doc_model.isa_identifier_name, str)):
            isa_name = self.doc_model.isa_identifier_name

        header = f'# {isa_name}'

        if self.doc_model.isa_description:
            header += f'\n\n{self.doc_model.isa_description}'

        return header

    def _has_general_documentation(self) -> bool:
        """Check if there's any general documentation to display."""
        # Check if there's any meaningful documentation content beyond basic config
        general = self.doc_model.general_docs

        # Check for custom documentation fields
        if general.get('details'):
            return True
        if general.get('addressing_modes'):
            return True
        if general.get('flags'):
            return True
        if general.get('examples'):
            return True

        # For now, always show general section since it contains configuration details
        # This differs from the test expectation but matches the requirements
        return True

    def _generate_general_section(self) -> str:
        """Generate the comprehensive general information section."""
        sections = ['## General Information']
        general = self.doc_model.general_docs

        # ISA Overview
        table_sections = []

        isa_overview = self._generate_isa_overview(general)
        if isa_overview:
            table_sections.append(isa_overview)

        # Hardware Architecture Details
        hardware_section = self._generate_hardware_section(general.get('hardware', {}))
        if hardware_section:
            table_sections.append(hardware_section)

        # Endianness Configuration
        endianness_section = self._generate_endianness_section(general.get('endianness', {}))
        if endianness_section:
            table_sections.append(endianness_section)

        # String and Data Handling
        string_section = self._generate_string_section(general.get('string_config', {}))
        if string_section:
            table_sections.append(string_section)

        if table_sections:
            sections.append('\n\n---\n\n'.join(table_sections))

        # Register Set
        registers_section = self._generate_registers_section(general.get('registers', []))
        if registers_section:
            sections.append(registers_section)

        # Addressing modes
        if general.get('addressing_modes'):
            sections.append(self._generate_addressing_modes_section(general['addressing_modes']))

        # Flags
        if general.get('flags'):
            sections.append(self._generate_flags_section(general['flags']))

        # Examples
        if general.get('examples'):
            sections.append(self._generate_general_examples_section(general['examples']))

        # Compatibility
        compatibility_section = self._generate_compatibility_section(general)
        if compatibility_section:
            sections.append(compatibility_section)

        return '\n\n'.join(sections)

    def _generate_operand_sets_section(self) -> str:
        """Generate the operand sets section of the documentation."""
        operand_sets = getattr(self.doc_model, 'operand_sets', None) or []
        if not operand_sets:
            return ''

        def sort_key(set_doc: dict[str, Any]) -> tuple[Any, ...]:
            category = set_doc.get('category')
            display_name = (set_doc.get('title') or set_doc.get('key') or '').lower()
            category_rank = 0 if category else 1
            category_label = category.lower() if isinstance(category, str) else ''
            config_index = set_doc.get('config_index', 0)
            return category_rank, category_label, display_name, config_index

        sorted_sets = sorted(operand_sets, key=sort_key)

        sections: list[str] = ['## Operand Sets']
        for operand_set in sorted_sets:
            key = operand_set.get('key', 'Operand Set')
            title = operand_set.get('title')
            code_key = f'`{key}`'
            header_text = f'{code_key} - {title}' if title else code_key
            subsection_parts: list[str] = [f'### {header_text}']

            category = operand_set.get('category')
            if category:
                subsection_parts.append(f'*Category: {category}*')

            description = operand_set.get('description')
            if description:
                subsection_parts.append(description)

            details = operand_set.get('details')
            if details:
                subsection_parts.append(details)

            table = self._generate_operand_set_table(operand_set.get('operands', []))
            if table:
                subsection_parts.append(table)
            elif self.verbose:
                click.echo(f'Warning: Operand set "{operand_set.get("key")}" has no operand entries.')

            sections.append('\n\n'.join(filter(None, subsection_parts)))

        return '\n\n'.join(sections)

    def _generate_operand_set_table(self, operands: list[dict[str, Any]]) -> str:
        """Generate the per-operand table for an operand set."""
        if not operands:
            return ''

        headers = ['Operand', 'Syntax', '[Addressing Mode](#addressing-modes)', 'Description', 'Details']
        alignments = ['left', 'left', 'left', 'left', 'left']
        rows: list[list[str]] = []

        for operand in operands:
            operand_name = operand.get('name', '')
            operand_title = operand.get('title')
            if operand_title and operand_name:
                operand_cell = f'{operand_title} (`{operand_name}`)'
            elif operand_title:
                operand_cell = operand_title
            else:
                operand_cell = f'`{operand_name}`' if operand_name else ''

            syntax = operand.get('syntax', '')
            if syntax:
                escaped_syntax = syntax.replace('|', r'\|')
                syntax_cell = f'`{escaped_syntax}`'
            else:
                syntax_cell = ''

            mode_value = operand.get('mode') or ''
            if operand.get('mode_from_doc') and mode_value:
                mode_cell = f'`{mode_value}`'
            else:
                mode_cell = mode_value
            description = operand.get('description') or ''
            if description:
                description = description.replace('\n', '<br>')

            details = operand.get('details') or ''
            if details:
                details = details.replace('\n', '<br>')

            rows.append([operand_cell, syntax_cell, mode_cell, description, details])

        table = self._generate_markdown_table(headers, rows, column_alignments=alignments)
        if not table:
            return ''

        return table

    def _generate_isa_overview(self, general: dict[str, Any]) -> str:
        """Generate the ISA Overview subsection."""
        rows = []

        if general.get('description'):
            rows.append(('Description', general['description']))

        if general.get('isa_name'):
            rows.append(('ISA Name', f"`{general['isa_name']}`"))

        if general.get('isa_version'):
            rows.append(('Version', str(general['isa_version'])))

        extension = general.get('file_extension', 'asm')
        if extension:
            rows.append(('File Extension', f'*.{extension}'))

        if not rows:
            return ''

        table = self._generate_attribute_table('ISA', rows)

        sections = ['### ISA Overview', table]

        if general.get('details'):
            sections.append(general['details'])

        return '\n\n'.join(sections)

    def _generate_hardware_section(self, hardware: dict[str, Any]) -> str:
        """Generate the Hardware Architecture Details subsection."""
        rows: list[tuple[str, str]] = []

        if hardware.get('address_size') is not None:
            rows.append(('Address Size', f"{hardware['address_size']} bits"))

        word_size = hardware.get('word_size', 8)
        rows.append(('Word Size', f'{word_size} bits'))

        word_segment_size = hardware.get('word_segment_size')
        if word_segment_size is not None and word_segment_size != word_size:
            rows.append(('Word Segment Size', f'{word_segment_size} bits'))

        page_size = hardware.get('page_size', 1)
        if page_size not in (None, 1):
            unit = 'addresses' if page_size != 1 else 'address'
            rows.append(('Page Size', f'{page_size} {unit}'))

        origin = hardware.get('origin', 0)
        origin_label = 'Default Origin Address' if origin == 0 else 'Origin Address'
        rows.append((origin_label, str(origin)))

        if not rows:
            return ''

        return self._generate_attribute_table('Hardware', rows)

    def _generate_endianness_section(self, endianness: dict[str, Any]) -> str:
        """Generate the Endianness Configuration subsection."""
        rows: list[tuple[str, str]] = []

        multi_word = endianness.get('multi_word_endianness', 'big')
        rows.append(('Multi-Word Endianness', f'`{multi_word}`'))

        intra_word = endianness.get('intra_word_endianness', 'big')
        rows.append(('Intra-Word Endianness', f'`{intra_word}`'))

        if not rows:
            return ''

        return self._generate_attribute_table('Endianness', rows)

    def _generate_string_section(self, string_config: dict[str, Any]) -> str:
        """Generate the String and Data Handling subsection."""
        rows: list[tuple[str, str]] = []

        cstr_term = string_config.get('cstr_terminator', 0)
        rows.append(('C-String Terminator', str(cstr_term)))

        embedded_strings = string_config.get('allow_embedded_strings', False)
        rows.append(('Embedded Strings Allowed', 'Enabled' if embedded_strings else 'Disabled'))

        byte_packing = string_config.get('string_byte_packing', False)
        rows.append(('String Byte Packing', 'Enabled' if byte_packing else 'Disabled'))

        if byte_packing:
            fill = string_config.get('string_byte_packing_fill', 0)
            rows.append(('String Byte Packing Fill', str(fill)))

        if not rows:
            return ''

        return self._generate_attribute_table('String Handling', rows)

    def _generate_registers_section(self, registers: list[dict[str, Any]]) -> str:
        """Generate the Register Set subsection."""
        if not registers:
            return ''

        has_title = any(reg.get('title') for reg in registers)
        has_description = any((reg.get('description') or reg.get('details')) for reg in registers)
        has_size = any(reg.get('size') is not None for reg in registers)

        headers = ['Symbol']
        alignments = ['left']
        if has_title:
            headers.append('Title')
            alignments.append('left')
        if has_description:
            headers.append('Description')
            alignments.append('left')
        if has_size:
            headers.append('Bit Size')
            alignments.append('right')

        rows: list[list[str]] = []

        for register in registers:
            symbol_value = register.get('name')
            symbol = f'`{symbol_value}`' if symbol_value is not None else ''
            row = [symbol]

            if has_title:
                row.append(register.get('title') or '')

            if has_description:
                description_value = register.get('description') or ''
                description = str(description_value).replace('\n', '<br>') if description_value else ''
                details = register.get('details')
                if details:
                    details_text = str(details).replace('\n', '<br>')
                    description = f'{description}<br><br>{details_text}' if description else details_text
                row.append(description)

            if has_size:
                size = register.get('size')
                bit_size = '' if size is None else str(size)
                row.append(bit_size)

            rows.append(row)

        table = self._generate_markdown_table(headers, rows, column_alignments=alignments)
        if not table:
            return ''

        return '### Register Set\n\n' + table

    def _generate_compatibility_section(self, general: dict[str, Any]) -> str:
        """Generate the Compatibility subsection."""
        min_version = general.get('min_version')
        if not min_version:
            return ''

        return f'### Compatibility\n\n**Minimum BespokeASM Version:** {min_version}'

    def _generate_addressing_modes_section(self, addressing_modes: list[dict[str, str]]) -> str:
        """Generate the Addressing Modes subsection."""
        if not addressing_modes:
            return ''

        sections = ['### Addressing Modes']

        # Prepare table data
        headers = ['Mode', 'Description', 'Details']
        rows = []

        for mode in addressing_modes:
            details = mode.get('details', '').replace('\n', '<br>') if mode.get('details') else ''
            description = mode.get('description', '').replace('\n', '<br>')
            mode_name = mode.get('name', '')
            mode_cell = f'`{mode_name}`' if mode_name else ''
            rows.append([mode_cell, description, details])

        # Generate optimized table
        table = self._generate_markdown_table(headers, rows)
        if table:
            sections.append(table)

        return '\n\n'.join(sections)

    def _generate_flags_section(self, flags: list[dict[str, str]]) -> str:
        """Generate the Flags subsection."""
        if not flags:
            return ''

        sections = ['### Flags']

        # Prepare table data
        headers = ['Name', 'Symbol', 'Description', 'Details']
        rows = []

        for flag in flags:
            symbol = flag.get('symbol', '') if flag.get('symbol') else ''
            if symbol:
                symbol = f'`{symbol}`'
            details = flag.get('details', '').replace('\n', '<br>') if flag.get('details') else ''
            description = flag.get('description', '').replace('\n', '<br>')
            rows.append([flag['name'], symbol, description, details])

        # Generate optimized table
        table = self._generate_markdown_table(headers, rows)
        if table:
            sections.append(table)

        return '\n\n'.join(sections)

    def _generate_general_examples_section(self, examples: list[dict[str, str]]) -> str:
        """Generate the Examples subsection."""
        if not examples:
            return ''

        sections = ['### Examples']

        for example in examples:
            example_sections = []

            if example.get('description'):
                example_sections.append(f"#### {example['description']}")

            if example.get('details'):
                example_sections.append(example['details'])

            if example.get('code'):
                example_sections.append(f"```assembly\n{example['code']}\n```")

            if example_sections:
                sections.append('\n\n'.join(example_sections))

        return '\n\n'.join(sections)

    def _generate_instructions_section(self) -> str:
        """Generate the instructions section organized by category."""
        sections = ['# Instructions']

        # Get instructions organized by category
        categories = self.doc_model.get_instructions_by_category()

        # Sort categories alphabetically
        for category in sorted(categories.keys()):
            sections.append(self._generate_category_section(category, categories[category]))

        return '\n\n'.join(sections)

    def _generate_category_section(self, category: str, instructions: list[str]) -> str:
        """
        Generate a category section with its instructions.

        Args:
            category: The category name
            instructions: List of instruction names in this category

        Returns:
            The markdown content for this category
        """
        sections = [f'## {category.title()}']

        for instruction in instructions:
            instruction_doc = self.doc_model.instruction_docs[instruction]
            sections.append(self._generate_instruction_documentation(instruction, instruction_doc))

        return '\n\n'.join(sections)

    def _generate_instruction_documentation(self, instruction_name: str, instruction_doc: dict[str, Any]) -> str:
        """
        Generate documentation for a single instruction.

        Args:
            instruction_name: The instruction mnemonic
            instruction_doc: The instruction documentation data

        Returns:
            The markdown content for this instruction
        """
        sections = []

        # Instruction header
        mnemonic = instruction_name.upper()
        header = f'### `{mnemonic}`'
        if instruction_doc.get('title'):
            header += f" : {instruction_doc['title']}"
        sections.append(header)

        documented = instruction_doc.get('documented', True)

        if not documented:
            sections.append('*Documentation not provided.*')

        # Details
        if instruction_doc.get('details'):
            sections.append(instruction_doc['details'])

        # Modifies table
        if instruction_doc.get('modifies'):
            sections.append(self._generate_modifies_table(instruction_doc['modifies']))

        # Examples
        if instruction_doc.get('examples'):
            sections.append(self._generate_instruction_examples(instruction_doc['examples']))

        return '\n\n'.join(sections)

    def _generate_modifies_table(self, modifies: list[dict[str, str]]) -> str:
        """Generate a table of what the instruction modifies."""
        if not modifies:
            return ''

        sections = ['#### Modifies']

        # Prepare table data
        headers = ['Type', 'Target', 'Description', 'Details']
        rows = []

        for modify in modifies:
            modify_type = modify.get('type', '').title()
            target = modify.get('target', '')
            description = modify.get('description', '').replace('\n', '<br>')
            details = modify.get('details', '').replace('\n', '<br>') if modify.get('details') else ''
            rows.append([modify_type, target, description, details])

        # Generate optimized table
        table = self._generate_markdown_table(headers, rows)
        if table:
            sections.append(table)

        return '\n\n'.join(sections)

    def _generate_instruction_examples(self, examples: list[dict[str, str]]) -> str:
        """Generate examples for an instruction."""
        if not examples:
            return ''

        sections = ['#### Examples']

        for example in examples:
            example_sections = []

            if example.get('description'):
                example_sections.append(f"##### {example['description']}")

            if example.get('details'):
                example_sections.append(example['details'])

            if example.get('code'):
                example_sections.append(f"```assembly\n{example['code']}\n```")

            if example_sections:
                sections.append('\n\n'.join(example_sections))

        return '\n\n'.join(sections)
