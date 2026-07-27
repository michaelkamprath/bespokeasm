"""Lexical scopes for assembler symbols.

Labels, constants, and flow-counter coordinates share global, file, local, and
named visibility rules. Each symbol kind retains type-specific lookup so a
coordinate cannot be consumed as an ordinary numeric label.
"""
from __future__ import annotations

import enum
import sys

from bespokeasm.assembler.keywords import ASSEMBLER_KEYWORD_SET
from bespokeasm.assembler.line_identifier import LineIdentifier
from bespokeasm.assembler.symbol_scope.flow_symbols import CounterCoordinate
from bespokeasm.assembler.symbol_scope.flow_symbols import FlowSymbolError as FlowSymbolError

__all__ = [
    'CounterCoordinate',
    'FlowSymbolError',
    'GlobalSymbolScope',
    'SymbolScope',
    'SymbolScopeType',
]


class SymbolScopeType(enum.Enum):
    GLOBAL = 0
    FILE = 1
    LOCAL = 2
    NAMED = 3

    @classmethod
    def get_symbol_scope(cls, symbol_name: str) -> SymbolScopeType:
        """Return the lexical scope implied by a symbol's prefix."""
        if symbol_name.startswith('.'):
            return SymbolScopeType.LOCAL
        elif symbol_name.startswith('_'):
            return SymbolScopeType.FILE
        else:
            return SymbolScopeType.GLOBAL

    @property
    def symbol_prefix(self) -> str:
        """Return the source prefix associated with this lexical scope."""
        if self == SymbolScopeType.LOCAL:
            return '.'
        elif self == SymbolScopeType.FILE:
            return '_'
        else:
            return ''


