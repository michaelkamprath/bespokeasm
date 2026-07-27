"""Flow-analysis symbols stored in lexical symbol scopes."""
from dataclasses import dataclass

from bespokeasm.assembler.line_identifier import LineIdentifier


class FlowSymbolError(ValueError):
    """An expression dependency that must be reported as a flow diagnostic."""


@dataclass
class CounterCoordinate:
    """A named counter position whose validity can only change to false."""

    label: str
    value: int
    counter_name: str
    counter_instance_id: int
    declared_offset: int
    line_id: LineIdentifier
    is_valid: bool = True
