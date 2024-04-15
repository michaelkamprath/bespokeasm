import sys

from bespokeasm.assembler.line_object.preprocessor_line import PreprocessorLine
from bespokeasm.assembler.line_identifier import LineIdentifier
from bespokeasm.assembler.memory_zone import MemoryZone
import bespokeasm.assembler.preprocessor.condition as condition
from bespokeasm.assembler.preprocessor.condition_stack import ConditionStack


CONDITIONAL_LINE_PREFIX_LIST = ['#if ', '#ifdef ', '#ifndef ', '#elif ', '#else', '#endif']


class ConditionLine(PreprocessorLine):
    def __init__(
                self,
                line_id: LineIdentifier,
                instruction: str,
                comment: str,
                memzone: MemoryZone,
                condition_stack: ConditionStack
            ):
        super().__init__(line_id, instruction, comment, memzone)

        if instruction.startswith('#if '):
            self._condition = condition.IfPreprocessorCondition(instruction, line_id)
        elif instruction.startswith('#elif '):
            self._condition = condition.ElifPreprocessorCondition(instruction, line_id)
        elif instruction == '#else':
            self._condition = condition.ElsePreprocessorCondition(instruction, line_id)
        elif instruction == '#endif':
            self._condition = condition.EndifPreprocessorCondition(instruction, line_id)
        elif instruction.startswith('#ifdef ') or instruction.startswith('#ifndef '):
            self._condition = condition.IfdefPreprocessorCondition(instruction, line_id)
        else:
            raise ValueError(f'Invalid condition line: {instruction}')

        try:
            condition_stack.process_condition(self._condition)
        except IndexError:
            sys.exit(
                f'ERROR - {line_id}: Preprocessor condition has no matching counterpart'
            )

    def __repr__(self) -> str:
        return f'ConditionLine<{self._line_id}>'

    @property
    def compilable(self) -> bool:
        return True
