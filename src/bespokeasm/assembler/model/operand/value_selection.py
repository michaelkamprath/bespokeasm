"""How `select_by_value` operands are decided while an instruction line is matched.

An `address` operand with `select_by_value: true` matches only when its value lies in its memory
zone. Values aren't known when a line is first matched, so the line's matching runs under a
`ValueSelection` that says how to decide: defer (don't match yet), assume (match on syntax alone),
or evaluate the value against the symbols that pass 1 has set. With no selection active, as when
explaining a mismatch, the operand matches on syntax alone, like any other address operand.
"""
import contextlib
import contextvars
from collections.abc import Callable
from collections.abc import Iterator

from bespokeasm.assembler.bytecode.parts import ByteCodePart
from bespokeasm.assembler.bytecode.parts import ExpressionByteCodePart
from bespokeasm.assembler.memory_zone import MemoryZone


class ValueSelection:
    def __init__(self, evaluate: Callable[[ExpressionByteCodePart], int | None] | None, assume: bool) -> None:
        self._evaluate = evaluate
        self._assume = assume
        # Whether an operand was left unmatched because its value wasn't known.
        self.deferred = False
        self._selected: set[int] = set()

    @classmethod
    def deferring(cls) -> 'ValueSelection':
        """Value-selected operands don't match; the line takes another form for now."""
        return cls(None, assume=False)

    @classmethod
    def assuming(cls) -> 'ValueSelection':
        """Value-selected operands match on syntax alone, for a line with no other form."""
        return cls(None, assume=True)

    @classmethod
    def evaluating(cls, evaluate: Callable[[ExpressionByteCodePart], int | None]) -> 'ValueSelection':
        """Value-selected operands match when ``evaluate`` gives a value in their zone; it gives
        None for a value that can't be known yet."""
        return cls(evaluate, assume=False)

    def selects(self, part: ExpressionByteCodePart, zone: MemoryZone) -> bool:
        if self._evaluate is None:
            self.deferred = self.deferred or not self._assume
            selected = self._assume
        else:
            value = self._evaluate(part)
            selected = value is not None and zone.start <= value <= zone.end
        if selected:
            self._selected.add(id(part))
        return selected

    def selected_any(self, parts: list[ByteCodePart]) -> bool:
        """Whether any of ``parts`` is a value-selected operand this selection matched."""
        return any(id(part) in self._selected for part in parts)


_active: contextvars.ContextVar[ValueSelection | None] = contextvars.ContextVar('value_selection', default=None)


@contextlib.contextmanager
def selecting_values(selection: ValueSelection) -> Iterator[ValueSelection]:
    """Match under ``selection``."""
    token = _active.set(selection)
    try:
        yield selection
    finally:
        _active.reset(token)


def selects(part: ExpressionByteCodePart, zone: MemoryZone) -> bool:
    """Whether a value-selected operand with ``part`` as its argument matches."""
    selection = _active.get()
    return True if selection is None else selection.selects(part, zone)
