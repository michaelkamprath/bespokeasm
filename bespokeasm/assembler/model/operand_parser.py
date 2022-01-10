from __future__ import annotations
import sys

from bespokeasm.assembler.line_identifier import LineIdentifier
from bespokeasm.assembler.byte_code.parts import ByteCodePart
from bespokeasm.assembler.model.operand_set import OperandSetCollection, OperandSet
from bespokeasm.assembler.model.operand import Operand, ParsedOperand, OperandBytecodePositionType
from bespokeasm.assembler.model.operand.factory import OperandFactory

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


class OperandSetsModel:
    _operand_sets: list[OperandSet]

    def __init__(self, config: dict, operand_set_collection: OperandSetCollection):
        self._config = config
        operand_sets = self._config['list']
        self._operand_sets = []
        for k in operand_sets:
            opset = operand_set_collection.get_operand_set(k)
            if opset is not None:
                self._operand_sets.append(opset)
            else:
                sys.exit(f'ERROR: instuction set configuration file makes reference to unknow operand set "{k}"')
    def __repr__(self) -> str:
        return str(self)
    def __str__(self) -> str:
        return f'OperandSetsModel<{str(self._operand_sets)}>'
    @property
    def reverse_argument_order(self) -> bool:
        '''Determines whether the order that the instruction's argument values
        emitted in machine code should be in the same order as the argument
        (false) or reversed (true)
        '''
        return self._config.get('reverse_argument_order', False)

    @property
    def operand_count(self) -> int:
        return len(self._operand_sets)

    def find_operands_from_operand_sets(
        self,
        line_id: LineIdentifier,
        operands: list[str],
        register_labels: set[str],
    ) -> MatchedOperandSet:
        '''attempts to find a operand match based on an operand set combination. Returns
           None if no match is found, or a MatchedOperandSet if a valid match is found.
        '''
        # the operands list must match configured operand count (null operands not supported here)
        if len(operands) != self.operand_count:
            return None
        matched_operands: list[ParsedOperand] = []
        for i in range(self.operand_count):
            operand = self._operand_sets[i].parse_operand(line_id, operands[i], register_labels)
            if operand is not None:
                matched_operands.append(operand)
            else:
                return None

        # now check to ensure this is an allowed combo
        if 'disallowed_pairs' in self._config:
            operand_ids = [op.operand.id for op in matched_operands]
            if operand_ids in self._config['disallowed_pairs']:
                # matched a disallowed pair, so no match reported
                return None

        return MatchedOperandSet(matched_operands, self.reverse_argument_order)

class SpecificOperandsModel:
    class SpecificOperandConfig:
        def __init__(self, config: dict, default_endian: str):
            self._config = config
            self._operands = [
                OperandFactory.factory(arg_type_id, arg_type_conf, default_endian)
                for arg_type_id, arg_type_conf in self._config.get('list', {}).items()
            ]

        def __repr__(self) -> str:
            return str(self)
        def __str__(self) -> str:
            operand_str = ','.join([str(op) for op in self._operands])
            return f'SpecificOperandConfig<{operand_str}>'
        def __getitem__(self, key: int) -> Operand:
            '''Returns the i-th operand in this specific configuration'''
            return self._operands[key]

        @property
        def reverse_argument_order(self) -> bool:
            '''Determines whether the order that the instruction's argument values
            emitted in machine code should be in the same order as the argument
            (false) or reversed (true)
            '''
            return self._config.get('reverse_argument_order', False)

        @property
        def operand_count(self) -> int:
            return len(self._operands)

    _specific_operands: list[SpecificOperandsModel.SpecificOperandConfig]
    def __init__(self, config: dict, default_endian: str):
        self._specific_operands = [
            SpecificOperandsModel.SpecificOperandConfig(arg_confing_dict, default_endian)
                for arg_confing_dict in config.values()
        ]
    def __repr__(self) -> str:
        return str(self)
    def __str__(self) -> str:
        names = []
        for opconfig in self._specific_operands:
            names.append(str(opconfig))
        operand_str = ','.join(names)
        return f'SpecificOperandsModel<{operand_str}>'

    def find_operands_from_specific_operands(
        self,
        line_id: LineIdentifier,
        operands: list[str],
        target_operand_count: int,
        register_labels: set[str],
    ) -> MatchedOperandSet:
        '''attempts to find a operand match based on any specific operand configuration.
           Returns None if no match is found, or a MatchedOperandSet if a valid match is found.
        '''
        for configured_operands in self._specific_operands:
            if configured_operands.operand_count != target_operand_count:
                # wrong operand count
                return None
            operand_index = 0
            null_operand_count = 0
            matched_operands: list[ParsedOperand] = []
            for i in range(configured_operands.operand_count):
                if configured_operands[i].null_operand:
                    operand = configured_operands[i].parse_operand(line_id, '', register_labels)
                    null_operand_count += 1
                else:
                    if operand_index >= len(operands):
                        # instruction had too few operand present
                        return None
                    operand = configured_operands[i].parse_operand(line_id, operands[operand_index], register_labels)
                operand_index += 1

                if operand is None:
                    # if it doesn't match an operand at any point, go to next specific configuration
                    matched_operands = []
                    break
                matched_operands.append(operand)

            if (len(operands) + null_operand_count !=  target_operand_count) or (target_operand_count != len(matched_operands)):
                matched_operands = []
                continue
            matched_set = MatchedOperandSet(matched_operands, configured_operands.reverse_argument_order)
            return matched_set
        return None


