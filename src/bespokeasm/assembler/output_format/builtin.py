"""Built-in output formats: the formats every ISA accepts.

``listing``, ``hex`` and ``intel_hex`` are defined, in ``resources/builtin_formats.yaml``, in
the same schema as a configuration's ``output_formats`` section; a configuration may define its
own ``listing``, which replaces the built-in one. ``symbols`` is Python, since a template cannot
escape JSON strings. Both kinds implement ``OutputFormat``, so ``-t``, the docs and the
format registry treat them alike.
"""
from __future__ import annotations

import functools
import importlib.resources as pkg_resources
from typing import NoReturn

from bespokeasm.assembler.output_format.base import OutputFormat
from bespokeasm.assembler.output_format.base import RenderContext

BUILTIN_DEFINITIONS_FILE = 'builtin_formats.yaml'
# Python formats, with their descriptions. They come after the defined formats.
PYTHON_FORMAT_DESCRIPTIONS = {
    'symbols': 'Every label and constant, with annotations, as JSON.',
}
# Built-in formats a configuration may replace with its own definition.
REPLACEABLE_BUILTINS = frozenset({'listing'})


class BuiltinFormatError(Exception):
    """A problem in the shipped built-in format definitions: a BespokeASM bug, not a user error."""


class PrinterFormat(OutputFormat):
    """A built-in format backed by a ``PrettyPrinterFactory`` printer."""

    def __init__(self, name: str) -> None:
        super().__init__(name, PYTHON_FORMAT_DESCRIPTIONS[name], is_builtin=True)

    def render(self, context: RenderContext) -> str:
        from bespokeasm.assembler.pretty_printer.factory import PrettyPrinterFactory

        printer = PrettyPrinterFactory.getPrettyPrinter(
            self.name,
            context.line_objects,
            context.model,
            context.source_file,
            export_model=context.export_model,
            source_line_objects=context.source_line_objects,
        )
        return printer.pretty_print()


def load_builtin_definitions(text: str) -> dict[str, OutputFormat]:
    """Load built-in format definitions from YAML text.

    A built-in format does not depend on the ISA. Its generators are checked against the
    format's own ``requires_word_size``; selecting the format on an ISA with another word
    size is then the format's requirement error, as for a configuration format.
    """
    from ruamel.yaml import YAML

    from bespokeasm.assembler.output_format.defined import load_format_definition
    from bespokeasm.assembler.output_format.generators import LoadEnvironment

    def problem(path: str, message: str) -> NoReturn:
        raise BuiltinFormatError(f'built-in output format definition {path} {message}')

    definitions = YAML(typ='safe').load(text) or {}
    if not isinstance(definitions, dict):
        raise BuiltinFormatError('built-in output format definitions must be a mapping of format names')
    formats: dict[str, OutputFormat] = {}
    for name, config in definitions.items():
        word_size = config.get('requires_word_size') if isinstance(config, dict) else None
        env = LoadEnvironment(
            annotation_namespaces={},
            # A generator that needs a word size the format does not require is a definition bug.
            word_size=word_size if isinstance(word_size, int) else 0,
            error=problem,
            warn=problem,
        )
        formats[name] = load_format_definition(name, config, env, root='builtin', is_builtin=True)
    return formats


@functools.cache
def builtin_formats() -> dict[str, OutputFormat]:
    """Every built-in format by name: the defined formats, listing first, then symbols."""
    from bespokeasm.assembler.output_format import resources

    text = pkg_resources.files(resources).joinpath(BUILTIN_DEFINITIONS_FILE).read_text()
    defined = load_builtin_definitions(text)
    for name in PYTHON_FORMAT_DESCRIPTIONS:
        if name in defined:
            raise BuiltinFormatError(f"built-in output format '{name}' is both defined and written in Python")
    return {**defined, 'symbols': PrinterFormat('symbols')}


def builtin_format_names() -> tuple[str, ...]:
    return tuple(builtin_formats())
