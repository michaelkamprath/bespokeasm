import sys

from bespokeasm.assembler.line_identifier import LineIdentifier
from bespokeasm.assembler.bytecode.assembled import AssembledInstruction, CompositeAssembledInstruction
from bespokeasm.assembler.model.operand_parser import MatchedOperandSet
from bespokeasm.assembler.model.instruction_macro import InstructionMacro, InstructionMacroVariant, MacroLineIdentifier
from bespokeasm.assembler.model import AssemblerModel
from bespokeasm.assembler.model.instruction_parser_base import InstructioParserBase
from bespokeasm.assembler.memory_zone.manager import MemoryZoneManager


class MacroBytecodeGenerator:

    @classmethod
    def generate_bytecode_parts(
        cls,
        macro: InstructionMacro,
        line_id: LineIdentifier,
        mnemonic: str,
        operands: str,
        isa_model: AssemblerModel,
        memzone_manager: MemoryZoneManager,
        parser_class: type[InstructioParserBase],
    ) -> AssembledInstruction:
        if mnemonic != macro.mnemonic:
            # this shouldn't happen
            sys.exit(f'ERROR: {line_id} - INTERNAL - Asked macro {macro} to parse mnemonic "{mnemonic}"')

        for variant in macro.variants:
            assembled_instruction = MacroBytecodeGenerator.generate_variant_bytecode_parts(
                variant,
                line_id,
                mnemonic,
                operands,
                isa_model,
                memzone_manager,
                parser_class,
            )
            if assembled_instruction is not None:
                return assembled_instruction

        sys.exit(f'ERROR: {line_id} - Instruction "{mnemonic}" has no valid operands configured.')

    @classmethod
    def generate_variant_bytecode_parts(
        cls,
        variant: InstructionMacroVariant,
        line_id: LineIdentifier,
        mnemonic: str,
        operands: str,
        isa_model: AssemblerModel,
        memzone_manager: MemoryZoneManager,
        parser_class: type[InstructioParserBase],
    ) -> AssembledInstruction:
        if mnemonic != variant.mnemonic:
            # this shouldn't happen
            sys.exit(f'ERROR: {line_id} - INTERNAL - Asked instruction {variant} to parse mnemonic "{mnemonic}"')
        if operands is not None and operands != '':
            operand_list = operands.strip().split(',')
        else:
            operand_list = []

        # first step is to parse the macro instruction, return None if operands don't match
        matched_operands: MatchedOperandSet = None
        if variant._operand_parser is not None:
            matched_operands = variant._operand_parser.find_matching_operands(
                line_id, operand_list, isa_model.registers, memzone_manager,
            )
            if matched_operands is None:
                return None
        elif len(operand_list) > 0:
            # This variant was expecting no operands but some were found. No match.
            return None

        # second, generate list of instruction strings and comments
        if 'instructions' not in variant._variant_config:
            sys.exit(f'ERROR - macro "{mnemonic}" does not have any instructions configured.')

        instruction_lines: list[str] = []
        for step_num, instruction_format in enumerate(variant._variant_config['instructions']):
            instruction_str: str = instruction_format

            if matched_operands is not None:
                for op_num, op in enumerate(matched_operands.operands):
                    # handle @ARG
                    arg_str = f'@ARG({op_num})'
                    if arg_str in instruction_str:
                        if op.operand_argument_string is None:
                            sys.exit(
                                f'ERROR: {line_id} - Macro "{variant.mnemonic}" step {step_num} uses @ARG({op_num}) '
                                f'but no operand argument exist. Consider using @OP{step_num} instead.'
                            )
                        # gate the replace so that not called on unspported operand types
                        instruction_str = instruction_str.replace(arg_str, op.operand_argument_string)
                    # handle @REG
                    reg_str = f'@REG({op_num})'
                    if reg_str in instruction_str:
                        if op.operand_register_string is None:
                            sys.exit(
                                f'ERROR: {line_id} - Macro "{variant.mnemonic}" step {step_num} uses @REG({op_num}) '
                                f'but no operand register exist. Consider using @OP{step_num} instead.'
                            )
                        # gate the replace so that not called on unspported operand types
                        instruction_str = instruction_str.replace(reg_str, op.operand_register_string)
                    # handle @OP
                    op_str = f'@OP({op_num})'
                    if op_str in instruction_str:
                        # gate the replace so that not called on unspported operand types
                        instruction_str = instruction_str.replace(op_str, op.operand_string)

            if '@ARG' in instruction_str:
                # ensure all @ARGs are handled
                sys.exit(f'ERROR: {line_id} - Macro "{variant.mnemonic}" has unrecognized @ARG on step {step_num}')
            if '@REG' in instruction_str:
                # ensure all @REGs are handled
                sys.exit(f'ERROR: {line_id} - Macro "{variant.mnemonic}" has unrecognized @REG on step {step_num}')
            if '@OP' in instruction_str:
                # ensure all @OPs are handled
                sys.exit(f'ERROR: {line_id} - Macro "{variant.mnemonic}" has unrecognized @OP on step {step_num}')

            instruction_lines.append(instruction_str)

        # third get assembled instruction for each generated line
        assembled_instructions: list[AssembledInstruction] = []
        for step_num, instruction_str in enumerate(instruction_lines):
            macro_line_id = MacroLineIdentifier(variant.mnemonic, step_num, line_id)
            instruction = parser_class.parse_instruction(isa_model, macro_line_id, instruction_str, memzone_manager)
            assembled_instructions.append(instruction)

        # finally, pack it all together into one assembled instruction
        composite_instruction = CompositeAssembledInstruction(line_id, assembled_instructions)
        return composite_instruction