class OperandParser:
    def __init__(self, instruction_operands_config: dict, operand_set_collection: OperandSetCollection, default_endian: str):
        if instruction_operands_config is not None:
            self._config = instruction_operands_config
        else:
            self._config = {'count': 0}
        # Set up Specific Operand
        if 'specific_operands' in self._config:
            self._specific_operands_model = SpecificOperandsModel(self._config['specific_operands'], default_endian)
        else:
            self._specific_operands_model = None
        # Sey Up Operant Sets
        if 'operand_sets' in self._config:
            self._operand_sets_model = OperandSetsModel( self._config['operand_sets'], operand_set_collection)
        else:
            self._operand_sets_model = None

    def __repr__(self) -> str:
        return str(self)

    def __str__(self) -> str:
        return f'OperandParser<{self._operand_sets_model}, {self._specific_operands_model}>'

    def validate(self, instruction: str):
        # check to make sure we as many operands configured as count.
        if self._operand_sets_model is not None and self.operand_count != self._operand_sets_model.operand_count:
            sys.exit(f'ERROR: CONFIGURATION - the number of properly configured operands ({len(self._operand_sets)}) does not match prescribed number ({self.operand_count}) for instruction "{instruction}"')

    @property
    def operand_count(self) -> int:
        return self._config['count']

    @property
    def _has_operand_sets(self):
        return self._operand_sets_model is not None

    def generate_machine_code(
        self, line_id: LineIdentifier,
        operands: list[str],
        register_labels: set[str]
    ) -> MatchedOperandSet:
        ''' the general goal of this method is to determin if any operands configured for this parser matched.
        If so, return the byte code parts associated with those oeprands. If not, return a flag indicating that
        this operand profile did not match.
        '''
        matched_operands: list[ParsedOperand] = []

        # Step 1 - Look for specific operand matches
        if self._specific_operands_model is not None:
            matched_operands = \
                self._specific_operands_model.find_operands_from_specific_operands(
                        line_id,
                        operands,
                        self.operand_count,
                        register_labels
                    )
            if matched_operands is not None:
                return matched_operands

        # Step 2 - Find an allowed combination match from an operand set
        if self._has_operand_sets:
            matched_operands = \
                self._operand_sets_model.find_operands_from_operand_sets(line_id, operands, register_labels)
            if matched_operands is not None:
                return matched_operands

        # if we are here, it's because no operands were parsed
        return None

class MatchedOperandSet:
    def __init__(self, operands: list[ParsedOperand], reverse_arg_order: bool) -> None:
        self._operands = operands
        self._reverse_arg_order = reverse_arg_order

    def __repr__(self) -> str:
        return str(self)

    def __str__(self) -> str:
        return f'MatchedOperandSet<{self._operands}>'

    def generate_byte_code(self, base_bytecode: ByteCodePart) -> list[ByteCodePart]:
        machine_code: list[ByteCodePart] = [base_bytecode]
        # first add bytecode
        for op in self._operands:
            if op.byte_code is not None:
                if op.operand.bytecode_position == OperandBytecodePositionType.SUFFIX:
                    machine_code.append(op.byte_code)
                elif op.operand.bytecode_position == OperandBytecodePositionType.PREFIX:
                    machine_code.insert(0, op.byte_code)
        # now add arguments
        arguments = [op.argument for op in self._operands if op.argument is not None]
        if self._reverse_arg_order:
            arguments.reverse()
        for arg in arguments:
            machine_code.append(arg)
        return machine_code