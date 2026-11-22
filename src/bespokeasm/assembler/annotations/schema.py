"""Annotation namespaces: the ``annotations`` section of an ISA configuration.

An annotation namespace declares which arguments a ``#annotate <namespace>`` line may
carry, which symbols it may be attached to, and the constraints (``data_size`` and
``value_range``) the annotated symbol must satisfy. The framework's own ``listing``
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
    value_range: SelectedRule | None = None
    is_builtin: bool = False

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

    def allowed_range(self, values: dict[str, Any]) -> tuple[int, int] | None:
        """The ``value_range`` these arguments require of a constant, or None."""
        if self.value_range is None:
            return None
        return self.value_range.evaluate(self.name, values)

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
        return self.value_range.basis(values) if self.value_range is not None else ''


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
        'heading': ArgumentSpec('heading', 'string'),
        'page_break': ArgumentSpec('page_break', 'boolean'),
        'collapse': ArgumentSpec('collapse', 'boolean'),
        'hide': ArgumentSpec('hide', 'boolean'),
    },
    is_builtin=True,
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
        documentation = config.get('documentation')
        if documentation is not None:
            if not isinstance(documentation, dict):
                self._error(f'{self._path}.documentation', 'must be a mapping')
            description = documentation.get('description')
            if description is not None and not isinstance(description, str):
                self._error(f'{self._path}.documentation.description', 'must be a string')

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
                **basics,
            )

        data_size = self._selected_rule('data_size', 'words', arguments, self._words_value)
        value_range = self._selected_rule('value_range', 'range', arguments, self._range_value)
        if data_size is not None and 'label' not in applies_to:
            self._error(f'{self._path}.data_size', 'only applies to labels, but applies_to does not include label')
        if value_range is not None and 'constant' not in applies_to:
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
        )

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
        if arg_type == 'enum':
            raw_values = config.get('values')
            if not isinstance(raw_values, list) or len(raw_values) == 0:
                self._error(f'{path}.values', 'is required for an enum argument and must be a non-empty list')
            values = tuple(str(value) for value in raw_values)
            if len(set(values)) != len(values):
                self._error(f'{path}.values', 'must not repeat a value')

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
        }

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

    def _selected_rule(
        self,
        key: str,
        value_key: str,
        arguments: dict[str, ArgumentSpec],
        convert: Callable[[Any, str], Any],
    ) -> SelectedRule | None:
        if key not in self._config:
            return None
        rule_path = f'{self._path}.{key}'
        rule = self._config[key]
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
