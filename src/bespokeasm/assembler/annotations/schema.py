"""Annotation namespaces: the ``annotations`` section of an ISA configuration.

An annotation namespace declares which arguments a ``#annotate <namespace>`` line may
carry, which symbols it may be attached to, and the constraints (``data_size`` and
``value_range``) the annotated symbol must satisfy. A namespace can also opt in to
``#verbatim <namespace>`` text blocks with ``verbatim``. The framework's own ``listing``
namespace exists for every ISA and may not be declared by a configuration.

Configuration problems are reported through an ``error(path, problem)`` callable that
does not return (``ConfigValidator.error``). Problems in assembly source raise
``AssemblerError``.
"""
from __future__ import annotations

import difflib
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from typing import NoReturn

from bespokeasm.assembler.diagnostic_reporter import AssemblerError
from bespokeasm.assembler.line_identifier import LineIdentifier
from bespokeasm.utilities import is_string_numeric
from bespokeasm.utilities import is_valid_label
from bespokeasm.utilities import parse_numeric_string

ARGUMENT_TYPES = ('enum', 'integer', 'string', 'boolean', 'symbol')
SYMBOL_KINDS = ('label', 'constant')
SYMBOL_SCOPES = ('global', 'file', 'local')
LISTING_NAMESPACE_NAME = 'listing'
PATTERN_NAMESPACE_NAME = re.compile(r'^[A-Za-z][A-Za-z0-9_]*$')
PATTERN_ARGUMENT_NAME = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*$')

ConfigErrorFn = Callable[[str, str], NoReturn]


@dataclass(frozen=True)
class RawArgument:
    """One ``key`` or ``key=value`` item from an ``#annotate`` line, before validation."""
    key: str
    value: str | None
    quoted: bool = False


@dataclass(frozen=True)
class Condition:
    """An all-of test on enum argument values, from a ``required_when``, ``allowed_when`` or ``when`` mapping."""
    tests: tuple[tuple[str, tuple[str, ...]], ...]

    def holds(self, values: dict[str, Any]) -> bool:
        return all(values.get(key) in allowed for key, allowed in self.tests)

    def describe(self) -> str:
        parts = []
        for key, allowed in self.tests:
            if len(allowed) == 1:
                parts.append(f'{key} is {allowed[0]}')
            else:
                parts.append(f'{key} is one of {", ".join(allowed)}')
        return ' and '.join(parts)


@dataclass(frozen=True)
class ArgumentSpec:
    name: str
    type: str
    values: tuple[str, ...] = ()
    minimum: int | None = None
    maximum: int | None = None
    pattern: re.Pattern | None = None
    required: bool = False
    required_when: Condition | None = None
    allowed_when: Condition | None = None
    has_default: bool = False
    default: Any = None
    # From ``documentation``: what the argument means, and for an enum what each value means.
    description: str | None = None
    value_descriptions: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class SelectedRule:
    """A constraint whose value is fixed or selected by one enum argument.

    Used for both ``data_size`` (values are word counts, optionally multiplied by an
    integer argument named by ``times``) and ``value_range`` (values are ``(min, max)``).
    """
    kind: str
    when: Condition | None
    fixed: Any = None
    selector: str | None = None
    table: tuple[tuple[str, Any], ...] = ()
    times: str | None = None
    # A boolean argument that, when true, makes ``times`` come from the label's data.
    infer_times: str | None = None
    # When this holds, the data ends with a terminator element that ``times`` leaves out,
    # and ``times`` comes from the data.
    terminated_when: Condition | None = None

    def applies(self, values: dict[str, Any]) -> bool:
        return self.when is None or self.when.holds(values)

    def infers_times(self, values: dict[str, Any]) -> bool:
        """Whether these arguments ask for ``times`` to be taken from the data."""
        return self.applies(values) and (
            (self.infer_times is not None and values.get(self.infer_times) is True)
            or self.is_terminated(values)
        )

    def is_terminated(self, values: dict[str, Any]) -> bool:
        """Whether these arguments say the data ends with a terminator that ``times`` leaves out."""
        return self.terminated_when is not None and self.applies(values) and self.terminated_when.holds(values)

    def inferring_arguments(self, values: dict[str, Any]) -> str:
        """The argument values that make ``times`` come from the data, as source writes them."""
        if self.is_terminated(values):
            return ' '.join(_argument_text(key, values[key]) for key, _ in self.terminated_when.tests)
        return f"'{self.infer_times}'"

    def evaluate(self, namespace: str, values: dict[str, Any], apply_times: bool = True) -> Any:
        """Return the constraint value for these arguments, or None if the rule does not apply.

        Raises ValueError when an argument the rule needs is absent.
        """
        if not self.applies(values):
            return None
        if self.selector is None:
            result = self.fixed
        else:
            selected = values.get(self.selector)
            if selected is None:
                raise ValueError(
                    f"annotation '{namespace}': {self.kind} needs argument '{self.selector}'"
                )
            result = dict(self.table)[selected]
            if result is None:
                # A null table entry: this value is not allowed where the rule applies.
                where = f' when {self.when.describe()}' if self.when is not None else ''
                raise ValueError(f"annotation '{namespace}': {self.selector}={selected} is not allowed{where}")
        if apply_times and self.times is not None:
            result = result * values.get(self.times, 1)
        return result

    def basis(self, values: dict[str, Any]) -> str:
        """The argument values that chose this rule's value, as in ``type=char count=16``.

        These are the selector and ``times`` arguments; a fixed rule names the arguments its
        ``when`` tests instead. Empty when no argument chose the value.
        """
        keys = [key for key in (self.selector, self.times, self.infer_times) if key is not None and key in values]
        if not keys and self.selector is None and self.when is not None:
            keys = [key for key, _ in self.when.tests if key in values]
        return ' '.join(_argument_text(key, values[key]) for key in keys)


