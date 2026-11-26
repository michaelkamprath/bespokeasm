from __future__ import annotations

from typing import Literal

from bespokeasm.assembler.bytecode.parts import ByteCodePart
from bespokeasm.assembler.diagnostic_reporter import AssemblerError
from bespokeasm.assembler.line_identifier import LineIdentifier
from bespokeasm.assembler.memory_zone.manager import MemoryZoneManager
from bespokeasm.assembler.model.operand import allowed_by_enclosure
from bespokeasm.assembler.model.operand import EnclosureRequirement
from bespokeasm.assembler.model.operand import Operand
from bespokeasm.assembler.model.operand import OperandBytecodePositionType
from bespokeasm.assembler.model.operand import ParsedOperand
from bespokeasm.assembler.model.operand.factory import OperandFactory
from bespokeasm.assembler.model.operand.operand_label import contains_operand_label_annotation
from bespokeasm.assembler.model.operand.operand_label import OperandLabelError
from bespokeasm.assembler.model.operand.operand_label import supports_operand_labels
from bespokeasm.assembler.model.operand.operand_label import UNSUPPORTED_OPERAND_LABEL_MESSAGE
from bespokeasm.assembler.model.operand_set import OperandSet
from bespokeasm.assembler.model.operand_set import OperandSetCollection
from bespokeasm.assembler.parsing import enclosure_depth
from bespokeasm.utilities import ENCLOSURES

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

    def __init__(
        self,
        instruction: str,
        config: dict,
        operand_set_collection: OperandSetCollection,
        word_size: int,
        word_segment_size: int,
    ):
        self._config = config
        self._word_size = word_size
        self._word_segment_size = word_segment_size
        if 'list' not in self._config:
            raise AssemblerError(
                None,
                f'Operand Set configuration dictionary is missing "list" key for instruction "{instruction}"',
            )
        operand_sets = self._config['list']
        self._operand_sets = []
        for k in operand_sets:
            opset = operand_set_collection.get_operand_set(k)
            if opset is not None:
                self._operand_sets.append(opset)
            else:
                raise AssemblerError(
                    None,
                    f'instruction set configuration file refers to unknown operand set "{k}"'
                    f' in definition of instruction "{instruction}"',
                )

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
    def reverse_bytecode_order(self) -> bool:
        '''Determines whether the order that the instruction operand's byte code values
        emitted in machine code should be in the same order as the operands
        (false) or reversed (true)
        '''
        return self._config.get('reverse_bytecode_order', False)

    @property
    def operand_count(self) -> int:
        return len(self._operand_sets)

    def find_operands_from_operand_sets(
        self,
        line_id: LineIdentifier,
        operands: list[str],
        register_labels: set[str],
        memzone_manager: MemoryZoneManager,
        enclosure_requirements: list[EnclosureRequirement | None] | None = None,
    ) -> MatchedOperandSet:
        '''attempts to find a operand match based on an operand set combination. Returns
           None if no match is found, or a MatchedOperandSet if a valid match is found.
        '''
        # the operands list must match configured operand count (null operands not supported here)
        if len(operands) != self.operand_count:
            return None
        matched_operands: list[ParsedOperand] = []
        for i in range(self.operand_count):
            operand = self._operand_sets[i].parse_operand(
                line_id,
                operands[i],
                register_labels,
                memzone_manager,
                enclosure_requirement=enclosure_requirements[i] if enclosure_requirements else None,
            )
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

        return MatchedOperandSet(matched_operands, self.reverse_argument_order, self.reverse_bytecode_order)


