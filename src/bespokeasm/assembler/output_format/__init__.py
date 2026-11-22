"""Pretty-print output formats: the built-in ones and those an ISA configuration defines.

Every format implements ``OutputFormat`` (``base``). Built-in formats are Python
(``builtin``); configuration formats are a template plus sections (``defined``,
``template``, ``generators``). ``resolve_output_format`` selects the ``-t`` value.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from bespokeasm.assembler.output_format.base import OutputFormat
from bespokeasm.assembler.output_format.builtin import BUILTIN_FORMATS

if TYPE_CHECKING:
    from bespokeasm.assembler.model import AssemblerModel


def available_output_formats(model: AssemblerModel) -> dict[str, OutputFormat]:
    """Every ``-t`` value this ISA accepts: the built-in formats, then the configuration's."""
    formats = dict(BUILTIN_FORMATS)
    formats.update(model.output_formats)
    return formats


def find_output_format(model: AssemblerModel, name: str) -> OutputFormat | None:
    """Built-in names match without regard to case; configuration names must match exactly."""
    if name in model.output_formats:
        return model.output_formats[name]
    return BUILTIN_FORMATS.get(name.lower())


def resolve_output_format(model: AssemblerModel, name: str) -> OutputFormat:
    output_format = find_output_format(model, name)
    if output_format is None:
        known = ', '.join(available_output_formats(model))
        model.diagnostic_reporter.error(
            None,
            f"this instruction set does not define output format '{name}'; available formats: {known}",
        )
    output_format.check_requirements(model)
    return output_format
