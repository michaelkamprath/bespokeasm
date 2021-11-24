# Assembly File
#
# this class models an assembly file. AN AssemblyFile object is created for each
# assembly file that is loaded. It is responsible for:
#
#    * providing a list of lines
#    * having a single file label scope

from bespokeasm.assembler.label_scope import LabelScope, LabelScopeType

class AssemblyFile:
    def __init__(self, filename: str) -> None:
        self._fielname = filename
        self._label_scope = LabelScope(
                LabelScopeType.FILE,
                LabelScope.global_scope(),
                self._fielname
            )
