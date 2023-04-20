from bespokeasm.assembler.line_object import LineObject
from bespokeasm.assembler.line_identifier import LineIdentifier
from bespokeasm.assembler.memory_zone import MemoryZone


class PreprocessorLine(LineObject):
    def __init__(self, line_id: LineIdentifier, instruction: str, comment: str, memzone: MemoryZone):
        super().__init__(line_id, instruction, comment, memzone)

    def __repr__(self) -> str:
        return f"PreprocessorLine<{self._line_id}>"
