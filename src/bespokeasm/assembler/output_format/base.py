"""The interface every pretty-print output format implements, built-in or config-defined."""
from __future__ import annotations

import os
from abc import ABC
from abc import abstractmethod
from dataclasses import dataclass
from typing import Any
from typing import TYPE_CHECKING

from bespokeasm.assembler.annotations.model import ExportModel
from bespokeasm.assembler.line_object import LineObject

if TYPE_CHECKING:
    from bespokeasm.assembler.model import AssemblerModel


@dataclass
class RenderContext:
    """Everything a format may read about one assembly. Formats never re-parse source."""
    model: AssemblerModel
    source_file: str
    line_objects: list[LineObject]          # compilable lines, in address order
    source_line_objects: list[LineObject]   # every parsed line, in source order
    export_model: ExportModel

    @property
    def source_file_name(self) -> str:
        return os.path.basename(self.source_file)


class OutputFormat(ABC):
    """A ``-t`` value: a name, documentation, requirements, and a render step."""

    def __init__(
        self,
        name: str,
        description: str | None = None,
        requires_word_size: int | None = None,
        is_builtin: bool = False,
    ) -> None:
        self._name = name
        self._description = description
        self._requires_word_size = requires_word_size
        self._is_builtin = is_builtin

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str | None:
        return self._description

    @property
    def requires_word_size(self) -> int | None:
        return self._requires_word_size

    @property
    def is_builtin(self) -> bool:
        return self._is_builtin

    def source_options(self) -> list[tuple[Any, Any]]:
        """The options source may set for this format with `#output-format`, each with its default."""
        return []

    @property
    def predefined_memory_zones(self) -> list[dict]:
        """Memory zones that exist only while this format is selected."""
        return []

    @property
    def predefined_constants(self) -> list[dict]:
        """Constants that exist only while this format is selected."""
        return []

    def check_requirements(self, model: AssemblerModel) -> None:
        if self._requires_word_size is not None and model.word_size != self._requires_word_size:
            model.diagnostic_reporter.error(
                None,
                f"output format '{self._name}' requires {self._requires_word_size}-bit words; "
                f'this instruction set has {model.word_size}-bit words',
            )

    @abstractmethod
    def render(self, context: RenderContext) -> str:
        """Return the complete output text."""
