"""Config-defined output formats: a template plus named sections, from ``output_formats``.

A format can name a shared set from ``output_format_shared`` with ``shared``. The format is
then the set with the format's own keys applied over it: ``predefined`` merges by item name,
and ``sections`` merges by section name and then by option key. Every merged value keeps the
config path it was written at, so an error names that key.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from bespokeasm import BESPOKEASM_VERSION_STR
from bespokeasm.assembler.output_format.base import OutputFormat
from bespokeasm.assembler.output_format.base import RenderContext
from bespokeasm.assembler.output_format.builtin import builtin_format_names
from bespokeasm.assembler.output_format.generators import build_generator
from bespokeasm.assembler.output_format.generators import Generator
from bespokeasm.assembler.output_format.generators import LoadEnvironment
from bespokeasm.assembler.output_format.template import NO_FORMAT_SPEC
from bespokeasm.assembler.output_format.template import Template

PATTERN_NAME = re.compile(r'^[A-Za-z][A-Za-z0-9_]*$')
TEMPLATE_FIELDS = ('source_file', 'isa_name', 'isa_version', 'bespokeasm_version')
# The kinds of item a format or shared set may predefine, with how a message names one.
PREDEFINED_KINDS = {'memory_zones': 'memory zone', 'constants': 'constant'}
# Keys only a format may have; a shared set may hold any other format key.
FORMAT_ONLY_KEYS = ('template', 'documentation', 'shared')
GLOBAL_ZONE_NAME = 'GLOBAL'


class DefinedFormat(OutputFormat):
    def __init__(
        self,
        name: str,
        description: str | None,
        requires_word_size: int | None,
        template: Template,
        sections: dict[str, Generator],
        shared: str | None = None,
        predefined: dict[str, list[dict]] | None = None,
        is_builtin: bool = False,
    ) -> None:
        super().__init__(name, description, requires_word_size, is_builtin=is_builtin)
        self._template = template
        self._sections = sections
        self._shared = shared
        self._predefined = predefined or {}

    @property
    def sections(self) -> dict[str, Generator]:
        return dict(self._sections)

    @property
    def shared(self) -> str | None:
        """The shared set this format names, if any."""
        return self._shared

    @property
    def predefined_memory_zones(self) -> list[dict]:
        return list(self._predefined.get('memory_zones', []))

    @property
    def predefined_constants(self) -> list[dict]:
        return list(self._predefined.get('constants', []))

    def render(self, context: RenderContext) -> str:
        values: dict[str, Any] = {
            'source_file': context.source_file_name,
            'isa_name': context.model.isa_name,
            'isa_version': context.model.isa_version,
            'bespokeasm_version': BESPOKEASM_VERSION_STR,
        }
        for name, generator in self._sections.items():
            values[name] = generator.render(context)
        return self._template.render(values)


@dataclass
class _Located:
    """A config value and the path it was written at."""
    value: Any
    path: str


@dataclass
class _Section:
    path: str                       # the format's section when it has one, else the shared set's
    options: dict[str, Any]
    option_paths: dict[str, str]
    in_format: bool                 # whether the format itself declares this section


def _check_requires_word_size(config: dict, path: str, env: LoadEnvironment) -> None:
    value = config.get('requires_word_size')
    if value is not None and (isinstance(value, bool) or not isinstance(value, int) or value < 1):
        env.error(f'{path}.requires_word_size', 'must be a positive integer')


def _check_sections(config: dict, path: str, env: LoadEnvironment) -> dict[str, dict]:
    sections = config.get('sections') or {}
    if not isinstance(sections, dict):
        env.error(f'{path}.sections', 'must be a mapping of section names')
    for section_name, section in sections.items():
        section_path = f'{path}.sections.{section_name}'
        if not isinstance(section_name, str) or PATTERN_NAME.match(section_name) is None:
            env.error(section_path, 'is not a valid section name (start with a letter; use letters, digits and "_")')
        if section_name in TEMPLATE_FIELDS:
            env.error(section_path, f"has the same name as the template field '{section_name}'")
        if not isinstance(section, dict):
            env.error(section_path, 'must be a mapping with a generator and its options')
    return sections


def _check_predefined(config: dict, path: str, env: LoadEnvironment) -> dict[str, list[_Located]]:
    """Check a ``predefined`` mapping and return its items by kind, each with its path."""
    predefined = config.get('predefined')
    if predefined is None:
        return {}
    predefined_path = f'{path}.predefined'
    if not isinstance(predefined, dict):
        env.error(predefined_path, 'must be a mapping')
    for key in predefined:
        if key not in PREDEFINED_KINDS:
            env.error(
                f'{predefined_path}.{key}',
                'is not allowed here; an output format can predefine only memory_zones and constants',
            )
    if env.check_predefined is not None:
        env.check_predefined(predefined, predefined_path)
    items: dict[str, list[_Located]] = {}
    for kind, description in PREDEFINED_KINDS.items():
        seen: set[str] = set()
        entries = predefined.get(kind) or []
        if not isinstance(entries, list):
            env.error(f'{predefined_path}.{kind}', 'must be a list')
        for index, entry in enumerate(entries):
            name = entry.get('name') if isinstance(entry, dict) else None
            if not isinstance(name, str):
                env.error(f'{predefined_path}.{kind}[{index}]', 'must be a mapping with a "name" string')
            entry_path = f'{predefined_path}.{kind}[{name}]'
            if name in seen:
                env.error(entry_path, f"defines the {description} '{name}' a second time")
            seen.add(name)
            taken = env.predefined_names.get(kind, {}).get(name)
            if kind == 'memory_zones' and name == GLOBAL_ZONE_NAME:
                taken = 'built-in memory zone'
            if taken is not None:
                env.error(entry_path, f"cannot be defined: '{name}' is already a {taken}")
            items.setdefault(kind, []).append(_Located(dict(entry), entry_path))
    return items


def _load_shared_sets(section: Any, env: LoadEnvironment) -> dict[str, dict]:
    if section is None:
        return {}
    if not isinstance(section, dict):
        env.error('output_format_shared', 'must be a mapping of shared set names')
    for name, config in section.items():
        path = f'output_format_shared.{name}'
        if not isinstance(name, str) or PATTERN_NAME.match(name) is None:
            env.error(path, 'is not a valid shared set name (start with a letter; use letters, digits and "_")')
        if not isinstance(config, dict):
            env.error(path, 'must be a mapping')
        for key in FORMAT_ONLY_KEYS:
            if key in config:
                env.error(f'{path}.{key}', 'is not allowed in a shared set; only an output format can have it')
        _check_requires_word_size(config, path, env)
        _check_sections(config, path, env)
        _check_predefined(config, path, env)
    return section


def _merge_predefined(
    base: dict[str, list[_Located]],
    own: dict[str, list[_Located]],
) -> dict[str, list[_Located]]:
    """Merge by item name: the format's item replaces the set's item of that name, and a new name adds one."""
    merged: dict[str, list[_Located]] = {}
    for kind in PREDEFINED_KINDS:
        items = list(base.get(kind, []))
        index = {item.value['name']: position for position, item in enumerate(items)}
        for item in own.get(kind, []):
            if item.value['name'] in index:
                items[index[item.value['name']]] = item
            else:
                items.append(item)
        if items:
            merged[kind] = items
    return merged


def _merge_sections(
    base: dict[str, dict],
    base_path: str | None,
    own: dict[str, dict],
    path: str,
) -> dict[str, _Section]:
    """Merge by section name, then by option key."""
    merged: dict[str, _Section] = {}
    for section_name, options in base.items():
        section_path = f'{base_path}.sections.{section_name}'
        merged[section_name] = _Section(
            path=section_path,
            options=dict(options),
            option_paths={key: f'{section_path}.{key}' for key in options},
            in_format=False,
        )
    for section_name, options in own.items():
        section_path = f'{path}.sections.{section_name}'
        section = merged.setdefault(section_name, _Section(section_path, {}, {}, in_format=True))
        section.path = section_path
        section.in_format = True
        for key, value in options.items():
            section.options[key] = value
            section.option_paths[key] = f'{section_path}.{key}'
    return merged


def load_format_definition(
    name: str,
    config: Any,
    env: LoadEnvironment,
    shared_sets: dict[str, dict] | None = None,
    root: str = 'output_formats',
    is_builtin: bool = False,
) -> DefinedFormat:
    """Load one format definition. ``root`` is the config path of the section that holds it."""
    shared_sets = shared_sets or {}
    path = f'{root}.{name}'
    if not isinstance(config, dict):
        env.error(path, 'must be a mapping')

    description = None
    documentation = config.get('documentation')
    if documentation is not None:
        if not isinstance(documentation, dict):
            env.error(f'{path}.documentation', 'must be a mapping')
        description = documentation.get('description')
        if description is not None and not isinstance(description, str):
            env.error(f'{path}.documentation.description', 'must be a string')

    shared = config.get('shared')
    base: dict = {}
    base_path = None
    if shared is not None:
        if not isinstance(shared, str) or shared not in shared_sets:
            known = (
                f'shared sets are {", ".join(shared_sets)}' if shared_sets
                else 'this configuration has no output_format_shared section'
            )
            env.error(f'{path}.shared', f"names unknown shared set '{shared}'; {known}")
        base = shared_sets[shared]
        base_path = f'output_format_shared.{shared}'

    _check_requires_word_size(config, path, env)
    requires_word_size = config.get('requires_word_size', base.get('requires_word_size'))

    own_sections = _check_sections(config, path, env)
    sections = _merge_sections(base.get('sections') or {}, base_path, own_sections, path)

    own_predefined = _check_predefined(config, path, env)
    base_predefined = _check_predefined(base, base_path, env) if base_path is not None else {}
    predefined = _merge_predefined(base_predefined, own_predefined)

    if 'template' not in config:
        env.error(f'{path}.template', 'is required')
    fields: dict[str, Any] = {field: 'x' for field in TEMPLATE_FIELDS}
    fields.update({section: NO_FORMAT_SPEC for section in sections})
    template = Template.parse(config['template'], fields, lambda problem: env.error(f'{path}.template', problem))

    generators: dict[str, Generator] = {}
    for section_name, section in sections.items():
        if section_name not in template.field_names:
            # A shared set's section that this format does not use is simply not part of it.
            if section.in_format:
                env.warn(section.path, 'is not used by the template, so it is never written')
            continue
        generators[section_name] = build_generator(
            name, section_name, section.options, env, section.path, section.option_paths,
        )

    return DefinedFormat(
        name,
        description,
        requires_word_size,
        template,
        generators,
        shared=shared,
        predefined={kind: [item.value for item in items] for kind, items in predefined.items()},
        is_builtin=is_builtin,
    )


def load_output_formats(section: Any, env: LoadEnvironment, shared_section: Any = None) -> dict[str, DefinedFormat]:
    """Load the ``output_formats`` section of a configuration, with its ``output_format_shared`` sets."""
    shared_sets = _load_shared_sets(shared_section, env)
    if section is None:
        section = {}
    if not isinstance(section, dict):
        env.error('output_formats', 'must be a mapping of output format names')
    formats: dict[str, DefinedFormat] = {}
    builtin_names = {name.lower() for name in builtin_format_names()}
    for name, config in section.items():
        path = f'output_formats.{name}'
        if not isinstance(name, str) or PATTERN_NAME.match(name) is None:
            env.error(path, 'is not a valid output format name (start with a letter; use letters, digits and "_")')
        if name.lower() in builtin_names:
            env.error(path, f"cannot be defined: '{name}' is a built-in output format")
        formats[name] = load_format_definition(name, config, env, shared_sets)
    used_sets = {output_format.shared for output_format in formats.values()}
    for set_name in shared_sets:
        if set_name not in used_sets:
            env.warn(f'output_format_shared.{set_name}', 'is not used by any output format')
    return formats


def format_scoped_names(formats: dict[str, DefinedFormat]) -> dict[str, dict[str, list[str]]]:
    """For each predefined kind, every format-scoped name mapped to the formats that define it."""
    names: dict[str, dict[str, list[str]]] = {kind: {} for kind in PREDEFINED_KINDS}
    for format_name, output_format in formats.items():
        for kind, items in (
            ('memory_zones', output_format.predefined_memory_zones),
            ('constants', output_format.predefined_constants),
        ):
            for item in items:
                names[kind].setdefault(item['name'], []).append(format_name)
    return names


def format_scoped_hint(formats: list[str], what: str = '') -> str:
    """The note added to an unknown-name error for a name only some formats define.
    ``what`` names the kind of item when the error does not already, as in "a constant"."""
    subject = f'it is {what} defined' if what else 'it is defined'
    if len(formats) == 1:
        return f"{subject} only by output format '{formats[0]}' (compile with -p -t {formats[0]})"
    quoted = ', '.join(f"'{name}'" for name in formats)
    return f'{subject} only by output formats {quoted} (compile with -p and -t naming one of them)'