class SymbolScope:
    class LabelInfo:
        def __init__(self, label: str, value: int, line_id: LineIdentifier) -> None:
            self._label = label
            self._value = value
            self._line_id = line_id

        def __repr__(self) -> str:
            return str(self)

        def __str__(self) -> str:
            return f'LabelInfo< {self.label} = {self.value} >'

        @property
        def label(self) -> str:
            return self._label

        @property
        def value(self) -> int:
            return self._value

        @property
        def line_id(self) -> LineIdentifier:
            return self._line_id

    def __init__(
        self,
        scope_type: SymbolScopeType,
        parent: SymbolScope | None,
        scope_reference: str,
        reserved_keywords: set[str] | frozenset[str] | None = None,
    ) -> None:
        self._type = scope_type
        self._parent = parent
        self._reference = scope_reference
        if reserved_keywords is None and parent is not None:
            reserved_keywords = parent.reserved_keywords
        self._reserved_keywords = frozenset(
            ASSEMBLER_KEYWORD_SET
            if reserved_keywords is None
            else reserved_keywords
        )
        self._labels = {}
        self._counter_coordinates: dict[str, CounterCoordinate] = {}
        self._ignored_counter_coordinates: dict[str, LineIdentifier] = {}
        self._defined_symbol_names: set[str] = set()

    def __repr__(self) -> str:
        return str(self)

    def __str__(self) -> str:
        return f'SymbolScope< {self.type}, {self._reference} >'

    @property
    def parent(self) -> SymbolScope | None:
        return self._parent

    @property
    def type(self) -> SymbolScopeType:
        return self._type

    @property
    def reference(self) -> str:
        return self._reference

    @property
    def reserved_keywords(self) -> frozenset[str]:
        """Return names unavailable to symbols in this assembly session."""
        return self._reserved_keywords

    def get_label_value(self, label: str, line_id: LineIdentifier) -> int:
        if label in self._labels:
            return self._labels[label].value
        elif self.parent is not None:
            return self.parent.get_label_value(label, line_id)
        else:
            return None

    def get_counter_coordinate(self, label: str) -> CounterCoordinate | None:
        """Resolve a coordinate through the same lexical hierarchy as labels."""
        if label in self._counter_coordinates:
            return self._counter_coordinates[label]
        if self.parent is not None:
            return self.parent.get_counter_coordinate(label)
        return None

    def set_counter_coordinate(
        self,
        coordinate: CounterCoordinate,
        scope: SymbolScopeType | None = None,
    ) -> None:
        """Insert a coordinate into its label-style scope without numeric exposure."""
        symbol_scope = SymbolScopeType.get_symbol_scope(coordinate.label) if scope is None else scope
        base_label = coordinate.label[len(symbol_scope.symbol_prefix):]
        if base_label in self.reserved_keywords:
            raise ValueError(
                f"coordinate '{coordinate.label}' cannot use assembler keyword '{base_label}'"
            )
        if symbol_scope.value < self.type.value:
            self.parent.set_counter_coordinate(coordinate, scope=symbol_scope)
        elif symbol_scope == self.type:
            if coordinate.label in self._defined_symbol_names:
                raise ValueError(
                    f"symbol '{coordinate.label}' is defined multiple times at scope {self}"
                )
            self._counter_coordinates[coordinate.label] = coordinate
            self._defined_symbol_names.add(coordinate.label)
        else:
            raise ValueError(
                f"coordinate '{coordinate.label}' is too low of scope for available scopes at this line"
            )

    def record_ignored_counter_coordinate(
        self,
        label: str,
        line_id: LineIdentifier,
    ) -> None:
        """Record a disabled declaration without reserving the normal namespace."""
        symbol_scope = SymbolScopeType.get_symbol_scope(label)
        if symbol_scope.value < self.type.value:
            self.parent.record_ignored_counter_coordinate(label, line_id)
        elif symbol_scope == self.type:
            self._ignored_counter_coordinates[label] = line_id
        else:
            # A disabled local declaration has no valid local scope, but retaining
            # it here still permits a precise diagnostic at a dependent use.
            self._ignored_counter_coordinates[label] = line_id

    def ignored_counter_coordinate_site(self, label: str) -> LineIdentifier | None:
        """Return the declaration site from the disabled-analysis-only index."""
        if label in self._ignored_counter_coordinates:
            return self._ignored_counter_coordinates[label]
        if self.parent is not None:
            return self.parent.ignored_counter_coordinate_site(label)
        return None

    def set_label_value(self, label: str, value: int, line_id: LineIdentifier, scope: SymbolScopeType = None) -> None:
        symbol_scope = SymbolScopeType.get_symbol_scope(label) if scope is None else scope
        # first check to see if label name is a keyword
        # remove label prefix for checking
        base_label = label[len(symbol_scope.symbol_prefix):]
        if base_label in self.reserved_keywords:
            sys.exit(f"ERROR: {line_id} - Label '{label}' is unallowed because it used an assembler keyword '{base_label}'")
        if symbol_scope.value < self.type.value:
            self.parent.set_label_value(label, value, line_id)
        elif symbol_scope == self.type:
            if label not in self._defined_symbol_names:
                self._labels[label] = SymbolScope.LabelInfo(label, value, line_id)
                self._defined_symbol_names.add(label)
            else:
                sys.exit(f"ERROR: {line_id} - Label '{label}' is defined multiple times at scope {self}")
        else:
            # we are only here if the label is too low level for this scope
            # example: local label defined before any global labels
            sys.exit(f"ERROR: {line_id} - Label '{label}' is to low of scope for available scopes at this line.")

    _global_scope = None

    @classmethod
    def global_scope(
        cls,
        register_labels: set[str],
        reserved_keywords: set[str] | frozenset[str] | None = None,
    ) -> SymbolScope:
        effective_keywords = frozenset(
            ASSEMBLER_KEYWORD_SET
            if reserved_keywords is None
            else reserved_keywords
        )
        if (
            cls._global_scope is None
            or cls._global_scope.reserved_keywords != effective_keywords
        ):
            cls._global_scope = GlobalSymbolScope(
                register_labels,
                effective_keywords,
            )
        return cls._global_scope


class GlobalSymbolScope(SymbolScope):
    def __init__(
        self,
        register_labels: set[str],
        reserved_keywords: set[str] | frozenset[str] | None = None,
    ) -> None:
        super().__init__(
            SymbolScopeType.GLOBAL,
            None,
            '--GLOBAL--',
            reserved_keywords,
        )
        self._register_labels = register_labels

    def get_label_value(self, label: str, line_id: LineIdentifier) -> int:
        '''Global scope version first checks whether passed label is actually a register'''
        # check to see if label is a register
        if label in self._register_labels:
            sys.exit(f'ERROR: {line_id} - register label "{label}" used in numeric expression')
        return super().get_label_value(label, line_id)
