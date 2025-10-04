from __future__ import annotations

import os
import sys

from bespokeasm.assembler.label_scope import LabelScope
from bespokeasm.assembler.label_scope import LabelScopeType
from bespokeasm.assembler.line_identifier import LineIdentifier


class NamedLabelScope(LabelScope):
    """Represents a named scope."""

    def __init__(self, name: str, prefix: str, scope_reference: str, defined_at: LineIdentifier):
        super().__init__(LabelScopeType.NAMED, None, scope_reference)
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
        return f'NamedLabelScope<{self.name}, prefix="{self.prefix}">'


class NamedScopeManager:
    """Manages named label scopes throughout the assembly process."""

    def __init__(self):
        # Global scope definitions: {scope_name: NamedScopeDefinition}
        self._scope_definitions: dict[str, NamedLabelScope] = {}
        self._used_prefixes: set[str] = set()

    def create_scope(self, name: str, prefix: str, defined_at: LineIdentifier) -> None:
        """Create a new named scope definition."""
        # Validate scope name
        if not name or ' ' in name or '\t' in name:
            sys.exit(f"ERROR: {defined_at} - Scope name '{name}' cannot contain whitespace")

        # Validate prefix
        if not prefix or ' ' in prefix or '\t' in prefix:
            sys.exit(
                f"ERROR: {defined_at} - Scope prefix '{prefix}' cannot contain whitespace"
            )

        # Validate prefix doesn't start with '.' to avoid confusion with local scope
        if prefix.startswith('.'):
            sys.exit(
                f"ERROR: {defined_at} - Scope prefix '{prefix}' cannot start with '.'"
                ' as this conflicts with local scope syntax'
            )

        # Check for duplicate scope name
        if name in self._scope_definitions:
            existing_def = self._scope_definitions[name]
            sys.exit(f"ERROR: {defined_at} - Scope '{name}' already defined at {existing_def.defined_at}")

        # Check for duplicate prefix (warn if same scope, error if different scope)
        if prefix in self._used_prefixes:
            existing_scope = next((scope for scope in self._scope_definitions.values() if scope.prefix == prefix), None)
            if existing_scope is not None:
                if existing_scope.name == name:
                    # warn if same scope
                    print(
                        f"WARNING: {defined_at} - Scope '{name}' defined with prefix '{prefix}' "
                        f'but is already defined at {existing_scope.defined_at}',
                        file=sys.stderr,
                    )
                else:
                    # error if different scope
                    sys.exit(
                        f"ERROR: {defined_at} - Scope '{name}' defined with prefix '{prefix}' that "
                        f"is already used by scope '{existing_scope.name}' defined at {existing_scope.defined_at}"
                    )

        # Create the scope definition
        definition = NamedLabelScope(name, prefix, name, defined_at)
        self._scope_definitions[name] = definition
        self._used_prefixes.add(prefix)

    def get_label_value(
        self,
        label: str,
        current_scope: LabelScope,
        active_named_scopes: ActiveNamedScopeList,
        line_id: LineIdentifier,
    ) -> int:
        """Get the value of a label found in the active named scopes.

        If not found, return None.
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
                    # Normalize paths for comparison (relative vs absolute)
                    scope_file = (
                        os.path.abspath(scope.defined_at.filename)
                        if scope.defined_at.filename
                        else None
                    )
                    label_file = (
                        os.path.abspath(line_id.filename)
                        if line_id.filename
                        else None
                    )
                    if scope_file != label_file:
                        # Label prefix matches but wrong file
                        # Let it fall back to normal scope hierarchy
                        return False
                    scope.set_label_value(label, value, line_id, LabelScopeType.NAMED)
                    return True
        return False

    def get_scope_definition(self, name: str) -> NamedLabelScope:
        return self._scope_definitions[name]


class ActiveNamedScopeList(list[str]):
    """Convenience class to manage active named scopes when processing an assembly file."""

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
