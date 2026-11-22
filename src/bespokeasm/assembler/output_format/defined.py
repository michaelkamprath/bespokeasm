"""Config-defined output formats: a template plus named sections, from ``output_formats``."""
from __future__ import annotations

import re
from typing import Any

from bespokeasm import BESPOKEASM_VERSION_STR
from bespokeasm.assembler.output_format.base import OutputFormat
from bespokeasm.assembler.output_format.base import RenderContext
from bespokeasm.assembler.output_format.builtin import BUILTIN_FORMAT_NAMES
from bespokeasm.assembler.output_format.generators import build_generator
from bespokeasm.assembler.output_format.generators import Generator
from bespokeasm.assembler.output_format.generators import LoadEnvironment
from bespokeasm.assembler.output_format.template import NO_FORMAT_SPEC
from bespokeasm.assembler.output_format.template import Template

PATTERN_NAME = re.compile(r'^[A-Za-z][A-Za-z0-9_]*$')
TEMPLATE_FIELDS = ('source_file', 'isa_name', 'isa_version', 'bespokeasm_version')


class DefinedFormat(OutputFormat):
    def __init__(
        self,
        name: str,
        description: str | None,
        requires_word_size: int | None,
        template: Template,
        sections: dict[str, Generator],
    ) -> None:
        super().__init__(name, description, requires_word_size, is_builtin=False)
        self._template = template
        self._sections = sections

    @property
    def sections(self) -> dict[str, Generator]:
        return dict(self._sections)

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


def _load_format(name: str, config: Any, env: LoadEnvironment) -> DefinedFormat:
    path = f'output_formats.{name}'
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

    requires_word_size = config.get('requires_word_size')
    if requires_word_size is not None and (
        isinstance(requires_word_size, bool) or not isinstance(requires_word_size, int) or requires_word_size < 1
    ):
        env.error(f'{path}.requires_word_size', 'must be a positive integer')

    sections_config = config.get('sections') or {}
    if not isinstance(sections_config, dict):
        env.error(f'{path}.sections', 'must be a mapping of section names')
    sections: dict[str, Generator] = {}
    for section_name, section_config in sections_config.items():
        section_path = f'{path}.sections.{section_name}'
        if not isinstance(section_name, str) or PATTERN_NAME.match(section_name) is None:
            env.error(section_path, 'is not a valid section name (start with a letter; use letters, digits and "_")')
        if section_name in TEMPLATE_FIELDS:
            env.error(section_path, f"has the same name as the template field '{section_name}'")
        sections[section_name] = build_generator(name, section_name, section_config, env)

    if 'template' not in config:
        env.error(f'{path}.template', 'is required')
    fields: dict[str, Any] = {field: 'x' for field in TEMPLATE_FIELDS}
    fields.update({section: NO_FORMAT_SPEC for section in sections})
    template = Template.parse(config['template'], fields, lambda problem: env.error(f'{path}.template', problem))
    for section_name in sections:
        if section_name not in template.field_names:
            env.warn(f'{path}.sections.{section_name}', 'is not used by the template, so it is never written')

    return DefinedFormat(name, description, requires_word_size, template, sections)


def load_output_formats(section: Any, env: LoadEnvironment) -> dict[str, DefinedFormat]:
    """Load the ``output_formats`` section of a configuration."""
    if section is None:
        return {}
    if not isinstance(section, dict):
        env.error('output_formats', 'must be a mapping of output format names')
    formats: dict[str, DefinedFormat] = {}
    builtin_names = {name.lower() for name in BUILTIN_FORMAT_NAMES}
    for name, config in section.items():
        path = f'output_formats.{name}'
        if not isinstance(name, str) or PATTERN_NAME.match(name) is None:
            env.error(path, 'is not a valid output format name (start with a letter; use letters, digits and "_")')
        if name.lower() in builtin_names:
            env.error(path, f"cannot be defined: '{name}' is a built-in output format")
        formats[name] = _load_format(name, config, env)
    return formats
