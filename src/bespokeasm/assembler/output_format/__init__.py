"""Pretty-print output formats: the built-in ones and those an ISA configuration defines.

Every format implements ``OutputFormat`` (``base``). A defined format is a template plus
sections (``defined``, ``template``, ``generators``): every configuration format, and most
built-in ones (``builtin``, from ``resources/builtin_formats.yaml``). A Python format renders
in code, as the built-in ``symbols`` does. ``resolve_output_format`` selects the ``-t`` value.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from bespokeasm.assembler.output_format.base import OutputFormat
from bespokeasm.assembler.output_format.builtin import builtin_formats
from bespokeasm.assembler.output_format.builtin import REPLACEABLE_BUILTINS

if TYPE_CHECKING:
    from bespokeasm.assembler.model import AssemblerModel


def available_output_formats(model: AssemblerModel) -> dict[str, OutputFormat]:
    """Every ``-t`` value this ISA accepts: the built-in formats, then the configuration's."""
    formats = dict(builtin_formats())
    formats.update(model.output_formats)
    return formats


def find_output_format(model: AssemblerModel, name: str) -> OutputFormat | None:
    """Built-in names match without regard to case; configuration names must match exactly.
    A configuration format that replaces a built-in one takes its place under any case."""
    if name in model.output_formats:
        return model.output_formats[name]
    builtin_name = name.lower()
    if builtin_name in REPLACEABLE_BUILTINS and builtin_name in model.output_formats:
        return model.output_formats[builtin_name]
    return builtin_formats().get(builtin_name)


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