class SpecificOperandsModel:
    class SpecificOperandConfig:
        def __init__(
            self,
            config: dict,
            default_multi_word_endian: Literal['big', 'little'],
            default_intra_word_endian: Literal['big', 'little'],
            registers: set[str],
            word_size: int,
            word_segment_size: int,
            diagnostic_reporter,
            default_numeric_base: str = 'decimal',
        ):
            self._config = config
            self._operands = [
                OperandFactory.factory(
                    arg_type_id,
                    arg_type_conf,
                    default_multi_word_endian,
                    default_intra_word_endian,
                    registers,
                    word_size,
                    word_segment_size,
                    diagnostic_reporter,
                    default_numeric_base=default_numeric_base,
                )
                for arg_type_id, arg_type_conf in self._config.get('list', {}).items()
            ]
            self._word_size = word_size
            self._word_segment_size = word_segment_size

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
        def reverse_bytecode_order(self) -> bool:
            '''Determines whether the order that the instruction operand's byte code values
            emitted in machine code should be in the same order as the operands
            (false) or reversed (true)
            '''
            return self._config.get('reverse_bytecode_order', False)

        @property
        def operand_count(self) -> int:
            return len(self._operands)

    _specific_operands: list[SpecificOperandsModel.SpecificOperandConfig]

    def __init__(
        self,
        config: dict,
        default_multi_word_endian: str,
        default_intra_word_endian: str,
        registers: set[str],
        word_size: int,
        word_segment_size: int,
        diagnostic_reporter,
        default_numeric_base: str = 'decimal',
    ):
        self._specific_operands = [
            SpecificOperandsModel.SpecificOperandConfig(
                arg_confing_dict,
                default_multi_word_endian,
                default_intra_word_endian,
                registers,
                word_size,
                word_segment_size,
                diagnostic_reporter,
                default_numeric_base=default_numeric_base,
            )
            for arg_confing_dict in config.values()
        ]
        self._word_size = word_size
        self._word_segment_size = word_segment_size

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
        memzone_manager: MemoryZoneManager,
        enclosure_requirements: list[EnclosureRequirement | None] | None = None,
    ) -> MatchedOperandSet:
        '''attempts to find a operand match based on any specific operand configuration.
           Returns None if no match is found, or a MatchedOperandSet if a valid match is found.
        '''
        operand_label_error: OperandLabelError | None = None
        for configured_operands in self._specific_operands:
            if configured_operands.operand_count != target_operand_count:
                # wrong operand count
                return None
            operand_index = 0
            null_operand_count = 0
            matched_operands: list[ParsedOperand] = []
            for i in range(configured_operands.operand_count):
                if configured_operands[i].null_operand:
                    operand = configured_operands[i].parse_operand(
                        line_id,
                        '',
                        register_labels,
                        memzone_manager,
                    )
                    null_operand_count += 1
                else:
                    if operand_index >= len(operands):
                        # instruction had too few operand present
                        return None
                    raw_operand = operands[operand_index]
                    requirement = enclosure_requirements[operand_index] if enclosure_requirements else None
                    if allowed_by_enclosure(configured_operands[i], requirement):
                        operand = configured_operands[i].parse_operand(
                            line_id,
                            raw_operand,
                            register_labels,
                            memzone_manager,
                        )
                    else:
                        operand = None
                    if operand is None \
                            and contains_operand_label_annotation(raw_operand) \
                            and not supports_operand_labels(configured_operands[i].type):
                        if operand_label_error is None:
                            operand_label_error = OperandLabelError(
                                line_id,
                                UNSUPPORTED_OPERAND_LABEL_MESSAGE,
                            )
                operand_index += 1

                if operand is None:
                    # if it doesn't match an operand at any point, go to next specific configuration
                    matched_operands = []
                    break
                matched_operands.append(operand)

            if (len(operands) + null_operand_count != target_operand_count) \
                    or (target_operand_count != len(matched_operands)):
                matched_operands = []
                continue
            matched_set = MatchedOperandSet(
                                matched_operands,
                                configured_operands.reverse_argument_order,
                                configured_operands.reverse_bytecode_order
                            )
            return matched_set
        if operand_label_error is not None:
            raise operand_label_error
        return None


