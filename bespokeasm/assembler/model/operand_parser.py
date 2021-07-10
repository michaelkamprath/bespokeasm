import sys

from bespokeasm.assembler.byte_code.parts import ByteCodePart
from bespokeasm.assembler.model.operand_set import OperandSet, OperandSetCollection

# Operand Parser
#
# An operand parser consists of:
#    - A list of 0 or more OperandSets, order is expected operand order
#    - A list of operand ID tuples representing operand combinations to not allow
#    - A list of zero or more specific operand tuples representing signatures of
#      operands not generable from the OperandSets
#
# The parsing of an operand list will be done in this order:
#    1. Determine if the operand list matches and specific operand tuples. If so
#       generate byte byte code and argument values and return
#    2. Determine if the operand list can match any operand signature generable from
#       the OperandSets. If so, ensure that signature does not match a disallowed signatre,
#       then generate byte byte code and argument values and return
#    3. Error
#


class OperandParser:
    def __init__(self, instruction_operands_config: dict, operand_set_collection: OperandSetCollection):
        if instruction_operands_config is not None:
            self._config = instruction_operands_config
        else:
            self._config = {'count': 0}
        self._operand_sets = []
        if 'operand_sets' in self._config:
            operand_sets = self._config['operand_sets']['list']
            self._operand_sets = [operand_set_collection.get_operand_set(k) for k in operand_sets]

    def __repr__(self) -> str:
        return str(self)
    def __str__(self) -> str:
        return f'OperandParser<{self._operand_sets}>'

    def validate(self, instruction: str):
        # check to make sure we as many operands configured as count.
        if self.operand_count != len(self._operand_sets):
            sys.exit(f'ERROR: CONFIGURATION - the number of properly configured operands ({len(self._operand_sets)}) does not match prescribed number ({self.operand_count}) for instruction "{instruction}"')

    @property
    def operand_count(self) -> int:
        return self._config['count']

    def generate_machine_code(self, line_num:int, operands: list[str]) -> tuple[list[ByteCodePart], list[ByteCodePart]]:
        bytecode_list = []
        argument_values = []

        if len(operands) == self.operand_count:
            for i in range(self.operand_count):
                bytecode_part, argument_part = self._operand_sets[i].parse_operand(line_num, operands[i])
                if bytecode_part is not None:
                    bytecode_list.append(bytecode_part)
                if argument_part is not None:
                    argument_values.append(argument_part)
                if bytecode_part is None and argument_part is None:
                    # if there is an argument, something should be produced, so this is and error
                    sys.exit(f'ERROR: line {line_num} - Unrecognized operand "{operands[i]}"')
        else:
            sys.exit(f'ERROR: line {line_num} - INTERNAL - operand list wrongs size. Expected {self.operand_count}, got {len(operands)}')
        return (bytecode_list, argument_values)