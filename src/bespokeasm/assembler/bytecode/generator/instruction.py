import sys

from bespokeasm.assembler.analysis import AnalysisOperand
from bespokeasm.assembler.analysis import freeze_analysis_value
from bespokeasm.assembler.analysis import FrozenExpression
from bespokeasm.assembler.analysis import InstructionAnalysisRecord
from bespokeasm.assembler.analysis import OperandSemanticKind
from bespokeasm.assembler.analysis import SourceIdentity
from bespokeasm.assembler.bytecode.assembled import AssembledInstruction
from bespokeasm.assembler.bytecode.parts import ExpressionByteCodePart
from bespokeasm.assembler.bytecode.parts import NumericByteCodePart
from bespokeasm.assembler.line_identifier import LineIdentifier
from bespokeasm.assembler.memory_zone.manager import MemoryZoneManager
from bespokeasm.assembler.model import AssemblerModel
from bespokeasm.assembler.model.instruction import Instruction
from bespokeasm.assembler.model.instruction import InstructionVariant
from bespokeasm.assembler.model.operand.operand_label import OperandLabelError
from bespokeasm.assembler.model.operand_parser import MatchedOperandSet
from bespokeasm.assembler.parsing import split_operands


class InstructionBytecodeGenerator:

    @classmethod
    def generate_bytecode_parts(
        cls,
        instruction: Instruction,
        line_id: LineIdentifier,
        mnemonic: str,
        operands: str,
        isa_model: AssemblerModel,
        memzone_manager: MemoryZoneManager,
        source_mnemonic: str | None = None,
        source_identity: SourceIdentity | None = None,
    ) -> AssembledInstruction:
        if mnemonic != instruction.mnemonic:
            # this shouldn't happen
            sys.exit(f'ERROR: {line_id} - INTERNAL - Asked instruction {instruction} to parse mnemonic "{mnemonic}"')
        source_mnemonic = mnemonic if source_mnemonic is None else source_mnemonic.lower()

        operand_label_error: OperandLabelError | None = None
        for variant in instruction.matching_variants(source_mnemonic):
            try:
                assembled_instruction = InstructionBytecodeGenerator.generate_variant_bytecode_parts(
                    variant,
                    line_id,
                    mnemonic,
                    source_mnemonic,
                    operands,
                    isa_model,
                    memzone_manager,
                    source_identity,
                )
            except OperandLabelError as e:
                if operand_label_error is None:
                    operand_label_error = e
                continue
            if assembled_instruction is not None:
                return assembled_instruction

        if operand_label_error is not None:
            isa_model.diagnostic_reporter.error(
                operand_label_error.line_id,
                operand_label_error.message,
                category=operand_label_error.category,
            )
        isa_model.diagnostic_reporter.error(
            line_id,
            f'Instruction "{source_mnemonic}" has no valid operands configured.',
        )

    @classmethod
    def generate_variant_bytecode_parts(
        cls,
        variant: InstructionVariant,
        line_id: LineIdentifier,
        mnemonic: str,
        source_mnemonic: str,
        operands: str,
        isa_model: AssemblerModel,
        memzone_manager: MemoryZoneManager,
        source_identity: SourceIdentity | None,
    ) -> AssembledInstruction:
        if mnemonic != variant.mnemonic:
            # this shouldn't happen
            sys.exit(f'ERROR: {line_id} - INTERNAL - Asked instruction {variant} to parse mnemonic "{mnemonic}"')
        operand_list = split_operands(operands)

        # generate the machine code parts
        multi_word_endian = variant._variant_config['bytecode'].get('multi_word_endian', isa_model.multi_word_endianness)
        intra_word_endian = variant._variant_config['bytecode'].get('intra_word_endian', isa_model.intra_word_endianness)
        base_bytecode = NumericByteCodePart(
            variant.base_bytecode_value,
            variant.base_bytecode_size,
            False,
            multi_word_endian,
            intra_word_endian,
            line_id,
            isa_model.word_size,
            isa_model.word_segment_size,
        )
        base_bytecode_suffix = None
        if variant.has_bytecode_suffix:
            base_bytecode_suffix = NumericByteCodePart(
                variant.suffix_bytecode_value,
                variant.suffix_bytecode_size,
                False,
                multi_word_endian,
                intra_word_endian,
                line_id,
                isa_model.word_size,
                isa_model.word_segment_size,
            )

        if variant._operand_parser is not None:
            matched_operands: MatchedOperandSet
            matched_operands = variant._operand_parser.find_matching_operands(
                line_id, operand_list, isa_model.registers, memzone_manager,
            )
            if matched_operands is None:
                return None
            machine_code = matched_operands.generate_bytecode(base_bytecode, base_bytecode_suffix)
            operand_label_bindings = []
            for parsed_operand in matched_operands.operands:
                if parsed_operand.operand_label is None:
                    continue
                if parsed_operand.argument is None:
                    raise OperandLabelError(
                        line_id,
                        f'Operand label "{parsed_operand.operand_label}" is invalid because '
                        'the annotated operand does not emit argument bytes.',
                    )
                operand_label_bindings.append((parsed_operand.operand_label, parsed_operand.argument))
        elif len(operand_list) > 0:
            # This variant was expecting no operands but some were found. No match.
            return None
        else:
            machine_code = [base_bytecode]
            operand_label_bindings = []
            matched_operands = MatchedOperandSet([], False, False)

        analysis_record = None
        if isa_model.analysis_records_enabled:
            if source_identity is None:
                raise RuntimeError('analysis-enabled instruction has no source identity')
            analysis_operands = []
            for parsed_operand in matched_operands.operands:
                if parsed_operand.operand.null_operand:
                    continue
                if isinstance(parsed_operand.argument, ExpressionByteCodePart):
                    expression_part = parsed_operand.argument
                elif isinstance(parsed_operand.bytecode, ExpressionByteCodePart):
                    expression_part = parsed_operand.bytecode
                else:
                    expression_part = None
                expression = (
                    FrozenExpression.from_node(expression_part.parsed_expression)
                    if expression_part is not None
                    else None
                )
                if 'REGISTER' in parsed_operand.operand.type.name:
                    semantic_kind = OperandSemanticKind.RUNTIME_REGISTER
                elif expression is not None:
                    semantic_kind = OperandSemanticKind.COMPILE_TIME_EXPRESSION
                else:
                    semantic_kind = OperandSemanticKind.OPAQUE
                analysis_operands.append(
                    AnalysisOperand(
                        operand_id=parsed_operand.operand_id,
                        operand_type=parsed_operand.operand.type,
                        source_text=parsed_operand.operand_string,
                        semantic_kind=semantic_kind,
                        expression=expression,
                    )
                )
            analysis_record = InstructionAnalysisRecord(
                source_identity=source_identity,
                selected_variant=variant,
                variant_number=variant.variant_number,
                source_mnemonic=source_mnemonic,
                canonical_mnemonic=mnemonic,
                semantics=freeze_analysis_value(variant.semantic_config),
                operands=tuple(analysis_operands),
            )

        return AssembledInstruction(
            line_id,
            machine_code,
            isa_model.word_size,
            isa_model.word_segment_size,
            multi_word_endian,
            intra_word_endian,
            operand_label_bindings=operand_label_bindings,
            analysis_record=analysis_record,
        )
