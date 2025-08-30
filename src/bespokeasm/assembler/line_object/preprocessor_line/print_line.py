import re
import sys

import click
from bespokeasm.assembler.line_identifier import LineIdentifier
from bespokeasm.assembler.line_object.preprocessor_line import PreprocessorLine
from bespokeasm.assembler.memory_zone import MemoryZone
from bespokeasm.assembler.preprocessor import Preprocessor
from bespokeasm.assembler.preprocessor.condition_stack import ConditionStack


class PrintLine(PreprocessorLine):
    PATTERN_PRINT = re.compile(r'^#print(?:\s+(\d+))?\s+"([\s\S]*?)"\s*$', re.MULTILINE)

    def __init__(
                self,
                line_id: LineIdentifier,
                instruction: str,
                comment: str,
                memzone: MemoryZone,
                preprocessor: Preprocessor,
                condition_stack: ConditionStack,
                log_verbosity: int,
            ) -> None:
        super().__init__(line_id, instruction, comment, memzone)

        match = re.search(PrintLine.PATTERN_PRINT, instruction)
        if match is None:
            sys.exit(f'ERROR - {line_id}: Invalid #print directive syntax: {instruction}')

        min_level_str = match.group(1)
        message = match.group(2)

        try:
            min_level = int(min_level_str) if min_level_str is not None else None
        except ValueError:
            sys.exit(f'ERROR - {line_id}: Invalid verbosity level in #print directive: {instruction}')

        should_emit = (
            condition_stack.currently_active(preprocessor)
            and not condition_stack.is_muted
            and (min_level is None or log_verbosity >= min_level)
        )

        if should_emit:
            click.echo(message)

        self._min_level = min_level
        self._message = message

    def __repr__(self) -> str:
        lvl = self._min_level if self._min_level is not None else 'always'
        return f'PrintLine<{lvl}: {self._message}>'