class OperandParser:
    def __init__(
                self,
                instruction: str,
                instruction_operands_config: dict,
                operand_set_collection: OperandSetCollection,
                default_multi_word_endian: str,
                default_intra_word_endian: str,
                registers: set[str],
                word_size: int,
                word_segment_size: int,
                diagnostic_reporter,
                default_numeric_base: str = 'decimal',
            ):
        if instruction_operands_config is not None:
            self._config = instruction_operands_config
            if 'count' not in self._config:
                diagnostic_reporter.error(
                    None,
                    f'configuration for instruction "{instruction}" does not have a "count" element',
                )
        else:
            self._config = {'count': 0}
        # Set up Specific Operand
        if 'specific_operands' in self._config:
            self._specific_operands_model = SpecificOperandsModel(
                self._config['specific_operands'],
                default_multi_word_endian,
                default_intra_word_endian,
                registers,
                word_size,
                word_segment_size,
                diagnostic_reporter,
                default_numeric_base=default_numeric_base,
            )
        else:
            self._specific_operands_model = None
        # Set Up Operant Sets
        if 'operand_sets' in self._config:
            self._operand_sets_model = OperandSetsModel(
                instruction,
                self._config['operand_sets'],
                operand_set_collection,
                word_size,
                word_segment_size,
            )
        else:
            self._operand_sets_model = None
        self._instruction_enclosed_forms = self.enclosed_forms()

    def __repr__(self) -> str:
        return str(self)

    def __str__(self) -> str:
        return f'OperandParser<{self._operand_sets_model}, {self._specific_operands_model}>'

    def validate(self, instruction: str):
        # check to make sure we as many operands configured as count.
        if self._operand_sets_model is not None and self.operand_count != self._operand_sets_model.operand_count:
            raise AssemblerError(
                None,
                f'the number of properly configured operands '
                f'({self._operand_sets_model.operand_count}) does not match prescribed '
                f'number ({self.operand_count}) for instruction "{instruction}"',
            )

    @property
    def operand_count(self) -> int:
        return self._config['count']

    @property
    def _has_operand_sets(self):
        return self._operand_sets_model is not None

    # ---- introspection used to explain failed matches -----------------------

    def source_operand_counts(self) -> set[int]:
        '''Return the numbers of operands a source line may write for this parser.

        Specific operand configurations may contain null (``empty``) operands that are
        not written in source, so their source count is the configured count minus the
        null operands.
        '''
        counts: set[int] = set()
        if self._operand_sets_model is not None:
            counts.add(self._operand_sets_model.operand_count)
        if self._specific_operands_model is not None:
            for configured in self._specific_operands_model._specific_operands:
                counts.add(sum(1 for operand in configured._operands if not operand.null_operand))
        if not counts:
            counts.add(self.operand_count)
        return counts

    def candidate_operands(self, position: int, source_operand_count: int) -> list[Operand]:
        '''Return every operand definition that could accept the source operand at ``position``.'''
        candidates: list[Operand] = []
        if self._operand_sets_model is not None and self._operand_sets_model.operand_count == source_operand_count:
            operand_sets = self._operand_sets_model._operand_sets
            if position < len(operand_sets):
                candidates.extend(operand_sets[position]._ordered_operand_list)
        if self._specific_operands_model is not None:
            for configured in self._specific_operands_model._specific_operands:
                source_operands = [operand for operand in configured._operands if not operand.null_operand]
                if len(source_operands) == source_operand_count and position < len(source_operands):
                    candidates.append(source_operands[position])
        return candidates

    def enclosed_forms(self) -> dict[tuple[int, int], set[EnclosureRequirement]]:
        '''The enclosed operand forms this parser accepts, by source operand count and position:
        `{(1, 0): {('parentheses', 1)}}` when the only operand may be written `(vec)`.'''
        forms: dict[tuple[int, int], set[EnclosureRequirement]] = {}
        for count in self.source_operand_counts():
            for position in range(count):
                for operand in self.candidate_operands(position, count):
                    if operand.enclosure_depth > 0:
                        forms.setdefault((count, position), set()).add((operand.enclosure, operand.enclosure_depth))
        return forms

    def use_instruction_enclosed_forms(self, forms: dict[tuple[int, int], set[EnclosureRequirement]]) -> None:
        '''Read enclosures by the forms of the whole instruction, all variants together, rather
        than this parser's own.'''
        self._instruction_enclosed_forms = forms

    def enclosure_requirements(self, operands: list[str]) -> list[EnclosureRequirement | None]:
        '''For each source operand, the enclosed form it must be read as: the deepest form the
        instruction configures at its position that wraps the whole operand, or None.'''
        requirements: list[EnclosureRequirement | None] = []
        for position, operand_text in enumerate(operands):
            forms = self._instruction_enclosed_forms.get((len(operands), position), ())
            deepest_first = sorted(forms, key=lambda form: form[1], reverse=True)
            requirements.append(next(
                (form for form in deepest_first if enclosure_depth(operand_text, *ENCLOSURES[form[0]]) >= form[1]),
                None,
            ))
        return requirements

    def disallowed_combination(
        self,
        line_id: LineIdentifier,
        operands: list[str],
        register_labels: set[str],
        memzone_manager: MemoryZoneManager,
    ) -> list[str] | None:
        '''Return the operand ids if ``operands`` match an operand set combination listed in
        ``disallowed_pairs``, otherwise None.'''
        model = self._operand_sets_model
        if model is None or 'disallowed_pairs' not in model._config or len(operands) != model.operand_count:
            return None
        operand_ids: list[str] = []
        requirements = self.enclosure_requirements(operands)
        for operand_set, operand_text, requirement in zip(model._operand_sets, operands, requirements):
            try:
                parsed = operand_set.parse_operand(
                    line_id, operand_text, register_labels, memzone_manager, enclosure_requirement=requirement,
                )
            except Exception:
                return None
            if parsed is None:
                return None
            operand_ids.append(parsed.operand.id)
        if operand_ids in model._config['disallowed_pairs']:
            return operand_ids
        return None

    def find_matching_operands(
        self, line_id: LineIdentifier,
        operands: list[str],
        register_labels: set[str],
        memzone_manager: MemoryZoneManager,
    ) -> MatchedOperandSet:
        ''' the general goal of this method is to determin if any operands configured for this parser matched.
        If so, return the byte code parts associated with those oeprands. If not, return a flag indicating that
        this operand profile did not match.
        '''
        matched_operands: list[ParsedOperand] = []

        if self.operand_count == 0 and len(operands) == 0:
            return MatchedOperandSet([], False, False)
        requirements = self.enclosure_requirements(operands)

        # Step 1 - Look for specific operand matches
        if self._specific_operands_model is not None:
            matched_operands = \
                self._specific_operands_model.find_operands_from_specific_operands(
                        line_id,
                        operands,
                        self.operand_count,
                        register_labels,
                        memzone_manager,
                        enclosure_requirements=requirements,
                    )
            if matched_operands is not None:
                return matched_operands

        # Step 2 - Find an allowed combination match from an operand set
        if self._has_operand_sets:
            matched_operands = \
                self._operand_sets_model.find_operands_from_operand_sets(
                    line_id, operands, register_labels, memzone_manager, enclosure_requirements=requirements,
                )
            if matched_operands is not None:
                return matched_operands

        # if we are here, it's because no operands were parsed
        return None


