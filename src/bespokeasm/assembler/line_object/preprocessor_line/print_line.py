import re
import sys

import click
from bespokeasm.assembler.line_identifier import LineIdentifier
from bespokeasm.assembler.line_object.preprocessor_line import PreprocessorLine
from bespokeasm.assembler.memory_zone import MemoryZone
from bespokeasm.assembler.preprocessor import Preprocessor
from bespokeasm.assembler.preprocessor.condition_stack import ConditionStack


class PrintLine(PreprocessorLine):
    PATTERN_PRINT = re.compile(
        r'^#print(?:\s+(\d+))?(?:\s+(black|red|green|yellow|blue|magenta|cyan|white))?\s+"([\s\S]*?)"\s*$',
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
                log_verbosity: int,
            ) -> None:
        super().__init__(line_id, instruction, comment, memzone)

        match = re.search(PrintLine.PATTERN_PRINT, instruction)
        if match is None:
            sys.exit(f'ERROR - {line_id}: Invalid #print directive syntax: {instruction}')

        min_level_str = match.group(1)
        color_str = match.group(2)
        message = match.group(3)

        try:
            min_level = int(min_level_str) if min_level_str is not None else None
        except ValueError:
            sys.exit(f'ERROR - {line_id}: Invalid verbosity level in #print directive: {instruction}')

        try:
            min_level = int(min_level_str) if min_level_str is not None else None
        except ValueError:
            sys.exit(f'ERROR - {line_id}: Invalid verbosity level in #print directive: {instruction}')

        color = None
        if color_str is not None:
            color = color_str.lower()
            allowed_colors = {'black', 'red', 'green', 'yellow', 'blue', 'magenta', 'cyan', 'white'}
            if color not in allowed_colors:
                sys.exit(f'ERROR - {line_id}: Invalid color in #print directive: {color_str}')

        should_emit = (
            condition_stack.currently_active(preprocessor)
            and not condition_stack.is_muted
            and (min_level is None or log_verbosity >= min_level)
        )

        if should_emit:
            if color is not None:
                click.secho(message, fg=color)
            else:
                click.echo(message)

        self._min_level = min_level
        self._color = color
        self._message = message

    def __repr__(self) -> str:
        lvl = self._min_level if self._min_level is not None else 'always'
        return f'PrintLine<{lvl}: {self._message}>'