def _argument_text(key: str, value: Any) -> str:
    """An argument as source writes it: a true boolean is a bare key."""
    if value is True:
        return key
    if value is False:
        return f'{key}=false'
    return f'{key}={value}'


@dataclass(frozen=True)
class AnnotationNamespace:
    name: str
    description: str | None
    applies_to: tuple[str, ...]
    scopes: tuple[str, ...]
    arguments: dict[str, ArgumentSpec]
    data_size: SelectedRule | None = None
    # In order: the first rule whose ``when`` holds is the one that applies.
    value_range: tuple[SelectedRule, ...] = ()
    is_builtin: bool = False
    # From ``documentation.examples``: each a mapping of ``title``, ``description`` and ``code``.
    examples: tuple[dict[str, str], ...] = ()
    # Whether source may carry ``#verbatim <namespace>`` blocks, and what they are for.
    accepts_verbatim: bool = False
    verbatim_description: str | None = None
    # The parts a block may name (``#verbatim <namespace> <part>``), in declaration order, each
    # with its description. A format places each part's blocks with its own section.
    verbatim_parts: tuple[tuple[str, str | None], ...] = ()

    @property
    def verbatim_part_names(self) -> tuple[str, ...]:
        return tuple(name for name, _ in self.verbatim_parts)

    # ---- source validation -------------------------------------------------

    def _error(self, line_id: LineIdentifier, problem: str) -> NoReturn:
        raise AssemblerError(line_id, f"annotation '{self.name}': {problem}")

    def validate_arguments(
        self,
        raw_arguments: list[RawArgument],
        line_id: LineIdentifier,
        default_numeric_base: str = 'decimal',
    ) -> dict[str, Any]:
        """Validate the arguments of one ``#annotate`` line and apply defaults."""
        explicit: dict[str, Any] = {}
        for raw in raw_arguments:
            spec = self.arguments.get(raw.key)
            if spec is None:
                self._error(line_id, self._unknown_argument_problem(raw.key))
            if raw.key in explicit:
                self._error(line_id, f"argument '{raw.key}' is given more than once")
            explicit[raw.key] = self._convert_value(spec, raw, line_id, default_numeric_base)

        values = dict(explicit)
        for spec in self.arguments.values():
            if spec.name not in values and spec.has_default and spec.allowed_when is None:
                values[spec.name] = spec.default
        for spec in self.arguments.values():
            if (
                spec.name not in values
                and spec.has_default
                and spec.allowed_when is not None
                and spec.allowed_when.holds(values)
            ):
                values[spec.name] = spec.default

        for name in explicit:
            spec = self.arguments[name]
            if spec.allowed_when is not None and not spec.allowed_when.holds(values):
                self._error(line_id, f"'{name}' is only allowed when {spec.allowed_when.describe()}")
        for spec in self.arguments.values():
            if spec.name in values:
                continue
            if spec.required:
                self._error(line_id, f"argument '{spec.name}' is required")
            if spec.required_when is not None and spec.required_when.holds(values):
                self._error(
                    line_id,
                    f"argument '{spec.name}' is required when {spec.required_when.describe()}",
                )
        rule = self.data_size
        if rule is not None and rule.infers_times(values) and rule.times in explicit:
            self._error(
                line_id,
                f"'{rule.times}' cannot be given with {rule.inferring_arguments(values)}, "
                f'which takes {rule.times} from the data',
            )
        return values

    def _unknown_argument_problem(self, key: str) -> str:
        known = list(self.arguments)
        if not known:
            return f"unknown argument '{key}'; this annotation takes no arguments"
        suggestion = difflib.get_close_matches(key, known, n=1, cutoff=0.7)
        if suggestion:
            return f"unknown argument '{key}'; did you mean '{suggestion[0]}'?"
        return f"unknown argument '{key}'; known arguments are {', '.join(known)}"

    def _convert_value(
        self,
        spec: ArgumentSpec,
        raw: RawArgument,
        line_id: LineIdentifier,
        default_numeric_base: str,
    ) -> Any:
        if raw.value is None:
            if spec.type == 'boolean':
                return True
            self._error(line_id, f"argument '{spec.name}' needs a value, for example {spec.name}=...")
        text = raw.value
        if spec.type == 'enum':
            if text not in spec.values:
                self._error(line_id, f"argument '{spec.name}' must be one of {', '.join(spec.values)}")
            return text
        if spec.type == 'boolean':
            lowered = text.lower()
            if raw.quoted or lowered not in ('true', 'false'):
                self._error(line_id, f"argument '{spec.name}' must be true or false, not \"{text}\"")
            return lowered == 'true'
        if spec.type == 'integer':
            value = None if raw.quoted else _parse_integer(text, default_numeric_base)
            if value is None:
                self._error(line_id, f"argument '{spec.name}' must be an integer, not \"{text}\"")
            if spec.minimum is not None and value < spec.minimum:
                self._error(line_id, f"argument '{spec.name}' must be at least {spec.minimum}, not {value}")
            if spec.maximum is not None and value > spec.maximum:
                self._error(line_id, f"argument '{spec.name}' must be at most {spec.maximum}, not {value}")
            return value
        if spec.type == 'symbol':
            if raw.quoted or not is_valid_label(text):
                self._error(
                    line_id,
                    f"argument '{spec.name}' must name a label or constant, not \"{text}\"",
                )
            return text
        # string
        if spec.pattern is not None and spec.pattern.fullmatch(text) is None:
            self._error(
                line_id,
                f"argument '{spec.name}' value \"{text}\" does not match the pattern {spec.pattern.pattern}",
            )
        return text

    def expected_words(self, values: dict[str, Any]) -> int | None:
        """The ``data_size`` word count these arguments require of a label, or None."""
        if self.data_size is None:
            return None
        return self.data_size.evaluate(self.name, values)

    def _value_range_rule(self, values: dict[str, Any]) -> SelectedRule | None:
        """The first ``value_range`` rule that applies to these arguments, or None."""
        return next((rule for rule in self.value_range if rule.applies(values)), None)

    def allowed_range(self, values: dict[str, Any]) -> tuple[int, int] | None:
        """The ``value_range`` these arguments require of a constant, or None."""
        rule = self._value_range_rule(values)
        return rule.evaluate(self.name, values) if rule is not None else None

    def element_words(self, values: dict[str, Any]) -> int | None:
        """The ``data_size`` of one element when the data sets ``times`` for these arguments, else None."""
        if self.data_size is None or not self.data_size.infers_times(values):
            return None
        return self.data_size.evaluate(self.name, values, apply_times=False)

    def is_terminated(self, values: dict[str, Any]) -> bool:
        """Whether a label's data must end with a terminator element that the count leaves out."""
        return self.data_size is not None and self.data_size.is_terminated(values)

    def data_size_basis(self, values: dict[str, Any]) -> str:
        """The arguments that chose the ``data_size`` word count, for messages."""
        return self.data_size.basis(values) if self.data_size is not None else ''

    def value_range_basis(self, values: dict[str, Any]) -> str:
        """The arguments that chose the ``value_range``, for messages."""
        rule = self._value_range_rule(values)
        return rule.basis(values) if rule is not None else ''


