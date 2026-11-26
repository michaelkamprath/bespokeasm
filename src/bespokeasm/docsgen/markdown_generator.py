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

        # Predefined memory zones section
        memory_zones_section = self._generate_predefined_memory_zones_section()
        if memory_zones_section:
            sections.append(memory_zones_section)

        # Predefined constants section
        constants_section = self._generate_predefined_constants_section()
        if constants_section:
            sections.append(constants_section)

        # Predefined data section
        data_section = self._generate_predefined_data_section()
        if data_section:
            sections.append(data_section)

        # Operand sets section
        if getattr(self.doc_model, 'operand_sets', None):
            operand_sets_section = self._generate_operand_sets_section()
            if operand_sets_section:
                sections.append(operand_sets_section)

        # Flow counters section
        flow_counters = getattr(self.doc_model, 'flow_counters', None)
        if isinstance(flow_counters, list) and flow_counters:
            sections.append(self._generate_flow_counters_section())

        # Output formats and annotations sections
        output_formats = getattr(self.doc_model, 'output_formats', None)
        if isinstance(output_formats, list) and output_formats:
            sections.append(self._generate_output_formats_section())
        annotations = getattr(self.doc_model, 'annotations', None)
        if isinstance(annotations, list) and self._declared_annotations():
            sections.append(self._generate_annotations_section())

        # Instructions section
        if self.doc_model.instruction_docs:
            sections.append(self._generate_instructions_section())
        elif self.verbose:
            click.echo('Warning: No instruction documentation found')

        # Macros section
        macro_docs = getattr(self.doc_model, 'macro_docs', {})
        if macro_docs:
            sections.append(self._generate_macros_section())

        # Examples section
        general_examples = getattr(self.doc_model, 'general_docs', {}).get('examples') or []
        if general_examples:
            sections.append(self._generate_examples_section(general_examples))

        content = '\n\n'.join(filter(None, sections))
        return f'{content}\n' if content else ''

    def _generate_flow_counters_section(self) -> str:
        """Generate the flow-counter classes and their public contracts."""
        sections = [
            '# Flow Counters',
            (
                'See [Flow Counters]'
                '(https://github.com/michaelkamprath/bespokeasm/wiki/'
                'Assembly-Language-Syntax#flow-counters) '
                'for the assembly-language syntax and general feature '
                'documentation.'
            ),
        ]
        for counter in self.doc_model.flow_counters:
            name = counter['name']
            title = counter.get('title') or name
            heading = (
                f'## {title} (`{name}`)'
                if title != name
                else f'## {name}'
            )
            counter_sections = [heading]
            if counter.get('description'):
                counter_sections.append(str(counter['description']))

            properties = self._generate_markdown_table(
                ['Property', 'Value'],
                [
                    [str(property_name), str(value)]
                    for property_name, value in counter.get(
                        'properties',
                        [],
                    )
                ],
            )
            if properties:
                counter_sections.append(properties)

            entry_modes = counter.get('entry_modes', [])
            if entry_modes:
                mode_table = self._generate_markdown_table(
                    [
                        'Mode',
                        'Initial Value',
                        'Exit Value',
                        'Description',
                    ],
                    [
                        [
                            f"`{mode['name']}`",
                            str(mode['init']),
                            str(mode['exit']),
                            str(mode.get('description', '')),
                        ]
                        for mode in entry_modes
                    ],
                )
                counter_sections.extend(['### Entry Modes', mode_table])

            terminals = counter.get('terminal_instructions', [])
            if terminals:
                terminal_table = self._generate_markdown_table(
                    ['Instruction', 'Reconciliation'],
                    [
                        [
                            f"`{terminal['instruction']}`",
                            terminal['order'],
                        ]
                        for terminal in terminals
                    ],
                )
                counter_sections.extend([
                    '### Terminal Instructions',
                    terminal_table,
                ])

            sections.append('\n\n'.join(counter_sections))
        return '\n\n'.join(sections)

    @staticmethod
    def _format_list(formats: list[str]) -> str:
        """`-t a`, `-t b` or `-t c`."""
        items = [f'`-t {name}`' for name in formats]
        if len(items) <= 1:
            return ''.join(items)
        return f'{", ".join(items[:-1])} or {items[-1]}'

    def _with_format_note(self, description: str | None, formats: list[str] | None) -> str | None:
        """A predefined item that only output formats define says which ones."""
        if not formats:
            return description
        note = f'*Only with {self._format_list(formats)}.*'
        return f'{description} {note}' if description else note

    def _generate_output_formats_section(self) -> str:
        """Every -t value this ISA accepts."""
        sections = [
            '# Output Formats',
            (
                'Select a pretty-print format with `-p -t <format>`. The built-in formats are '
                'available for every instruction set; the others are defined by this configuration. See '
                '[Output Formats](https://github.com/michaelkamprath/bespokeasm/wiki/Output-Formats).'
            ),
        ]
        rows = []
        for output_format in self.doc_model.output_formats:
            # How the configuration builds a format (a shared set) is for config authors, not readers.
            source = 'built-in' if output_format['builtin'] else 'configuration'
            predefined = ', '.join(f'`{name}`' for name in output_format.get('predefined') or [])
            annotations = ', '.join(f'`{name}`' for name in output_format.get('annotations') or [])
            rows.append([
                f"`{output_format['name']}`",
                self._format_description(output_format),
                source,
                annotations,
                predefined,
            ])
        sections.append(self._generate_markdown_table(
            ['Format', 'Description', 'Defined By', 'Exports Annotations', 'Predefines'],
            rows,
            column_alignments=['left'] * 5,
        ))
        return '\n\n'.join(sections)

    def _format_description(self, output_format: dict[str, Any]) -> str:
        """The format's description. A word-size requirement that this ISA meets says nothing, so
        only a requirement it does not meet is mentioned: the format can never be selected."""
        description = output_format.get('description') or ''
        required = output_format.get('requires_word_size')
        word_size = getattr(self.doc_model, 'general_docs', {}).get('hardware', {}).get('word_size')
        if required and word_size is not None and required != word_size:
            note = f'*Cannot be used with this ISA: it needs {required}-bit words.*'
            description = f'{description} {note}' if description else note
        return description

    def _generate_annotations_section(self) -> str:
        """The annotation namespaces this configuration declares."""
        sections = [
            '# Annotations',
            (
                'Source attaches an annotation to a label or constant with '
                '`#annotate <namespace> key=value ...` on the line directly above its definition. '
                'Every instruction set also has the `listing` namespace, which shapes `-t listing` '
                'output. See [Annotations](https://github.com/michaelkamprath/bespokeasm/wiki/Annotations).'
            ),
        ]
        for namespace in self._declared_annotations():
            parts = [f"## `{namespace['name']}`", *self._namespace_body(namespace, heading_level=2)]
            sections.append('\n\n'.join(parts))
        return '\n\n'.join(sections)

    def _declared_annotations(self) -> list[dict[str, Any]]:
        return [namespace for namespace in self.doc_model.annotations if not namespace.get('builtin')]

    def _namespace_body(self, namespace: dict[str, Any], heading_level: int, hover: bool = False) -> list[str]:
        """A namespace's description, where it applies, its arguments, its constraints and its
        examples. ``heading_level`` is the level of the namespace's own heading. ``hover`` lists
        the arguments one per line instead of in a table, which a hover is too narrow for; an
        argument's own hover has its values' descriptions."""
        singular_unit, plural_unit = self._hover_size_units()
        parts = []
        if namespace.get('description'):
            parts.append(str(namespace['description']))
        kinds = ' and '.join(f'{kind}s' for kind in namespace['applies_to'])
        scopes = namespace['scopes']
        scope_text = 'any scope' if len(scopes) == 3 else f"{' or '.join(scopes)} scope"
        parts.append(f'Applies to {kinds}, in {scope_text}.')
        if namespace.get('verbatim'):
            verbatim = f"Accepts `#verbatim {namespace['name']}` text blocks"
            description = namespace['verbatim'].get('description')
            parts.append(f'{verbatim}: {description}' if description else f'{verbatim}.')
            verbatim_parts = namespace['verbatim'].get('parts') or []
            if verbatim_parts:
                parts.append('A block can name a part, which an output format places separately:')
                parts.append('\n'.join(
                    f"- `#verbatim {namespace['name']} {part['name']}`"
                    + (f": {part['description']}" if part.get('description') else '')
                    for part in verbatim_parts
                ))
        if hover and namespace['arguments']:
            parts.append('**Arguments:**')
            parts.append('\n'.join(self._argument_line(argument) for argument in namespace['arguments']))
        rows = []
        for argument in namespace['arguments'] if not hover else []:
            rows.append([
                f"`{argument['name']}`",
                self._argument_description(argument),
                argument['type'],
                self._argument_values(argument),
                self._argument_presence(argument),
                f"`{argument['default']}`" if argument['has_default'] else '',
            ])
        if rows:
            parts.append(self._generate_markdown_table(
                ['Argument', 'Description', 'Type', 'Values', 'Presence', 'Default'],
                rows,
                column_alignments=['left'] * 6,
            ))
        data_size = namespace.get('data_size')
        if data_size:
            parts.append(self._data_size_text(data_size, singular_unit, plural_unit))
        for rule in namespace.get('value_range') or []:
            parts.append(self._value_range_text(rule))
        examples = namespace.get('examples') or []
        if examples:
            parts.append(f"{'#' * (heading_level + 1)} Examples")
            for example in examples:
                if example.get('title'):
                    parts.append(f"{'#' * (heading_level + 2)} {example['title']}")
                if example.get('description'):
                    parts.append(str(example['description']))
                parts.append(f"```assembly\n{example['code']}\n```")
        return parts

    def _argument_line(self, argument: dict[str, Any]) -> str:
        """One argument as a list line: `kind`: enum (`addr`, `var`, `const`), required. Description."""
        values = (
            ', '.join(f'`{value}`' for value in argument['values']) if argument['type'] == 'enum'
            else self._argument_values(argument)
        )
        facts = [f"{argument['type']} ({values})" if values else argument['type'], self._argument_presence(argument)]
        if argument['has_default']:
            facts.append(f"default `{argument['default']}`")
        line = f"- `{argument['name']}`: {', '.join(facts)}."
        description = self._argument_description(argument)
        return f'{line} {description}' if description else line

    @staticmethod
    def _argument_description(argument: dict[str, Any]) -> str:
        return argument.get('description') or ''

    @staticmethod
    def _condition_text(tests: list[tuple[str, list[str]]] | None) -> str:
        """`kind` is `var` or `const`, and ..."""
        parts = []
        for key, values in tests or []:
            quoted = [f'`{value}`' for value in values]
            choice = quoted[0] if len(quoted) == 1 else f"{', '.join(quoted[:-1])} or {quoted[-1]}"
            parts.append(f'`{key}` is {choice}')
        return ' and '.join(parts)

    def generate_annotation_hover_docs(self) -> dict[str, dict[str, Any]]:
        """Hover markdown for each annotation namespace and each of its arguments, keyed by
        namespace: ``{'doc': ..., 'arguments': {name: ...}, 'values': [...], 'parts': {name: ...}}``,
        where ``values`` are the namespace's enum values and ``parts`` its ``#verbatim`` parts.
        Includes the framework's ``listing``."""
        docs: dict[str, dict[str, Any]] = {}
        singular_unit, plural_unit = self._hover_size_units()
        for namespace in getattr(self.doc_model, 'annotations', None) or []:
            name = namespace['name']
            heading = 'Framework Annotation' if namespace.get('builtin') else 'Annotation'
            namespace_doc = '\n\n'.join([
                f'### `{name}` : {heading}', '---', *self._namespace_body(namespace, heading_level=3, hover=True),
            ])
            arguments = {
                argument['name']: self._argument_hover(namespace, argument, singular_unit, plural_unit)
                for argument in namespace['arguments']
            }
            # The enum values, so an editor can color them in a hover as the syntax does.
            values = sorted({
                str(value) for argument in namespace['arguments'] if argument['type'] == 'enum'
                for value in argument['values']
            })
            parts = {
                part['name']: self._verbatim_part_hover(name, part)
                for part in (namespace.get('verbatim') or {}).get('parts') or []
            }
            docs[name] = {'doc': namespace_doc, 'arguments': arguments, 'values': values, 'parts': parts}
        return docs

    @staticmethod
    def _verbatim_part_hover(namespace_name: str, part: dict[str, Any]) -> str:
        sections = [f"### `{part['name']}` : `#verbatim {namespace_name}` Part", '---']
        sections.append(
            str(part['description']) if part.get('description')
            else 'An output format places these blocks separately.'
        )
        return '\n\n'.join(sections)

    def _argument_hover(
        self, namespace: dict[str, Any], argument: dict[str, Any], singular_unit: str, plural_unit: str,
    ) -> str:
        sections = [f"### `{argument['name']}` : `{namespace['name']}` Annotation Argument", '---']
        if argument.get('description'):
            sections.append(str(argument['description']))
        rows = [
            ('Type', argument['type']),
            ('Values', self._argument_values(argument, separator=', ') if not argument.get('value_descriptions')
             else ', '.join(f'`{value}`' for value in argument['values'])),
            ('Presence', self._argument_presence(argument)),
            ('Default', f"`{argument['default']}`" if argument['has_default'] else ''),
        ]
        table = self._generate_markdown_table(
            ['Attribute', 'Value'],
            [[f'**{label}**', value] for label, value in rows if value],
            column_alignments=['left', 'left'],
        )
        if table:
            sections.append(table)
        if argument.get('value_descriptions'):
            sections.append('\n'.join(f'- `{value}`: {text}' for value, text in argument['value_descriptions']))
        data_size = namespace.get('data_size')
        if data_size and argument['name'] in data_size.get('arguments', []):
            sections.append(self._data_size_text(data_size, singular_unit, plural_unit))
        for rule in namespace.get('value_range') or []:
            if argument['name'] in rule.get('arguments', []):
                sections.append(self._value_range_text(rule))
        return '\n\n'.join(sections)

    @staticmethod
    def _argument_values(argument: dict[str, Any], separator: str = '<br>') -> str:
        if argument['type'] == 'enum':
            described = dict(argument.get('value_descriptions') or [])
            if described:
                return separator.join(
                    f'`{value}`: {described[value]}' if value in described else f'`{value}`'
                    for value in argument['values']
                )
            return ', '.join(f'`{value}`' for value in argument['values'])
        if argument['type'] == 'integer':
            low, high = argument.get('minimum'), argument.get('maximum')
            if low is not None and high is not None:
                return f'{low} to {high}'
            if low is not None:
                return f'{low} or more'
            if high is not None:
                return f'{high} or less'
            return ''
        if argument['type'] == 'string' and argument.get('pattern'):
            return f"matches `{argument['pattern']}`"
        if argument['type'] == 'symbol':
            return 'a label or constant'
        if argument['type'] == 'boolean':
            return 'a bare flag, or `true`/`false`'
        return ''

    @classmethod
    def _argument_presence(cls, argument: dict[str, Any]) -> str:
        parts = []
        if argument['required']:
            parts.append('required')
        elif argument.get('required_when'):
            parts.append(f"required when {cls._condition_text(argument['required_when'])}")
        else:
            parts.append('optional')
        if argument.get('allowed_when'):
            parts.append(f"only when {cls._condition_text(argument['allowed_when'])}")
        return '; '.join(parts)

    def _data_size_text(self, rule: dict[str, Any], singular_unit: str, plural_unit: str) -> str:
        """The data-size constraint: one element's size, then how many elements."""
        when = f" when {self._condition_text(rule['when'])}" if rule.get('when') else ''
        if rule.get('selector'):
            sizes = ', '.join(
                f"`{value}` {self._format_quantity_with_units(words, singular_unit, plural_unit)}"
                if words is not None else f'`{value}` not allowed'
                for value, words in rule['table']
            )
            size_text = f"one element's size depends on `{rule['selector']}`: {sizes}"
        else:
            size_text = f"{self._format_quantity_with_units(rule.get('fixed'), singular_unit, plural_unit)}"
        text = f"**Data size** (a label's data, {when.strip() or 'always'}): {size_text}."
        times = rule.get('times')
        if times:
            ways = [f'`{times}` elements (1 when absent)']
            if rule.get('infer_times'):
                ways.append(
                    f"with `{rule['infer_times']}`, as many elements as the data holds"
                )
            if rule.get('terminated_when'):
                ways.append(
                    f"when {self._condition_text(rule['terminated_when'])}, as many as the data holds "
                    f'before its string terminator, which must end the data'
                )
            text += ' The data holds ' + '; '.join(ways) + '.'
        return text

    def _value_range_text(self, rule: dict[str, Any]) -> str:
        when = f" when {self._condition_text(rule['when'])}" if rule.get('when') else ''
        if rule.get('selector'):
            ranges = ', '.join(
                f'`{value}` {limits[0]} to {limits[1]}' if limits is not None else f'`{value}` not allowed'
                for value, limits in rule['table']
            )
            range_text = f"by `{rule['selector']}`: {ranges}"
        else:
            fixed = rule.get('fixed')
            range_text = f'{fixed[0]} to {fixed[1]}' if fixed else ''
        return f"**Value range** (a constant's value, {when.strip() or 'always'}): {range_text}."

    def generate_instruction_markdown(
        self,
        instruction_name: str,
        instruction_doc: dict[str, Any],
        include_missing_doc_notice: bool = True,
        table_style: str = 'markdown',
        add_header_rule: bool = False
    ) -> str:
        """
        Generate markdown documentation for a single instruction.

        Args:
            instruction_name: The instruction mnemonic
            instruction_doc: The instruction documentation data
            include_missing_doc_notice: Whether to include a missing doc notice
            table_style: "markdown" or "ascii" for table rendering
            add_header_rule: Whether to add a horizontal rule after the header

        Returns:
            The markdown content for the instruction
        """
        return self._generate_instruction_documentation(
            instruction_name,
            instruction_doc,
            include_missing_doc_notice=include_missing_doc_notice,
            table_style=table_style,
            add_header_rule=add_header_rule
        )

    def generate_predefined_hover_docs(self) -> dict[str, dict[str, str]]:
        """
        Generate hover markdown for documented predefined entities.

        Returns:
            Dictionary with hover docs grouped by predefined category.
        """
        return {
            'constants': self._generate_predefined_constant_hover_docs(),
            'data': self._generate_predefined_data_hover_docs(),
            'memory_zones': self._generate_predefined_memory_zone_hover_docs(),
        }

    def generate_register_hover_docs(self) -> dict[str, str]:
        """
        Generate hover markdown for documented registers.

        Returns:
            Dictionary mapping register name to hover markdown.
            Only registers with documentation are included.
        """
        registers = getattr(self.doc_model, 'general_docs', {}).get('registers', [])
        singular_unit, plural_unit = self._hover_size_units()

        docs: dict[str, str] = {}
        for register in registers:
            title = register.get('title')
            description = register.get('description')
            if not title and not description:
                continue

            name = register.get('name')
            if not name:
                continue

            rows: list[tuple[str, str]] = []
            size = register.get('size')
            if size is not None:
                rows.append(('Size', f'{size} bits'))

            display_title = title or 'Register'
            docs[name] = self._generate_predefined_hover_markdown(
                name,
                display_title,
                description,
                rows
            )

        return docs

    def _generate_predefined_constant_hover_docs(self) -> dict[str, str]:
        constants = getattr(self.doc_model, 'predefined_constants', None) or []
        address_size = (
            getattr(self.doc_model, 'general_docs', {})
            .get('hardware', {})
            .get('address_size')
        )
        hex_width = self._hex_width_for_address_size(address_size)
        singular_unit, plural_unit = self._hover_size_units()

        docs: dict[str, str] = {}
        for constant in constants:
            if not constant.get('documented', False):
                continue

            name = constant.get('name')
            if not name:
                continue

            value_text = self._format_hex_value(constant.get('value'), hex_width)
            rows: list[tuple[str, str]] = []
            if value_text:
                rows.append(('Value', f'`{value_text}`'))

            if constant.get('format_values'):
                rows[-1:] = [('Value', ', '.join(
                    f'`{self._format_hex_value(format_value, hex_width)}` (`{format_name}`)'
                    for format_name, format_value in constant['format_values'].items()
                ))]

            const_type = constant.get('type')
            if const_type:
                rows.append(('Type', f'`{const_type}`'))

            if const_type == 'variable' and constant.get('size') is not None:
                size_text = self._format_quantity_with_units(constant.get('size'), singular_unit, plural_unit)
                if size_text:
                    rows.append(('Size', size_text))

            if constant.get('formats'):
                rows.append(('Only with', self._format_list(constant['formats'])))

            description = constant.get('description')
            docs[name] = self._generate_predefined_hover_markdown(
                name,
                'Predefined Constant',
                description,
                rows
            )

        return docs

    def _generate_predefined_data_hover_docs(self) -> dict[str, str]:
        data_blocks = getattr(self.doc_model, 'predefined_data', None) or []
        hardware = getattr(self.doc_model, 'general_docs', {}).get('hardware', {})
        address_width = self._hex_width_for_address_size(hardware.get('address_size'))
        value_width = self._hex_width_for_address_size(hardware.get('word_size'))
        singular_unit, plural_unit = self._hover_size_units()

        docs: dict[str, str] = {}
        for data_block in data_blocks:
            if not data_block.get('documented', False):
                continue

            name = data_block.get('name')
            if not name:
                continue

            rows: list[tuple[str, str]] = []

            address_text = self._format_hex_value(data_block.get('address'), address_width)
            if address_text:
                rows.append(('Address', f'`{address_text}`'))

            size_text = self._format_quantity_with_units(data_block.get('size'), singular_unit, plural_unit)
            if size_text:
                rows.append(('Size', size_text))

            fill_value = data_block.get('value')
            if fill_value is not None:
                fill_text = self._format_hex_value(fill_value, value_width)
                if fill_text:
                    rows.append(('Fill Value', f'`{fill_text}`'))

            description = data_block.get('description')
            docs[name] = self._generate_predefined_hover_markdown(
                name,
                'Predefined Data Block',
                description,
                rows
            )

        return docs

    def _generate_predefined_memory_zone_hover_docs(self) -> dict[str, str]:
        memory_zones = getattr(self.doc_model, 'predefined_memory_zones', None) or []
        address_size = (
            getattr(self.doc_model, 'general_docs', {})
            .get('hardware', {})
            .get('address_size')
        )
        hex_width = self._hex_width_for_address_size(address_size)

        docs: dict[str, str] = {}
        for zone in memory_zones:
            if not zone.get('documented', False):
                continue

            name = zone.get('name')
            if not name:
                continue

            rows: list[tuple[str, str]] = []

            start_text = self._format_hex_value(zone.get('start'), hex_width)
            if start_text:
                rows.append(('Start', f'`{start_text}`'))

            end_text = self._format_hex_value(zone.get('end'), hex_width)
            if end_text:
                rows.append(('End', f'`{end_text}`'))

            if zone.get('formats'):
                rows.append(('Only with', self._format_list(zone['formats'])))

            zone_title = zone.get('title') or 'Predefined Memory Zone'
            description = zone.get('description')
            docs[name] = self._generate_predefined_hover_markdown(
                name,
                str(zone_title),
                description,
                rows
            )

        return docs

    def _generate_predefined_hover_markdown(
        self,
        name: str,
        title: str,
        description: str | None,
        rows: list[tuple[str, str]],
    ) -> str:
        sections = [f'### `{name}` : {title}', '---']
        if description:
            sections.append(str(description))

        table_rows = [[f'**{label}**', value] for label, value in rows if value]
        table = self._generate_markdown_table(
            ['Attribute', 'Value'],
            table_rows,
            column_alignments=['left', 'left']
        )
        if table:
            sections.append(table)

        return '\n\n'.join(sections)

    def _hover_size_units(self) -> tuple[str, str]:
        """
        Return singular/plural size units used for hover text.

        Hover sizing follows user-facing convention:
        - 8-bit words => bytes
        - non-8-bit words => words
        """
        word_size = (
            getattr(self.doc_model, 'general_docs', {})
            .get('hardware', {})
            .get('word_size', 8)
        )
        try:
            if int(word_size) == 8:
                return 'byte', 'bytes'
        except (TypeError, ValueError):
            pass
        return 'word', 'words'

    @staticmethod
    def _format_quantity_with_units(value: Any, singular_unit: str, plural_unit: str) -> str:
        if value is None:
            return ''

        try:
            quantity = int(value)
            unit = singular_unit if quantity == 1 else plural_unit
            return f'{quantity} {unit}'
        except (TypeError, ValueError):
            text = str(value).strip()
            if not text:
                return ''
            return f'{text} {plural_unit}'

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

    @staticmethod
    def _format_hex_value(value: Any, width: int | None = None) -> str:
        """Format a numeric value as hexadecimal for documentation output."""
        if value is None:
            return ''

        if isinstance(value, str):
            raw = value.strip()
            if not raw:
                return ''
            try:
                number = int(raw, 0)
            except ValueError:
                return raw
            return MarkdownGenerator._format_hex_number(number, width)

        try:
            number = int(value)
        except (TypeError, ValueError):
            return str(value)

        return MarkdownGenerator._format_hex_number(number, width)

    @staticmethod
    def _format_hex_number(number: int, width: int | None) -> str:
        """Format a signed integer as hex with optional zero padding."""
        abs_value = abs(number)
        if width:
            hex_body = f'{abs_value:0{width}X}'
        else:
            hex_body = f'{abs_value:X}'
        prefix = f'0x{hex_body}'
        return prefix if number >= 0 else f'-{prefix}'

    @staticmethod
    def _hex_width_for_address_size(address_size: Any) -> int | None:
        """Calculate hex digit width for an address size, if aligned to nibbles."""
        if address_size is None:
            return None
        try:
            bits = int(address_size)
        except (TypeError, ValueError):
            return None
        if bits <= 0 or bits % 4 != 0:
            return None
        return bits // 4

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

        expression_section = self._generate_expression_syntax_section(general.get('expression_syntax', {}))
        if expression_section:
            table_sections.append(expression_section)

        aliases_section = self._generate_directive_aliases_section(general.get('directive_aliases', {}))
        if aliases_section:
            table_sections.append(aliases_section)

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

            table = self._generate_operand_set_table(operand_set.get('operands', []))
            if table:
                subsection_parts.append(table)
            elif self.verbose:
                click.echo(f'Warning: Operand set "{operand_set.get("key")}" has no operand entries.')

            sections.append('\n\n'.join(filter(None, subsection_parts)))

        return '\n\n'.join(sections)

    def _generate_predefined_memory_zones_section(self) -> str:
        """Generate the predefined memory zones section of the documentation."""
        memory_zones = getattr(self.doc_model, 'predefined_memory_zones', None) or []
        if not memory_zones:
            return ''

        address_size = (
            getattr(self.doc_model, 'general_docs', {})
            .get('hardware', {})
            .get('address_size')
        )
        hex_width = self._hex_width_for_address_size(address_size)

        headers = ['Name', 'Start', 'End', 'Title', 'Description']
        alignments = ['left', 'left', 'left', 'left', 'left']
        rows: list[list[str]] = []

        for zone in memory_zones:
            name = zone.get('name') or ''
            name_cell = f'`{name}`' if name else ''

            start = zone.get('start')
            end = zone.get('end')
            start_hex = self._format_hex_value(start, hex_width)
            end_hex = self._format_hex_value(end, hex_width)

            documented = zone.get('documented', False)
            title = None
            description = None
            if documented:
                title = zone.get('title') or name
                description = zone.get('description')
            description = self._with_format_note(description, zone.get('formats'))

            rows.append([
                name_cell,
                start_hex,
                end_hex,
                title or '',
                description or ''
            ])

        table = self._generate_markdown_table(headers, rows, column_alignments=alignments)
        if not table:
            return ''

        return '\n\n'.join(['## Predefined Memory Zones', table])

    def _generate_predefined_constants_section(self) -> str:
        """Generate the predefined constants section of the documentation."""
        constants = getattr(self.doc_model, 'predefined_constants', None) or []
        if not constants:
            return ''

        address_size = (
            getattr(self.doc_model, 'general_docs', {})
            .get('hardware', {})
            .get('address_size')
        )
        hex_width = self._hex_width_for_address_size(address_size)

        headers = ['Name', 'Value', 'Type', 'Size (Words)', 'Description']
        alignments = ['left', 'left', 'left', 'left', 'left']
        rows: list[list[str]] = []

        for constant in constants:
            name = constant.get('name') or ''
            name_cell = f'`{name}`' if name else ''

            value = constant.get('value')
            value_hex = self._format_hex_value(value, hex_width)
            if constant.get('format_values'):
                value_hex = ', '.join(
                    f'{self._format_hex_value(format_value, hex_width)} (`{format_name}`)'
                    for format_name, format_value in constant['format_values'].items()
                )

            documented = constant.get('documented', False)
            const_type = None
            size = None
            description = None
            if documented:
                const_type = constant.get('type')
                if const_type == 'variable':
                    size = constant.get('size')
                description = constant.get('description')
            description = self._with_format_note(description, constant.get('formats'))

            rows.append([
                name_cell,
                value_hex,
                const_type or '',
                str(size) if size is not None else '',
                description or ''
            ])

        table = self._generate_markdown_table(headers, rows, column_alignments=alignments)
        if not table:
            return ''

        return '\n\n'.join(['## Predefined Constants', table])

    def _generate_predefined_data_section(self) -> str:
        """Generate the predefined data section of the documentation."""
        data_blocks = getattr(self.doc_model, 'predefined_data', None) or []
        if not data_blocks:
            return ''

        hardware = getattr(self.doc_model, 'general_docs', {}).get('hardware', {})
        address_size = hardware.get('address_size')
        word_size = hardware.get('word_size')
        address_width = self._hex_width_for_address_size(address_size)
        value_width = self._hex_width_for_address_size(word_size)

        headers = ['Name', 'Address', 'Size (Bytes)', 'Value', 'Description']
        alignments = ['left', 'left', 'left', 'left', 'left']
        rows: list[list[str]] = []

        for data_block in data_blocks:
            name = data_block.get('name') or ''
            name_cell = f'`{name}`' if name else ''

            address = data_block.get('address')
            address_hex = self._format_hex_value(address, address_width)

            size = data_block.get('size')
            size_cell = str(size) if size is not None else ''

            value = data_block.get('value')
            value_hex = self._format_hex_value(value, value_width)

            documented = data_block.get('documented', False)
            description = data_block.get('description') if documented else None

            rows.append([
                name_cell,
                address_hex,
                size_cell,
                value_hex,
                description or ''
            ])

        table = self._generate_markdown_table(headers, rows, column_alignments=alignments)
        if not table:
            return ''

        return '\n\n'.join(['## Predefined Data', table])

    def _generate_operand_set_table(self, operands: list[dict[str, Any]]) -> str:
        """Generate the per-operand table for an operand set."""
        if not operands:
            return ''

        addressing_modes = getattr(self.doc_model, 'general_docs', {}).get('addressing_modes') or []
        addressing_mode_header = '[Addressing Mode](#addressing-modes)' if addressing_modes else 'Addressing Mode'

        headers = ['Operand', 'Syntax', 'Value', addressing_mode_header, 'Description']
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

            value_text = operand.get('value') or ''
            if value_text:
                value_text = str(value_text).replace('\n', '<br>')
            value_cell = value_text

            mode_value = operand.get('mode') or ''
            if operand.get('mode_from_doc') and mode_value:
                mode_cell = f'`{mode_value}`'
            else:
                mode_cell = mode_value
            description = operand.get('description') or ''
            if description:
                description = description.replace('\n', '<br>')

            rows.append([operand_cell, syntax_cell, value_cell, mode_cell, description])

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

        multi_word = endianness.get('multi_word_endian', 'big')
        rows.append(('Multi-Word Endianness', f'`{multi_word}`'))

        intra_word = endianness.get('intra_word_endian', 'big')
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

    _BARE_NUMBER_BASES = {'hex': 'Hexadecimal', 'octal': 'Octal', 'binary': 'Binary'}
    _LOW_HIGH_OPERATOR_TEXT = {
        'tight': 'Low and high {unit} of the term that follows: `<label+1` is `(<label)+1`',
        'whole_expression': (
            'Low and high {unit} of everything after the operator, written at the start of an '
            'expression or parenthesis: `<label+1` is `<(label+1)`'
        ),
    }
    _CURRENT_ADDRESS_TEXT = {
        'instruction_start': "The instruction's first byte; in data, the value's own address",
        'value_address': "The address of the operand's own bytes; in data, the value's own address",
    }

    def _generate_expression_syntax_section(self, syntax: dict[str, Any]) -> str:
        """Generate the Expression Syntax subsection: only what differs from the defaults, so an
        instruction set with decimal bare numbers and no optional operators shows nothing."""
        rows: list[tuple[str, str]] = []
        base = self._BARE_NUMBER_BASES.get(str(syntax.get('default_numeric_base') or 'decimal'))
        if base:
            rows.append(('Bare Numbers', base))
        if syntax.get('low_high_operators') in self._LOW_HIGH_OPERATOR_TEXT:
            unit = 'byte' if syntax.get('word_size', 8) == 8 else f"{syntax['word_size']}-bit word"
            rows.append((
                '`<` and `>`',
                self._LOW_HIGH_OPERATOR_TEXT[syntax['low_high_operators']].format(unit=unit),
            ))
        if syntax.get('current_address') in self._CURRENT_ADDRESS_TEXT:
            rows.append(('`*`', self._CURRENT_ADDRESS_TEXT[syntax['current_address']]))
        if not rows:
            return ''
        return self._generate_attribute_table('Expression Syntax', rows)

    def _generate_directive_aliases_section(self, aliases: dict[str, str]) -> str:
        """Generate the Directive Aliases subsection: the other names this instruction set gives
        data and fill directives, such as `.word` for `.2byte`."""
        rows = [(f'`.{alias}`', f'Same as `.{target}`') for alias, target in sorted(aliases.items())]
        if not rows:
            return ''
        return self._generate_attribute_table('Directive Aliases', rows)

    def _generate_registers_section(self, registers: list[dict[str, Any]]) -> str:
        """Generate the Register Set subsection."""
        if not registers:
            return ''

        has_title = any(reg.get('title') for reg in registers)
        has_description = any(reg.get('description') for reg in registers)
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
        has_title = any(mode.get('title') for mode in addressing_modes)
        headers = ['Mode']
        if has_title:
            headers.append('Title')
        headers.append('Description')
        rows = []

        for mode in addressing_modes:
            description = mode.get('description', '').replace('\n', '<br>')
            mode_name = mode.get('name', '')
            mode_cell = f'`{mode_name}`' if mode_name else ''
            row = [mode_cell]
            if has_title:
                title = mode.get('title') or ''
                row.append(str(title).replace('\n', '<br>') if title else '')
            row.append(description)
            rows.append(row)

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
        headers = ['Name', 'Symbol', 'Description']
        rows = []

        for flag in flags:
            symbol = flag.get('symbol', '') if flag.get('symbol') else ''
            if symbol:
                symbol = f'`{symbol}`'
            description = flag.get('description', '').replace('\n', '<br>')
            rows.append([flag['name'], symbol, description])

        # Generate optimized table
        table = self._generate_markdown_table(headers, rows)
        if table:
            sections.append(table)

        return '\n\n'.join(sections)

    def _generate_examples_section(self, examples: list[dict[str, str]]) -> str:
        """Generate the Examples section."""
        if not examples:
            return ''

        sections = ['# Examples']

        for example in examples:
            example_sections = []

            if example.get('title'):
                example_sections.append(f"## {example['title']}")

            if example.get('description'):
                example_sections.append(example['description'])

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

    def _generate_macros_section(self) -> str:
        """Generate the macros section organized by category."""
        sections = ['# Macros']

        categories = self.doc_model.get_macros_by_category()
        for category in sorted(categories.keys()):
            sections.append(self._generate_category_section(
                category,
                categories[category],
                doc_map=self.doc_model.macro_docs,
                include_missing_doc_notice=False
            ))

        return '\n\n'.join(sections)

    def _generate_category_section(
        self,
        category: str,
        operations: list[str],
        doc_map: dict[str, Any] | None = None,
        include_missing_doc_notice: bool = True
    ) -> str:
        """
        Generate a category section with its instructions.

        Args:
            category: The category name
            operations: List of instruction or macro names in this category
            doc_map: Documentation map keyed by operation mnemonic

        Returns:
            The markdown content for this category
        """
        doc_map = doc_map or self.doc_model.instruction_docs
        sections = [f'## {category.title()}']

        num_instructions = len(operations)
        for index, operation in enumerate(operations):
            instruction_doc = doc_map[operation]
            sections.append(
                self._generate_instruction_documentation(
                    operation,
                    instruction_doc,
                    include_missing_doc_notice=include_missing_doc_notice
                )
            )
            if index < num_instructions - 1:
                sections.append('---')

        return '\n\n'.join(sections)

    def _generate_instruction_documentation(
        self,
        instruction_name: str,
        instruction_doc: dict[str, Any],
        include_missing_doc_notice: bool = True,
        table_style: str = 'markdown',
        add_header_rule: bool = False
    ) -> str:
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
        if add_header_rule:
            sections.append('---')

        documented = instruction_doc.get('documented', True)

        if not documented and include_missing_doc_notice:
            sections.append('*Documentation not provided.*')

        # Shared description
        if instruction_doc.get('description'):
            sections.append(instruction_doc['description'])

        # Operand syntax by version
        versions = instruction_doc.get('versions') or []
        multi_version = len(versions) > 1
        for version in versions:
            version_section = self._generate_instruction_version_section(
                mnemonic,
                version,
                include_heading=multi_version,
                table_style=table_style
            )
            if version_section:
                sections.append(version_section)

        # Modifies table
        if instruction_doc.get('modifies'):
            sections.append(self._generate_modifies_table(
                instruction_doc['modifies'],
                table_style=table_style
            ))

        # Effective flow metadata can differ per version. Keep these derived
        # tables after every hand-authored modifies table so generated rows
        # never reorder or duplicate authored documentation.
        if multi_version:
            for version in versions:
                flow_modifies = version.get('flow_modifies', [])
                if not flow_modifies:
                    continue
                sections.append(self._generate_modifies_table(
                    flow_modifies,
                    table_style=table_style,
                    heading=(
                        f"Modifies — Version {version.get('index')} "
                        'Counter Effects'
                    ),
                ))

        # Examples
        if instruction_doc.get('examples'):
            sections.append(self._generate_instruction_examples(instruction_doc['examples']))

        return '\n\n'.join(sections)

    def _build_operand_display_names(self, operands: list[dict[str, Any]]) -> list[str]:
        """
        Construct display names for operands, adding numeric suffixes when the same
        operand name appears multiple times in the calling syntax.
        """
        counts: dict[str, int] = {}
        base_names: list[str] = []

        for operand in operands:
            raw_name = operand.get('syntax') or operand.get('display_name') or operand.get('name') or ''
            base_name = str(raw_name) if raw_name is not None else ''
            base_names.append(base_name)
            if operand.get('include_in_code', True) and base_name:
                counts[base_name] = counts.get(base_name, 0) + 1

        duplicates = {name for name, count in counts.items() if count > 1}
        duplicate_indices = {name: 1 for name in duplicates}

        display_names: list[str] = []
        for operand, base_name in zip(operands, base_names):
            display_text = (
                operand.get('syntax')
                or operand.get('display_name')
                or operand.get('name')
                or base_name
            )
            if operand.get('include_in_code', True) and base_name in duplicates:
                display_name = f'{display_text}{duplicate_indices[base_name]}'
                duplicate_indices[base_name] += 1
            else:
                display_name = display_text
            display_names.append(display_name)

        return display_names

    def _generate_instruction_version_section(
        self,
        mnemonic: str,
        version_data: dict[str, Any],
        include_heading: bool,
        table_style: str = 'markdown'
    ) -> str:
        """Generate the syntax documentation for a single instruction version."""
        lines: list[str] = []

        if include_heading:
            version_index = version_data.get('index')
            heading_label = f'#### Version {version_index}'
            version_title = version_data.get('title')
            if version_title:
                heading_label += f' : {version_title}'
            lines.append(heading_label)

        version_description = version_data.get('description')
        if version_description:
            lines.append(version_description)

        signatures = version_data.get('signatures') or []
        if not signatures:
            signatures = [{'operands': []}]

        for signature in signatures:
            lines.append('*Calling syntax:*')

            operands = signature.get('operands') or []
            display_names = self._build_operand_display_names(operands)
            operand_tokens: list[str] = []
            for operand, display_name in zip(operands, display_names):
                if not operand.get('include_in_code', True):
                    continue
                if display_name:
                    operand_tokens.append(display_name)

            syntax_line = version_data.get('mnemonic', mnemonic)
            if operand_tokens:
                syntax_line = f"{syntax_line} {', '.join(operand_tokens)}"

            lines.append(f'```asm\n{syntax_line}\n```')

            operand_table = self._generate_instruction_operand_table(
                operands,
                display_names,
                table_style=table_style
            )
            if operand_table:
                lines.append('where')
                lines.append(operand_table)

        if version_data.get('modifies'):
            lines.append(self._generate_modifies_table(
                version_data['modifies'],
                table_style=table_style
            ))

        if version_data.get('examples'):
            lines.append(self._generate_instruction_examples(version_data['examples']))

        return '\n\n'.join(lines)

    def _generate_instruction_operand_table(
        self,
        operands: list[dict[str, Any]],
        display_names: list[str] | None = None,
        table_style: str = 'markdown'
    ) -> str:
        """Build the operand table for an instruction signature."""
        if not operands:
            return ''

        headers = ['Operand', 'Type', 'Value', 'Description']
        alignments = ['left', 'left', 'left', 'left']
        rows: list[list[str]] = []

        display_names = display_names or []

        for index, operand in enumerate(operands):
            operand_name_value = operand.get('name')
            base_name = str(operand_name_value) if operand_name_value is not None else ''
            display_name = display_names[index] if index < len(display_names) else base_name
            operand_cell = f'`{display_name}`' if display_name else ''

            operand_type_value = operand.get('type')
            operand_type = str(operand_type_value) if operand_type_value is not None else ''

            value_text = operand.get('value')
            value_cell = str(value_text) if value_text is not None else ''
            if value_cell:
                value_cell = value_cell.replace('\n', '<br>')

            description_value = operand.get('description')
            if description_value is None:
                description_cell = ''
            else:
                description_cell = str(description_value).replace('\n', '<br>')

            rows.append([operand_cell, operand_type, value_cell, description_cell])

        if table_style == 'ascii':
            return self._generate_ascii_table(headers, rows)
        return self._generate_markdown_table(headers, rows, column_alignments=alignments)

    def _generate_modifies_table(
        self,
        modifies: list[dict[str, str]],
        table_style: str = 'markdown',
        heading: str = 'Modifies',
    ) -> str:
        """Generate a table of what the instruction modifies."""
        if not modifies:
            return ''

        sections = [f'#### {heading}']

        # Prepare table data
        headers = ['Type', 'Target', 'Description']
        rows = []

        for modify in modifies:
            modify_type = modify.get('type', '').title()
            target = modify.get('target', '')
            description = modify.get('description', '').replace('\n', '<br>')
            rows.append([modify_type, target, description])

        # Generate optimized table
        if table_style == 'ascii':
            table = self._generate_ascii_table(headers, rows)
        else:
            table = self._generate_markdown_table(headers, rows)
        if table:
            sections.append(table)

        return '\n\n'.join(sections)

    def _generate_ascii_table(
        self,
        headers: list[str],
        rows: list[list[str]]
    ) -> str:
        """Generate a fixed-width ASCII table for hover rendering."""
        if not headers or not rows:
            return ''

        sanitized_rows = [
            [self._sanitize_ascii_cell(cell) for cell in row]
            for row in rows
        ]
        sanitized_headers = [self._sanitize_ascii_cell(cell) for cell in headers]

        column_count = len(sanitized_headers)
        padded_rows = [
            row + [''] * (column_count - len(row))
            for row in sanitized_rows
        ]

        widths = [
            max(len(sanitized_headers[idx]), *(len(row[idx]) for row in padded_rows))
            for idx in range(column_count)
        ]

        def render_separator() -> str:
            segments = ['+' + '-' * (width + 2) for width in widths]
            return ''.join(segments) + '+'

        def render_row(values: list[str]) -> str:
            cells = [
                f' {value.ljust(widths[idx])} '
                for idx, value in enumerate(values)
            ]
            return '|' + '|'.join(cells) + '|'

        lines = [render_separator(), render_row(sanitized_headers), render_separator()]
        for row in padded_rows:
            lines.append(render_row(row))
        lines.append(render_separator())

        return '```\n' + '\n'.join(lines) + '\n```'

    @staticmethod
    def _sanitize_ascii_cell(value: Any) -> str:
        """Normalize a cell value for ASCII table rendering."""
        if value is None:
            return ''
        text = str(value)
        return (
            text.replace('<br>', ' / ')
            .replace('\n', ' / ')
            .replace('\r', '')
        ).strip()

    def _generate_instruction_examples(self, examples: list[dict[str, str]]) -> str:
        """Generate examples for an instruction."""
        if not examples:
            return ''

        sections = ['#### Examples']

        for example in examples:
            example_sections = []

            if example.get('title'):
                example_sections.append(f"##### {example['title']}")

            if example.get('description'):
                example_sections.append(example['description'])

            if example.get('code'):
                example_sections.append(f"```assembly\n{example['code']}\n```")

            if example_sections:
                sections.append('\n\n'.join(example_sections))

        return '\n\n'.join(sections)
