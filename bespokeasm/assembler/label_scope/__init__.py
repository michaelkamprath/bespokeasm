# Label Scope Manager
#
#  Label scope determines where a label can be usedin an expression. The labels scopes are:
#
#       Global - Labels that can be used anywhere during assembly. These labels are not
#                prefixed with a _ or .
#       File -   Labels that can only be used in the *.asm file in which the label was found.
#                These labels are prefixed with a "_"
#       Local -  Labels that can only be used between two non-local labels or .org directive
#                within the same file. These labels are prefixed with a "."
#
#  Label scopes are hiearchical, where a local scope has a specific file scope as its parent, and a
#  file scope has the global scope as its parent.
#
#  Constants can only be global or file scope, and they do not affect the determination of local scope.
#
#  DESIGN OVERVIEW
#
#  each LineObject gets assigned a label scope on the first pass. Basic alorithm
#
#       1. Have a "current scope" value that is initialize to the current file scope, which is a child of the global scope.
#       2. Process each line to find labels
#           a. Update the "current scope" entity:
#               i.   If the line is a global or file label, create a new local scope for it
#                    and update the "current scope" to be that new local scope entity.
#               ii.  If the line is a .org directive, set the "current scope" to the current file scope.
#               iii. Otherwise do not update the "current scope" value
#           b. assign the line a scope entity of "current scope"
#           c. Process the line according to its line syntax. If it is a label or constant, save the
#              value mapping to the appropiate scope of the label or constant per its syntax. This is
#              done by starting at the line's assigned scope entity, and then recursing through its
#              parent entities until the scope entity matches the scope of the label or constant.
#               i.   If a local label is found while the "current scope" is file or global, throw an error.
#       3. Subsequently when resolving labels, the scope of the label to be resolve is determined by
#          its syntax (starts with _ or .). A recursive parent search is performed from scope entity
#          of the line being processed until the the scope that matches the label systax is found, and
#          then the label is resolved at that scope.
#           a. Only labels in a line's assigned scope and it's parental lineage are considered when resolving
#              a label.
#
from __future__ import annotations

import enum
import sys



class LabelScopeType(enum.Enum):
    GLOBAL = 0
    FILE = 1
    LOCAL = 2

    @classmethod
    def get_label_scope(cls, label: str) -> LabelScopeType:
        if label.startswith('.'):
            return LabelScopeType.LOCAL
        elif label.startswith('_'):
            return LabelScopeType.FILE
        else:
            return LabelScopeType.GLOBAL

class LabelScope:
    class LabelInfo:
        def __init__(self, label: str, value: int, line_num: int) -> None:
            self._label = label
            self._value = value
            self._line_num = line_num

        @property
        def label(self) -> str:
            return self._label
        @property
        def value(self) -> int:
            return self._value
        @property
        def line_num(self) -> int:
            return self._line_num

    def __init__(self, scope_type: LabelScopeType, parent: LabelScope, scope_reference: str) -> None:
        self._type = scope_type
        self._parent = parent
        self._labels = {}

    @property
    def parent(self) -> LabelScope:
        return self._parent

    @property
    def type(self) -> LabelScopeType:
        return self._type

    def get_label_value(self, label: str, line_num: int) -> int:
        if label in self._labels:
            return self._labels[label].value
        elif self.parent is not None:
            return self.parent.get_label_value(label, line_num)
        else:
            return None

    def set_label_value(self, label: str, value: int, line_num: int) -> None:
        label_scope = LabelScopeType.get_label_scope(label)
        if label_scope.value < self.type.value:
            self.parent.set_label_value(label, value, line_num)
        elif label_scope == self.type:
            if label not in self._labels:
                self._labels[label] = LabelScope.LabelInfo(label, value, line_num)
            else:
                sys.exit(f"ERROR: line {line_num} - Label '{label}' is defined multiple times.")
        else:
            # we are only here if the label is too low level for this scope
            # example: local label defined before any global labels
            sys.exit(f"ERROR: line {line_num} - Label '{label}' is to low of scope for available scopes at this line.")

    _global_scope = None
    @classmethod
    def global_scope(cls, register_labels: set[str]) -> LabelScope:
        if cls._global_scope is None:
            cls._global_scope = GlobalLabelScope(register_labels)
        return cls._global_scope


class GlobalLabelScope(LabelScope):
    def __init__(self, register_labels: set[str]) -> None:
        super().__init__(LabelScopeType.GLOBAL, None, '--GLOBAL--')
        self._register_labels = register_labels

    def get_label_value(self, label: str, line_num: int) -> int:
        '''Global scope version first checks whether passed label is actually a register'''
        # check to see if label is a register
        if label in self._register_labels:
            sys.exit(f'ERROR: line {line_num} - register label "{label}" used in numeric expression')
        return super().get_label_value(label, line_num)