def _parse_integer(text: str, default_numeric_base: str) -> int | None:
    sign = 1
    body = text
    if body.startswith('-'):
        sign = -1
        body = body[1:]
    elif body.startswith('+'):
        body = body[1:]
    if body == '' or not is_string_numeric(body, default_numeric_base):
        return None
    try:
        return sign * parse_numeric_string(body, default_numeric_base)
    except ValueError:
        return None


# ---- the framework's own namespace --------------------------------------------

LISTING_NAMESPACE = AnnotationNamespace(
    name=LISTING_NAMESPACE_NAME,
    description='Controls how the annotated symbol appears in the `-t listing` output.',
    applies_to=SYMBOL_KINDS,
    scopes=SYMBOL_SCOPES,
    arguments={
        'heading': ArgumentSpec(
            'heading', 'string', description='Prints this heading, underlined, above the symbol.',
        ),
        'page_break': ArgumentSpec(
            'page_break', 'boolean',
            description='Starts a new page above the symbol: a form feed, then the file and column headers again.',
        ),
        'collapse': ArgumentSpec(
            'collapse', 'boolean',
            description="Shows the first row of the label's data, then a count of the words not shown.",
        ),
        'hide': ArgumentSpec(
            'hide', 'boolean',
            description="Leaves the symbol's lines out of the listing; its bytes are still assembled.",
        ),
    },
    is_builtin=True,
    examples=(
        {
            'title': 'A heading above a collapsed table',
            'description': 'The listing prints the heading, then the first row of the table and a count of the rest.',
            'code': (
                '#annotate listing heading="Lookup tables" collapse\n'
                'sine_table:\n'
                '    .byte 0, 3, 6, 9, 12, 16, 19, 22, 25, 28, 31, 34, 37, 40, 43, 46'
            ),
        },
    ),
)