def share_enclosed_forms(parsers: list[OperandParser | None]) -> None:
    '''Give each of an instruction's variant parsers the enclosed forms of all of them, so an
    enclosure means the same thing whichever variant is being tried.'''
    forms: dict[tuple[int, int], set[EnclosureRequirement]] = {}
    for parser in parsers:
        if parser is not None:
            for key, parser_forms in parser.enclosed_forms().items():
                forms.setdefault(key, set()).update(parser_forms)
    for parser in parsers:
        if parser is not None:
            parser.use_instruction_enclosed_forms(forms)


class MatchedOperandSet:
    def __init__(self, operands: list[ParsedOperand], reverse_arg_order: bool, reverse_op_bytecode_order: bool) -> None:
        self._operands = operands
        self._reverse_arg_order = reverse_arg_order
        self._reverse_op_bytecode_order = reverse_op_bytecode_order

    def __repr__(self) -> str:
        return str(self)

    def __str__(self) -> str:
        return f'MatchedOperandSet<{self._operands}>'

    @property
    def operands(self) -> list[ParsedOperand]:
        return self._operands

    def generate_bytecode(self, base_bytecode: ByteCodePart, base_bytecode_suffix: ByteCodePart) -> list[ByteCodePart]:
        machine_code: list[ByteCodePart] = [base_bytecode]
        suffix_op_bytecode: list[ByteCodePart] = []
        prefix_op_bytecode: list[ByteCodePart] = []
        # first add bytecode
        for op in self._operands:
            if op.bytecode is not None:
                if op.operand.bytecode_position == OperandBytecodePositionType.SUFFIX:
                    suffix_op_bytecode.append(op.bytecode)
                elif op.operand.bytecode_position == OperandBytecodePositionType.PREFIX:
                    prefix_op_bytecode.insert(0, op.bytecode)

        if self._reverse_op_bytecode_order:
            suffix_op_bytecode.reverse()
            prefix_op_bytecode.reverse()
        machine_code = prefix_op_bytecode + machine_code + suffix_op_bytecode

        if base_bytecode_suffix is not None:
            machine_code.append(base_bytecode_suffix)
        # now add arguments
        # Reversing the argument order reverses the operands; one operand's arguments keep their order.
        operand_arguments = [op.arguments for op in self._operands]
        if self._reverse_arg_order:
            operand_arguments.reverse()
        for arguments in operand_arguments:
            machine_code.extend(arguments)
        return machine_code
