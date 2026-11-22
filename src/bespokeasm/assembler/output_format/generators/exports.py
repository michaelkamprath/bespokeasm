"""The ``exports`` generator: one line per symbol that carries an annotation."""
from __future__ import annotations

import math
import re
from typing import Any

from bespokeasm.assembler.annotations.model import AnnotatedSymbol
from bespokeasm.assembler.diagnostic_reporter import AssemblerError
from bespokeasm.assembler.output_format.base import RenderContext
from bespokeasm.assembler.output_format.columns import ColumnTable
from bespokeasm.assembler.output_format.generators import Generator
from bespokeasm.assembler.output_format.template import Template

ORDERS = ('address', 'source')
# Fields every export has; an annotation argument may not reuse these names.
# ``name`` is the exception: it is the ``name`` argument when present, else the symbol.
SYMBOL_FIELDS = ('symbol', 'address', 'value', 'size', 'words')
_ARGUMENT_SAMPLES = {'enum': 'x', 'string': 'x', 'integer': 0, 'boolean': True, 'symbol': 0}


class ExportsGenerator(Generator):
    name = 'exports'
    required_options = frozenset({'annotation'})
    optional_options = frozenset({
        'order', 'unique', 'reserved_names', 'name_pattern', 'lines_key', 'lines', 'value_map',
        'columns', 'separator', 'header_rule', 'rule_separator',
    })

    def configure(self, options: dict[str, Any]) -> None:
        annotation = options['annotation']
        namespace = self.env.annotation_namespaces.get(annotation) if isinstance(annotation, str) else None
        if namespace is None:
            self.error(
                'annotation',
                f"names annotation '{annotation}', which this configuration does not declare; "
                f'annotations are {", ".join(sorted(self.env.annotation_namespaces))}',
            )
        self.namespace = namespace

        self.order = options.get('order', 'source')
        if self.order not in ORDERS:
            self.error('order', f'must be {" or ".join(ORDERS)}, not "{self.order}"')

        unique = options.get('unique')
        if unique not in (None, 'name'):
            self.error('unique', f'must be "name", not "{unique}"')
        self.unique = unique == 'name'

        reserved = options.get('reserved_names', [])
        if not isinstance(reserved, list) or not all(isinstance(item, str) for item in reserved):
            self.error('reserved_names', 'must be a list of names')
        self.reserved_names = frozenset(reserved)

        self.name_pattern = None
        if 'name_pattern' in options:
            if not isinstance(options['name_pattern'], str):
                self.error('name_pattern', 'must be a string')
            try:
                self.name_pattern = re.compile(options['name_pattern'])
            except re.error as exc:
                self.error('name_pattern', f'is not a valid regular expression: {exc}')

        for argument in namespace.arguments:
            if argument in SYMBOL_FIELDS:
                self.error(
                    'annotation',
                    f"names annotation '{namespace.name}', whose argument '{argument}' has the same name as "
                    f'an export field ({", ".join(SYMBOL_FIELDS)})',
                )
        self.value_map = self._configure_value_map(options.get('value_map', {}))
        self.fields = self._field_samples()
        uses_lines = 'lines_key' in options or 'lines' in options
        uses_columns = 'columns' in options
        if uses_lines and uses_columns:
            self.error(None, "uses generator 'exports' with both lines and columns; give lines_key and lines, or columns")
        for option in ('separator', 'header_rule', 'rule_separator'):
            if option in options and not uses_columns:
                self.error(option, 'is only used with columns')
        self.lines: dict[str, Template] | None = None
        self.table: ColumnTable | None = None
        if uses_columns:
            self.table = ColumnTable.load(
                options['columns'], options.get('separator'), self.fields,
                lambda option, problem: self.error(option, problem),
                enum_fields={
                    name: spec.values for name, spec in self.namespace.arguments.items() if spec.type == 'enum'
                },
                header_rule=options.get('header_rule'),
                rule_separator=options.get('rule_separator'),
                warn=lambda option, problem: self.env.warn(self.option_path(option), problem),
            )
        else:
            self._configure_lines(options)

    def _configure_value_map(self, value_map: Any) -> dict[str, dict[str, str]]:
        """``value_map`` rewrites enum argument values in this section's output, as in
        ``{type: {str: char}}``. Line selection by ``lines_key`` still uses the source value."""
        if not isinstance(value_map, dict):
            self.error('value_map', 'must map enum argument names to mappings of value to output text')
        result: dict[str, dict[str, str]] = {}
        for argument, mapping in value_map.items():
            spec = self.namespace.arguments.get(argument)
            if spec is None or spec.type != 'enum':
                self.error(f'value_map.{argument}', f"must name an enum argument of annotation '{self.namespace.name}'")
            if not isinstance(mapping, dict):
                self.error(f'value_map.{argument}', 'must map values of the argument to output text')
            for value, text in mapping.items():
                if str(value) not in spec.values:
                    self.error(f'value_map.{argument}.{value}', f"is not a value of argument '{argument}'")
                if not isinstance(text, str):
                    self.error(f'value_map.{argument}.{value}', 'must be a string')
            result[argument] = {str(value): text for value, text in mapping.items()}
        return result

    def _field_samples(self) -> dict[str, Any]:
        fields: dict[str, Any] = {'name': 'x', 'symbol': 'x', 'address': 0, 'value': 0, 'size': 0, 'words': '00'}
        for argument, spec in self.namespace.arguments.items():
            if argument != 'name':
                fields[argument] = _ARGUMENT_SAMPLES[spec.type]
        return fields

    def _configure_lines(self, options: dict[str, Any]) -> None:
        if 'lines_key' not in options or 'lines' not in options:
            self.error(None, "uses generator 'exports', which requires 'lines_key' and 'lines', or 'columns'")
        key = options['lines_key']
        spec = self.namespace.arguments.get(key) if isinstance(key, str) else None
        if spec is None or spec.type != 'enum':
            self.error('lines_key', f"must name an enum argument of annotation '{self.namespace.name}'")
        self.lines_key = key
        lines = options['lines']
        if not isinstance(lines, dict):
            self.error('lines', f"must map each value of '{key}' to a line template")
        for value in spec.values:
            if value not in {str(k) for k in lines}:
                self.error('lines', f"has no line template for {key}={value}")
        self.lines: dict[str, Template] = {}
        for value, text in lines.items():
            if str(value) not in spec.values:
                self.error(f'lines.{value}', f"is not a value of argument '{key}'")
            self.lines[str(value)] = Template.parse(
                text,
                self.fields,
                lambda problem, value=value: self.error(f'lines.{value}', problem),
            )

    # ---- rendering -------------------------------------------------------------

    def render(self, context: RenderContext) -> str:
        symbols = context.export_model.for_namespace(self.namespace.name)
        if not symbols:
            context.model.diagnostic_reporter.warn(
                None,
                f"format '{self.format_name}': no symbols carry an '{self.namespace.name}' annotation",
            )
            return ''
        if self.order == 'address':
            symbols = (
                sorted((s for s in symbols if s.is_label), key=lambda s: s.address)
                + [s for s in symbols if not s.is_label]
            )
        hex_width = math.ceil(context.model.word_size / 4)
        rows = []
        seen: dict[str, AnnotatedSymbol] = {}
        for symbol in symbols:
            values = self._values(symbol, hex_width)
            self._check_name(values['name'], symbol, seen)
            rows.append(values)
        if self.table is not None:
            # A column chooses its field by an argument's source value, before value_map.
            keys = [symbol.annotations[self.namespace.name].arguments for symbol in symbols]
            return self.table.render(rows, keys)
        return '\n'.join(self._line_template(symbol).render(values) for symbol, values in zip(symbols, rows))

    def _values(self, symbol: AnnotatedSymbol, hex_width: int) -> dict[str, Any]:
        annotation = symbol.annotations[self.namespace.name]
        values: dict[str, Any] = {}
        for argument, spec in self.namespace.arguments.items():
            if spec.type == 'symbol':
                values[argument] = annotation.resolved_symbols.get(argument)
            else:
                value = annotation.arguments.get(argument)
                values[argument] = self.value_map.get(argument, {}).get(value, value)
        name_argument = annotation.arguments.get('name') if 'name' in self.namespace.arguments else None
        values.update({
            'name': str(name_argument) if name_argument not in (None, '') else symbol.name,
            'symbol': symbol.name,
            'address': symbol.address,
            'value': None if symbol.is_label else symbol.value,
            # A label with no data has no size to report: the field is empty rather than 0.
            'size': symbol.size or None,
            'words': ' '.join(f'{word.value:0{hex_width}x}' for word in symbol.words) if symbol.is_label else None,
        })
        return values

    def _check_name(self, name: str, symbol: AnnotatedSymbol, seen: dict[str, AnnotatedSymbol]) -> None:
        if self.name_pattern is not None and self.name_pattern.fullmatch(name) is None:
            raise AssemblerError(
                symbol.line_id,
                f"export name '{name}' is not valid for format '{self.format_name}'; "
                f'it does not match {self.name_pattern.pattern}',
            )
        if name in self.reserved_names:
            raise AssemblerError(
                symbol.line_id,
                f"export name '{name}' is not valid for format '{self.format_name}'; it is a reserved name",
            )
        if self.unique:
            first = seen.get(name)
            if first is not None:
                raise AssemblerError(
                    symbol.line_id,
                    f"export name '{name}' is used by '{first.name}' and '{symbol.name}'",
                )
            seen[name] = symbol

    def _line_template(self, symbol: AnnotatedSymbol) -> Template:
        annotation = symbol.annotations[self.namespace.name]
        key_value = annotation.arguments.get(self.lines_key)
        if key_value is None:
            raise AssemblerError(
                annotation.line_id,
                f"format '{self.format_name}' chooses each line by '{self.lines_key}', "
                f"but '{symbol.name}' has no '{self.lines_key}' argument",
            )
        return self.lines[key_value]