BUILTIN_NAMESPACES = {LISTING_NAMESPACE.name: LISTING_NAMESPACE}


# ---- configuration loading ----------------------------------------------------

def _is_int(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


class _NamespaceLoader:
    def __init__(self, name: str, config: dict, error: ConfigErrorFn) -> None:
        self._name = name
        self._config = config
        self._error = error
        self._path = f'annotations.{name}'

    def load(self) -> AnnotationNamespace:
        config = self._config
        description = None
        examples: tuple[dict[str, str], ...] = ()
        documentation = config.get('documentation')
        if documentation is not None:
            if not isinstance(documentation, dict):
                self._error(f'{self._path}.documentation', 'must be a mapping')
            for key in documentation:
                if key not in ('description', 'examples'):
                    self._error(
                        f'{self._path}.documentation.{key}',
                        'is not a documentation setting; annotations take description, examples',
                    )
            description = documentation.get('description')
            if description is not None and not isinstance(description, str):
                self._error(f'{self._path}.documentation.description', 'must be a string')
            examples = self._examples(documentation.get('examples'), f'{self._path}.documentation.examples')

        applies_to = self._name_list('applies_to', SYMBOL_KINDS)
        scopes = self._name_list('scopes', SYMBOL_SCOPES)

        arguments_config = config.get('arguments')
        if arguments_config is None:
            arguments_config = {}
        if not isinstance(arguments_config, dict):
            self._error(f'{self._path}.arguments', 'must be a mapping of argument names')
        # Pass one: types and value constraints. Pass two: conditions, which refer to
        # other (enum) arguments and so need every argument's type.
        partial: dict[str, dict] = {}
        for arg_name, arg_config in arguments_config.items():
            arg_path = f'{self._path}.arguments.{arg_name}'
            if not isinstance(arg_name, str) or PATTERN_ARGUMENT_NAME.match(arg_name) is None:
                self._error(arg_path, 'is not a valid argument name (use letters, digits and "_")')
            if not isinstance(arg_config, dict):
                self._error(arg_path, 'must be a mapping')
            partial[arg_name] = self._argument_basics(arg_name, arg_config, arg_path)
        arguments: dict[str, ArgumentSpec] = {}
        for arg_name, basics in partial.items():
            arg_path = f'{self._path}.arguments.{arg_name}'
            arg_config = arguments_config[arg_name]
            required_when = self._condition(arg_config, 'required_when', arg_path, partial, exclude=arg_name)
            allowed_when = self._condition(arg_config, 'allowed_when', arg_path, partial, exclude=arg_name)
            arguments[arg_name] = ArgumentSpec(
                required_when=required_when,
                allowed_when=allowed_when,
                # Not `description`: that name holds the namespace's own description.
                description=self._argument_documentation(arg_config, arg_path),
                **basics,
            )

        data_size = self._selected_rule('data_size', 'words', arguments, self._words_value)
        value_range = self._value_range_rules(arguments)
        if data_size is not None and 'label' not in applies_to:
            self._error(f'{self._path}.data_size', 'only applies to labels, but applies_to does not include label')
        if value_range and 'constant' not in applies_to:
            self._error(
                f'{self._path}.value_range',
                'only applies to constants, but applies_to does not include constant',
            )
        return AnnotationNamespace(
            name=self._name,
            description=description,
            applies_to=applies_to,
            scopes=scopes,
            arguments=arguments,
            data_size=data_size,
            value_range=value_range,
            examples=examples,
            **self._verbatim(),
        )

    def _verbatim(self) -> dict[str, Any]:
        """``verbatim`` opts the namespace in to ``#verbatim`` blocks: a mapping with the optional
        ``documentation`` (a ``description``) and ``parts`` (the parts a block may name)."""
        if 'verbatim' not in self._config:
            return {}
        path = f'{self._path}.verbatim'
        config = self._config['verbatim']
        if not isinstance(config, dict):
            self._error(path, 'must be a mapping, such as {} or {documentation: {description: ...}}')
        for key in config:
            if key not in ('documentation', 'parts'):
                self._error(f'{path}.{key}', 'is not a verbatim setting; verbatim takes documentation and parts')
        parts_config = config.get('parts', {})
        if not isinstance(parts_config, dict) or ('parts' in config and not parts_config):
            self._error(f'{path}.parts', 'must be a non-empty mapping of part names, such as {header: {}}')
        parts = []
        for name, part in parts_config.items():
            part_path = f'{path}.parts.{name}'
            if not isinstance(name, str) or not PATTERN_NAMESPACE_NAME.match(name):
                self._error(part_path, 'is not a part name: a letter followed by letters, digits or underscores')
            if part is not None and not isinstance(part, dict):
                self._error(part_path, 'must be a mapping, such as {} or {documentation: {description: ...}}')
            for key in part or {}:
                if key != 'documentation':
                    self._error(f'{part_path}.{key}', 'is not a part setting; a part takes documentation')
            parts.append((name, self._verbatim_description((part or {}).get('documentation'), part_path)))
        return {
            'accepts_verbatim': True,
            'verbatim_description': self._verbatim_description(config.get('documentation'), path),
            'verbatim_parts': tuple(parts),
        }

    def _verbatim_description(self, documentation: Any, path: str) -> str | None:
        """The ``description`` of a verbatim ``documentation`` mapping, or ``None``."""
        if documentation is None:
            return None
        if not isinstance(documentation, dict):
            self._error(f'{path}.documentation', 'must be a mapping')
        for key in documentation:
            if key != 'description':
                self._error(
                    f'{path}.documentation.{key}',
                    'is not a documentation setting; verbatim documentation takes description',
                )
        description = documentation.get('description')
        if description is not None and not isinstance(description, str):
            self._error(f'{path}.documentation.description', 'must be a string')
        return description

    def _examples(self, examples: Any, path: str) -> tuple[dict[str, str], ...]:
        """Usage examples, as instructions have: each a ``code`` block with an optional ``title``
        and ``description``."""
        if examples is None:
            return ()
        if not isinstance(examples, list):
            self._error(path, 'must be a list of examples, each with code and an optional title and description')
        loaded = []
        for index, example in enumerate(examples):
            example_path = f'{path}[{index}]'
            if not isinstance(example, dict):
                self._error(example_path, 'must be a mapping with code and an optional title and description')
            for key in example:
                if key not in ('title', 'description', 'code'):
                    self._error(f'{example_path}.{key}', 'is not an example setting; examples take title, description, code')
            if 'code' not in example:
                self._error(example_path, 'needs code')
            for key in ('title', 'description', 'code'):
                if key in example and not isinstance(example[key], str):
                    self._error(f'{example_path}.{key}', 'must be a string')
            loaded.append({key: example[key].rstrip('\n') if key == 'code' else example[key] for key in example})
        return tuple(loaded)

    def _argument_documentation(self, config: dict, path: str) -> str | None:
        """An argument's optional ``documentation``: its ``description``. Each enum value is
        documented with the value itself, under ``values``."""
        documentation = config.get('documentation')
        if documentation is None:
            return None
        doc_path = f'{path}.documentation'
        if not isinstance(documentation, dict):
            self._error(doc_path, 'must be a mapping')
        for key in documentation:
            if key == 'values':
                self._error(
                    f'{doc_path}.values',
                    f'is not a documentation setting; document each value under {path}.values, '
                    'as {value: {documentation: {description: ...}}}',
                )
            if key != 'description':
                self._error(f'{doc_path}.{key}', 'is not a documentation setting; arguments take description')
        description = documentation.get('description')
        if description is not None and not isinstance(description, str):
            self._error(f'{doc_path}.description', 'must be a string')
        return description

    def _name_list(self, key: str, choices: tuple[str, ...]) -> tuple[str, ...]:
        if key not in self._config:
            return choices
        value = self._config[key]
        if isinstance(value, str):
            value = [value]
        if not isinstance(value, list) or len(value) == 0:
            self._error(f'{self._path}.{key}', f'must be a non-empty list of {", ".join(choices)}')
        for item in value:
            if item not in choices:
                self._error(f'{self._path}.{key}', f'must contain only {", ".join(choices)}, not "{item}"')
        return tuple(choice for choice in choices if choice in value)

    def _argument_basics(self, name: str, config: dict, path: str) -> dict:
        arg_type = config.get('type')
        if arg_type not in ARGUMENT_TYPES:
            self._error(f'{path}.type', f'must be one of {", ".join(ARGUMENT_TYPES)}')
        for key, allowed_types in (
            ('values', ('enum',)),
            ('min', ('integer',)),
            ('max', ('integer',)),
            ('pattern', ('string',)),
        ):
            if key in config and arg_type not in allowed_types:
                self._error(f'{path}.{key}', f'only applies to arguments of type {" or ".join(allowed_types)}')

        values: tuple[str, ...] = ()
        value_descriptions: tuple[tuple[str, str], ...] = ()
        if arg_type == 'enum':
            values, value_descriptions = self._enum_values(config.get('values'), f'{path}.values')

        minimum = config.get('min')
        maximum = config.get('max')
        for key, value in (('min', minimum), ('max', maximum)):
            if value is not None and not _is_int(value):
                self._error(f'{path}.{key}', 'must be an integer')
        if minimum is not None and maximum is not None and minimum > maximum:
            self._error(f'{path}.min', f'must not be greater than max ({maximum})')

        pattern = None
        if 'pattern' in config:
            if not isinstance(config['pattern'], str):
                self._error(f'{path}.pattern', 'must be a string')
            try:
                pattern = re.compile(config['pattern'])
            except re.error as exc:
                self._error(f'{path}.pattern', f'is not a valid regular expression: {exc}')

        required = config.get('required', False)
        if not isinstance(required, bool):
            self._error(f'{path}.required', 'must be true or false')

        has_default = 'default' in config
        default = config.get('default')
        if has_default:
            if required:
                self._error(f'{path}.default', 'cannot be set on a required argument')
            default = self._check_default(arg_type, default, values, minimum, maximum, pattern, f'{path}.default')

        return {
            'name': name,
            'type': arg_type,
            'values': values,
            'minimum': minimum,
            'maximum': maximum,
            'pattern': pattern,
            'required': required,
            'has_default': has_default,
            'default': default,
            'value_descriptions': value_descriptions,
        }

    def _enum_values(self, raw_values: Any, path: str) -> tuple[tuple[str, ...], tuple[tuple[str, str], ...]]:
        """An enum's values: a list, or a mapping of each value to its optional ``documentation``
        (``{addr: {documentation: {description: ...}}, var: ...}``)."""
        if isinstance(raw_values, list):
            if not raw_values:
                self._error(path, 'is required for an enum argument and must not be empty')
            values = tuple(str(value) for value in raw_values)
            if len(set(values)) != len(values):
                self._error(path, 'must not repeat a value')
            return values, ()
        if not isinstance(raw_values, dict) or not raw_values:
            self._error(
                path,
                'is required for an enum argument: a list of values, or a mapping of each value to its documentation',
            )
        values = tuple(str(value) for value in raw_values)
        described = []
        for value, entry in raw_values.items():
            entry_path = f'{path}.{value}'
            if entry is None:
                continue
            if not isinstance(entry, dict):
                self._error(entry_path, 'must be a mapping with an optional documentation block')
            for key in entry:
                if key != 'documentation':
                    self._error(f'{entry_path}.{key}', 'is not a value setting; a value takes only documentation')
            documentation = entry.get('documentation')
            if documentation is None:
                continue
            if not isinstance(documentation, dict):
                self._error(f'{entry_path}.documentation', 'must be a mapping')
            for key in documentation:
                if key != 'description':
                    self._error(
                        f'{entry_path}.documentation.{key}',
                        'is not a documentation setting; a value takes description',
                    )
            description = documentation.get('description')
            if description is not None:
                if not isinstance(description, str):
                    self._error(f'{entry_path}.documentation.description', 'must be a string')
                described.append((str(value), description))
        return values, tuple(described)

    def _check_default(self, arg_type, default, values, minimum, maximum, pattern, path) -> Any:
        if arg_type == 'enum':
            if str(default) not in values:
                self._error(path, f'must be one of {", ".join(values)}')
            return str(default)
        if arg_type == 'boolean':
            if not isinstance(default, bool):
                self._error(path, 'must be true or false')
            return default
        if arg_type == 'integer':
            if not _is_int(default):
                self._error(path, 'must be an integer')
            if (minimum is not None and default < minimum) or (maximum is not None and default > maximum):
                self._error(path, 'is outside the argument\'s min and max')
            return default
        if arg_type == 'symbol':
            if not isinstance(default, str) or not is_valid_label(default):
                self._error(path, 'must be a label or constant name')
            return default
        if not isinstance(default, str):
            self._error(path, 'must be a string')
        if pattern is not None and pattern.fullmatch(default) is None:
            self._error(path, f'does not match the argument\'s pattern {pattern.pattern}')
        return default

    def _condition(
        self,
        config: dict,
        key: str,
        path: str,
        arguments: dict[str, dict],
        exclude: str | None = None,
    ) -> Condition | None:
        if key not in config:
            return None
        condition_path = f'{path}.{key}'
        condition = config[key]
        if not isinstance(condition, dict) or len(condition) == 0:
            self._error(condition_path, 'must be a mapping of enum argument names to lists of values')
        tests = []
        for arg_name, allowed in condition.items():
            target = arguments.get(arg_name)
            if target is None or target['type'] != 'enum' or arg_name == exclude:
                self._error(f'{condition_path}.{arg_name}', 'must name another enum argument of this annotation')
            if not isinstance(allowed, list):
                allowed = [allowed]
            allowed = tuple(str(value) for value in allowed)
            for value in allowed:
                if value not in target['values']:
                    self._error(
                        f'{condition_path}.{arg_name}',
                        f'"{value}" is not a value of argument \'{arg_name}\'',
                    )
            tests.append((arg_name, allowed))
        return Condition(tuple(tests))

    def _words_value(self, value, path: str) -> int:
        if not _is_int(value) or value < 0:
            self._error(path, 'must be a word count (an integer of at least 0)')
        return value

    def _range_value(self, value, path: str) -> tuple[int, int]:
        if (
            not isinstance(value, list)
            or len(value) != 2
            or not all(_is_int(item) for item in value)
            or value[0] > value[1]
        ):
            self._error(path, 'must be a [min, max] pair of integers with min no greater than max')
        return (value[0], value[1])

    def _value_range_rules(self, arguments: dict[str, ArgumentSpec]) -> tuple[SelectedRule, ...]:
        """``value_range`` is one rule, or a list of rules of which the first whose ``when``
        holds applies, so that different arguments can select their range differently."""
        config = self._config.get('value_range')
        if config is None:
            return ()
        if not isinstance(config, list):
            return (self._selected_rule('value_range', 'range', arguments, self._range_value),)
        if not config:
            self._error(f'{self._path}.value_range', 'must be a rule or a non-empty list of rules')
        return tuple(
            self._selected_rule(
                'value_range', 'range', arguments, self._range_value,
                rule=rule, rule_path=f'{self._path}.value_range[{index}]',
            )
            for index, rule in enumerate(config)
        )

    def _selected_rule(
        self,
        key: str,
        value_key: str,
        arguments: dict[str, ArgumentSpec],
        convert: Callable[[Any, str], Any],
        rule: Any = None,
        rule_path: str | None = None,
    ) -> SelectedRule | None:
        if rule is None:
            if key not in self._config:
                return None
            rule = self._config[key]
        rule_path = rule_path or f'{self._path}.{key}'
        if not isinstance(rule, dict):
            self._error(rule_path, 'must be a mapping')
        argument_basics = {name: {'type': spec.type, 'values': spec.values} for name, spec in arguments.items()}
        when = self._condition(rule, 'when', rule_path, argument_basics)
        if value_key not in rule:
            self._error(f'{rule_path}.{value_key}', 'is required')
        value = rule[value_key]
        value_path = f'{rule_path}.{value_key}'

        if not isinstance(value, dict):
            return SelectedRule(kind=key, when=when, fixed=convert(value, value_path))

        times = None
        if 'times' in value:
            if key != 'data_size':
                self._error(f'{value_path}.times', 'is only allowed in data_size')
            times = value['times']
            target = arguments.get(times)
            if target is None or target.type != 'integer':
                self._error(f'{value_path}.times', 'must name an integer argument of this annotation')
        terminated_when = None
        if 'terminated_when' in rule:
            if key != 'data_size':
                self._error(f'{rule_path}.terminated_when', 'is only allowed in data_size')
            if times is None:
                self._error(f'{rule_path}.terminated_when', f'needs {value_path}.times, the argument it computes')
            terminated_when = self._condition(rule, 'terminated_when', rule_path, argument_basics)
        infer_times = None
        if 'infer_times' in value:
            if times is None:
                self._error(f'{value_path}.infer_times', 'needs times, the argument it computes')
            infer_times = value['infer_times']
            target = arguments.get(infer_times)
            if target is None or target.type != 'boolean':
                self._error(f'{value_path}.infer_times', 'must name a boolean argument of this annotation')
        selectors = [name for name in value if name not in ('times', 'infer_times')]
        if len(selectors) != 1:
            self._error(value_path, 'must select its value by exactly one enum argument')
        selector = selectors[0]
        target = arguments.get(selector)
        if target is None or target.type != 'enum':
            self._error(f'{value_path}.{selector}', 'must name an enum argument of this annotation')
        table_config = value[selector]
        if not isinstance(table_config, dict):
            self._error(f'{value_path}.{selector}', 'must map each value of the argument to its setting')
        table = []
        for enum_value in target.values:
            if enum_value not in {str(k) for k in table_config}:
                self._error(f'{value_path}.{selector}', f'has no entry for "{enum_value}"')
        for table_key, table_value in table_config.items():
            if str(table_key) not in target.values:
                self._error(
                    f'{value_path}.{selector}.{table_key}',
                    f'is not a value of argument \'{selector}\'',
                )
            # A null entry means the value is not allowed where the rule applies.
            converted = None if table_value is None else convert(table_value, f'{value_path}.{selector}.{table_key}')
            table.append((str(table_key), converted))
        return SelectedRule(
            kind=key, when=when, selector=selector, table=tuple(table), times=times, infer_times=infer_times,
            terminated_when=terminated_when,
        )


def load_annotation_namespaces(section, error: ConfigErrorFn) -> dict[str, AnnotationNamespace]:
    """Return the built-in namespaces plus those the ``annotations`` section declares."""
    namespaces = dict(BUILTIN_NAMESPACES)
    if section is None:
        return namespaces
    if not isinstance(section, dict):
        error('annotations', 'must be a mapping of annotation namespace names')
    for name, config in section.items():
        path = f'annotations.{name}'
        if not isinstance(name, str) or PATTERN_NAMESPACE_NAME.match(name) is None:
            error(path, 'is not a valid annotation namespace name (start with a letter; use letters, digits and "_")')
        if name in BUILTIN_NAMESPACES:
            error(path, f'"{name}" is a framework annotation namespace and cannot be declared by a configuration')
        if not isinstance(config, dict):
            error(path, 'must be a mapping')
        namespaces[name] = _NamespaceLoader(name, config, error).load()
    return namespaces
