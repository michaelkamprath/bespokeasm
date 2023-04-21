
from bespokeasm.assembler.preprocessor.condition import \
            PreprocessorCondition, DependentPreprocessorCondition, EndifPreprocessorCondition
from bespokeasm.assembler.preprocessor import Preprocessor


class ConsitionStack:
    def __init__(self):
        self._stack: list[PreprocessorCondition] = []

    def process_condition(self, condition: PreprocessorCondition):
        if isinstance(condition, EndifPreprocessorCondition):
            popped_consition = self._stack.pop()
            if isinstance(popped_consition, DependentPreprocessorCondition):
                pass
        elif isinstance(condition, DependentPreprocessorCondition):
            # a dependent condition pops the current condition and makes it the parent to the new condition.
            # this way the dependent chain is only ever 1-deep in the stack, making nested #if/#else/#endif
            # statements easier to handle.
            popped_condition = self._stack.pop()
            # TODO: check if popped_condition is allowed to be the parent of tihs condition
            condition.parent = popped_condition
            self._stack.append(condition)
        else:
            self._stack.append(condition)

    def currently_active(self, preprocessor: Preprocessor) -> bool:
        if len(self._stack) == 0:
            return True
        return self._stack[-1].evaluate(preprocessor)
