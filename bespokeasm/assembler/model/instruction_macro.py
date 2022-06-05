import sys

from bespokeasm.assembler.model.instruction_base import InstructionBase
from bespokeasm.assembler.model.operand_set import OperandSetCollection
from bespokeasm.assembler.model.operand_parser import OperandParser
from bespokeasm.assembler.line_identifier import LineIdentifier


class MacroLineIdentifier(LineIdentifier):
    def __init__(self, macro_memonic: str, macro_step: int, macro_lineid: LineIdentifier) -> None:
        super().__init__(macro_lineid.line_num, macro_lineid.filename)
        self._macro = macro_memonic
        self._step = macro_step

    def __str__(self) -> str:
        return super().__str__() + f', macro {self._macro} step {self._step}'


class InstructionMacroVariant(InstructionBase):
    def __init__(
                self,
                mnemonic: str,
                macro_variant_config: dict,
                operand_set_collection: OperandSetCollection,
                default_endian: str,
                registers: set[str],
                variant_num: int,
            ) -> None:
        super().__init__(mnemonic, default_endian, registers)
        self._variant_config = macro_variant_config
        self._variant_num = variant_num

        if 'operands' in self._variant_config:
            self._operand_parser = OperandParser(
                mnemonic,
                self._variant_config.get('operands', None),
                operand_set_collection,
                default_endian,
                registers,
            )
            self._operand_parser.validate(mnemonic)
        else:
            self._operand_parser = None

    @property
    def operand_count(self) -> int:
        return self._operand_parser.operand_count

    @property
    def base_bytecode_size(self) -> int:
        sys.exit('ERROR - InstrutionMacroVariant.base_bytecode_size is unimplemented')
        return 0

    def __str__(self) -> str:
        operand_str = str(self._operand_parser) if self._operand_parser is not None else "NO_OPERANDS"
        return f'InstrutionMacroVariant<{self._mnemonic, operand_str}>'


class InstructionMacro(InstructionBase):
    '''
    An object that consists of a composable sequence of instruction objects.
    '''

    # config dict schema:
    #
    # macro_menomic: [
    #  # list of variants
    #  - {
    #   operands: [
    #       op_name : {
    #           # normal operand config
    #       },
    #       op2_name : {
    #           # normal operand config
    #       }
    #   ],
    #   instructions: [
    #       # instructions are simply their text representation with special labels
    #       # for the passed operands
    #       #      @ARG(op_name) - emits the string of the operand argument. The operand type
    #       #                      determins what its argument is. Expressions are not resolvbed yet,
    #       #                      the original string is what is passed.
    #       #      @OP(op_name)  - emits the string of the entire operand, as is.  Expressions are not resolved yet.
    #       #
    #       # these strings will be iterpreted as is. For example, they could be inserted into an express:
    #       #     macro = "push4 12955"
    #       #
    #       #  could be composed of the individual intructions of
    #       #       push2 ((@ARG(immediate)) >> 16)
    #       #       push2 ((@ARG(immediate) & $0000FFFF)
    #       #
    #               "instruction 1",
    #               "instruction 2",
    #                   ...
    #   ]
    # }
    # - { variant }
    #
    # operand supported modifications
    #
    #   * NumericExpressionOperand:
    #       - augment expression. original expression is treated as an atomic entity.
    #   * IndirectNumericOperand:
    #       - augment numeric expression.  original expression is treated as an atomic entity.
    #   * IndirectRegisterOperand:
    #       - augment numeric expression of offset.  original expression is treated as an atomic entity.
    #
    def __init__(
                self,
                mnemonic: str,
                macro_config: list[dict],
                operand_set_collection: OperandSetCollection,
                default_endian: str,
                registers: set[str]
            ) -> None:
        super().__init__(mnemonic, default_endian, registers)
        self._config = macro_config

        variant_num = 0
        self._variants: list[InstructionMacroVariant] = []
        for variant_config in self._config:
            variant_num += 1
            self._variants.append(
                InstructionMacroVariant(
                    mnemonic,
                    variant_config,
                    operand_set_collection,
                    default_endian,
                    registers,
                    variant_num
                )
            )

    @property
    def variants(self) -> list[InstructionMacroVariant]:
        return self._variants

    def __str__(self) -> str:
        return f'InstructionMacro<{self._mnemonic}>'
