from __future__ import annotations

import os

from bespokeasm.assembler.diagnostic_reporter import DiagnosticReporter
from bespokeasm.assembler.line_identifier import LineIdentifier
from bespokeasm.assembler.symbol_scope import SymbolScope
from bespokeasm.assembler.symbol_scope import SymbolScopeType
from bespokeasm.assembler.symbol_scope.flow_symbols import CounterCoordinate


class NamedSymbolScope(SymbolScope):
    """Represents a named scope."""

    def __init__(self, name: str, prefix: str, scope_reference: str, defined_at: LineIdentifier):
        super().__init__(SymbolScopeType.NAMED, None, scope_reference)
        self._name = name
        self._prefix = prefix
        self._defined_at = defined_at

    @property
    def name(self) -> str:
        return self._name

    @property
    def prefix(self) -> str:
        return self._prefix

    @property
    def defined_at(self) -> LineIdentifier:
        return self._defined_at

    def __str__(self) -> str:
        return f'NamedSymbolScope<{self.name}, prefix="{self.prefix}">'


class NamedScopeManager:
    """Manage named lexical symbol scopes throughout assembly."""

    def __init__(self, diagnostic_reporter: DiagnosticReporter):
        if diagnostic_reporter is None:
            raise ValueError('DiagnosticReporter is required for NamedScopeManager')
        # Global scope definitions: {scope_name: NamedScopeDefinition}
        self._scope_definitions: dict[str, NamedSymbolScope] = {}
        self._used_prefixes: set[str] = set()
        self._diagnostic_reporter = diagnostic_reporter

    @property
    def diagnostic_reporter(self) -> DiagnosticReporter:
        return self._diagnostic_reporter

    def create_scope(self, name: str, prefix: str, defined_at: LineIdentifier) -> None:
        """Create a new named scope definition."""
        # Validate scope name
        if not name or ' ' in name or '\t' in name:
            self._diagnostic_reporter.error(
                defined_at,
                f"Scope name '{name}' cannot contain whitespace",
            )

        # Validate prefix
        if not prefix or ' ' in prefix or '\t' in prefix:
            self._diagnostic_reporter.error(
                defined_at,
                f"Scope prefix '{prefix}' cannot contain whitespace",
            )

        # Validate prefix doesn't start with '.' to avoid confusion with local scope
        if prefix.startswith('.'):
            self._diagnostic_reporter.error(
                defined_at,
                f"Scope prefix '{prefix}' cannot start with '.' as this conflicts with local scope syntax",
            )

        # Check for duplicate scope name
        if name in self._scope_definitions:
            existing_def = self._scope_definitions[name]
            self._diagnostic_reporter.error(
                defined_at,
                f"Scope '{name}' already defined at {existing_def.defined_at}",
            )

        # Check for duplicate prefix (warn if same scope, error if different scope)
        if prefix in self._used_prefixes:
            existing_scope = next((scope for scope in self._scope_definitions.values() if scope.prefix == prefix), None)
            if existing_scope is not None:
                if existing_scope.name == name:
                    # warn if same scope
                    self._diagnostic_reporter.warn(
                        defined_at,
                        f"Scope '{name}' defined with prefix '{prefix}' "
                        f'but is already defined at {existing_scope.defined_at}',
                    )
                else:
                    # error if different scope
                    self._diagnostic_reporter.error(
                        defined_at,
                        f"Scope '{name}' defined with prefix '{prefix}' that "
                        f"is already used by scope '{existing_scope.name}' defined at {existing_scope.defined_at}",
                    )

        # Create the scope definition
        definition = NamedSymbolScope(name, prefix, name, defined_at)
        self._scope_definitions[name] = definition
        self._used_prefixes.add(prefix)

    def get_label_value(
        self,
        label: str,
        current_scope: SymbolScope,
        active_named_scopes: ActiveNamedScopeList,
        line_id: LineIdentifier,
    ) -> int:
        """Get the value of a label from active named scopes or current scope.

        Searches active named scopes in order (most recently activated first) for a scope
        whose prefix matches the label. If found, returns the label value from that scope.
        If not found in any active named scope, delegates to current_scope.get_label_value().

        Note: This method may raise SystemExit if the label is not found.
        """
        for name in active_named_scopes:
            if name in self._scope_definitions:
                scope = self._scope_definitions[name]
                if label.startswith(scope.prefix):
                    return scope.get_label_value(label, line_id)
        return current_scope.get_label_value(label, line_id)

    def set_label_value(
        self,
        label: str,
        value: int,
        line_id: LineIdentifier,
        active_named_scopes: ActiveNamedScopeList,
        is_constant: bool = False,
    ) -> bool:
        """Set the value of a label found in the active named scopes.

        If an appropriate named scope for label prefix is not found,
        returns False.

        Important: Labels and constants can only be created in a named scope
        if they are defined in the same file where that named scope was created.
        This restriction allows libraries to control which labels belong to
        their namespace. If a label with a named scope's prefix is defined in
        a different file, it will fall back to the normal scope hierarchy
        (global/file/local) instead of being added to the named scope.
        """
        for name in active_named_scopes:
            if name in self._scope_definitions:
                scope = self._scope_definitions[name]
                if label.startswith(scope.prefix):
                    # Labels and constants can only be created in the same file
                    # where the named scope was created. This prevents external
                    # code from polluting a library's namespace.
                    # Normalize paths for comparison (resolve symlinks and relative paths)
                    scope_file = (
                        os.path.realpath(scope.defined_at.filename)
                        if scope.defined_at.filename
                        else None
                    )
                    label_file = (
                        os.path.realpath(line_id.filename)
                        if line_id.filename
                        else None
                    )
                    if scope_file != label_file:
                        # Label prefix matches but wrong file
                        # Let it fall back to normal scope hierarchy
                        return False
                    scope.set_label_value(label, value, line_id, SymbolScopeType.NAMED)
                    return True
        return False

    def get_counter_coordinate(
        self,
        label: str,
        current_scope: SymbolScope,
        active_named_scopes: ActiveNamedScopeList,
    ) -> CounterCoordinate | None:
        """Resolve a coordinate from active named scopes, then lexical scopes."""
        for name in active_named_scopes:
            if name in self._scope_definitions:
                scope = self._scope_definitions[name]
                if label.startswith(scope.prefix):
                    return scope.get_counter_coordinate(label)
        return current_scope.get_counter_coordinate(label)

    def set_counter_coordinate(
        self,
        coordinate: CounterCoordinate,
        active_named_scopes: ActiveNamedScopeList,
    ) -> bool:
        """Insert a coordinate into a matching active named scope when eligible."""
        for name in active_named_scopes:
            if name not in self._scope_definitions:
                continue
            scope = self._scope_definitions[name]
            if not coordinate.label.startswith(scope.prefix):
                continue
            scope_file = (
                os.path.realpath(scope.defined_at.filename)
                if scope.defined_at.filename
                else None
            )
            coordinate_file = (
                os.path.realpath(coordinate.line_id.filename)
                if coordinate.line_id.filename
                else None
            )
            if scope_file != coordinate_file:
                return False
            scope.set_counter_coordinate(coordinate, scope=SymbolScopeType.NAMED)
            return True
        return False

    def get_scope_definition(self, name: str) -> NamedSymbolScope | None:
        """Get a named scope definition by name.

        Returns the NamedSymbolScope if it exists, None otherwise.
        This method is used internally and by tests.
        """
        return self._scope_definitions.get(name)


class ActiveNamedScopeList(list[str]):
    """Convenience class to manage active named scopes when processing an assembly file."""

    @classmethod
    def empty(cls, diagnostic_reporter: DiagnosticReporter) -> ActiveNamedScopeList:
        """Create an empty active named scope list for preprocessor evaluation."""
        return cls(NamedScopeManager(diagnostic_reporter))

    def __init__(self, named_scope_manager: NamedScopeManager):
        super().__init__()
        self._named_scope_manager = named_scope_manager

    def copy(self) -> ActiveNamedScopeList:
        """Copy the active named scopes list, keeping a reference to the same named scope manager."""
        new_list = ActiveNamedScopeList(self._named_scope_manager)
        new_list.extend(self)
        return new_list

    def activate_named_scope(self, name: str):
        """Activates a named scope for this line object. If already active, move to top of precedence."""
        if name in self:
            self.remove(name)
        self.insert(0, name)

    def deactivate_named_scope(self, name: str):
        """Deactivates a named scope for this line object. If not active, do nothing."""
        if name in self:
            self.remove(name)

    def clear_active_named_scopes(self):
        """Clears all active named scopes for this line object."""
        self.clear()

    @property
    def named_scope_manager(self) -> NamedScopeManager:
        return self._named_scope_manager
