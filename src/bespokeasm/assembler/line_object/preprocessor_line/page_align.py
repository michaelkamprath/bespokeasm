import re

from bespokeasm.assembler.line_object.preprocessor_line import PreprocessorLine
from bespokeasm.assembler.line_identifier import LineIdentifier
from bespokeasm.assembler.memory_zone import MemoryZone


class PageAlignLine(PreprocessorLine):
    PATTERN_DEFINE_SYMBOL = re.compile(
            r'^#page',
        )

    def __init__(
        self,
        line_id: LineIdentifier,
        instruction: str,
        comment: str,
        memzone: MemoryZone,
    ):
        super().__init__(line_id, instruction, comment, memzone)
