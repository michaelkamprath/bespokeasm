import re

from bespokeasm.assembler.line_identifier import LineIdentifier
from bespokeasm.assembler.line_object.preprocessor_line import PreprocessorLine
from bespokeasm.assembler.memory_zone import MemoryZone
from bespokeasm.assembler.preprocessor import Preprocessor
from bespokeasm.assembler.preprocessor.condition_stack import ConditionStack


class ErrorLine(PreprocessorLine):
    PATTERN_ERROR = re.compile(
        r'^#error(?:\s+"([\s\S]*?)")?\s*$',
        re.IGNORECASE,
    )

    def __init__(
                self,
                line_id: LineIdentifier,
                instruction: str,
                comment: str,
                memzone: MemoryZone,
                preprocessor: Preprocessor,
                condition_stack: ConditionStack,
            ) -> None:
        super().__init__(line_id, instruction, comment, memzone)

        match = re.search(ErrorLine.PATTERN_ERROR, instruction)
        if match is None:
            preprocessor.diagnostic_reporter.error(
                line_id,
                f'Invalid #error directive syntax: {instruction}',
            )

        message = match.group(1)
        if message is None or message == '':
            message = 'encountered error directive'

        should_emit = (
            condition_stack.currently_active(preprocessor)
            and not condition_stack.is_muted
        )
        if should_emit:
            preprocessor.diagnostic_reporter.error(line_id, message)

        self._message = message

    def __repr__(self) -> str:
        return f'ErrorLine<{self._line_id}>'
