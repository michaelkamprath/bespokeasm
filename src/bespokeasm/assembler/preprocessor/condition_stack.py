from bespokeasm.assembler.diagnostic_reporter import DiagnosticReporter
from bespokeasm.assembler.preprocessor import Preprocessor
from bespokeasm.assembler.preprocessor.condition import EndifPreprocessorCondition
from bespokeasm.assembler.preprocessor.condition import MutePreprocessorCondition
from bespokeasm.assembler.preprocessor.condition import PreprocessorCondition
from bespokeasm.assembler.preprocessor.condition import UnmutePreprocessorCondition


class ConditionStack:
    def __init__(self, diagnostic_reporter: DiagnosticReporter):
        if diagnostic_reporter is None:
            raise ValueError('DiagnosticReporter is required for ConditionStack')
        self._stack: list[PreprocessorCondition] = []
        self._mute_counter = 0
        self._diagnostic_reporter = diagnostic_reporter

    def process_condition(self, condition: PreprocessorCondition, preprocessor: Preprocessor):
        if isinstance(condition, EndifPreprocessorCondition):
            popped_consition = self._stack.pop()
            if popped_consition.is_dependent:
                pass
        elif isinstance(condition, MutePreprocessorCondition):
            if self.currently_active(preprocessor):
                self._increment_mute_counter()
        elif isinstance(condition, UnmutePreprocessorCondition):
            if self.currently_active(preprocessor):
                if self._mute_counter == 0:
                    self._diagnostic_reporter.warn(
                        condition.line_id,
                        '#unmute has no effect (no active #mute)',
                    )
                self._decrement_mute_counter()
        elif condition.is_dependent:
            # a dependent condition pops the current condition and makes it the parent to the new condition.
            # this way the dependent chain is only ever 1-deep in the stack, making nested #if/#else/#endif
            # statements easier to handle.
            popped_condition = self._stack.pop()
            condition.parent = popped_condition
            self._stack.append(condition)
        else:
            self._stack.append(condition)

    def currently_active(self, preprocessor: Preprocessor) -> bool:
        if len(self._stack) == 0:
            return True
        return self._stack[-1].evaluate(preprocessor)

    def _increment_mute_counter(self):
        self._mute_counter += 1

    def _decrement_mute_counter(self):
        if self._mute_counter > 0:
            self._mute_counter -= 1

    @property
    def is_muted(self) -> bool:
        """Returns True if the current condition stack is muted."""
        return self._mute_counter > 0

    @property
    def mute_depth(self) -> int:
        return self._mute_counter
