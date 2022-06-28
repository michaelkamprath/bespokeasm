import sys

from bespokeasm.assembler.model.instruction import Instruction
from bespokeasm.assembler.model.instruction_macro import InstructionMacro
from bespokeasm.assembler.model.instruction_base import InstructionBase
from bespokeasm.assembler.model.operand_set import OperandSetCollection
from bespokeasm.assembler.keywords import ASSEMBLER_KEYWORD_SET

class InstructionSet(dict[str,InstructionBase]):
    def __init__(
                self,
                instructions_config: dict,
                macros_config: dict,
                operand_set_collection: OperandSetCollection,
                default_endian: str,
                registers: set[str]
            ):
        self._instructions_config = instructions_config
        self._macros_config = macros_config

        lower_leywords = {kw.lower():kw for kw in ASSEMBLER_KEYWORD_SET}

        for mnemonic, instr_config in self._instructions_config.items():
            mnemonic = mnemonic.lower()
            if mnemonic in lower_leywords:
                sys.exit(f'ERROR - ISA configuration defined instruction "{mnemonic}" which is also a BespokeASM keyword')
            self[mnemonic] = Instruction(mnemonic, instr_config, operand_set_collection, default_endian, registers)

        if self._macros_config is not None:
            # build a list of macros first so a macro can't be defined based on other macros
            macro_list: list[InstructionMacro] = []
            for mnemonic, macro_config_list in self._macros_config.items():
                mnemonic = mnemonic.lower()
                if mnemonic in lower_leywords:
                    sys.exit(f'ERROR - ISA configuration defined instruction "{mnemonic}" which is also a BespokeASM keyword')
                # check macro mnemonic is not in existing instructions
                if mnemonic in self:
                    sys.exit(f'ERROR - Macro "{mnemonic}" has same mnemonic as a configured instruction.')
                macro_list.append(
                    InstructionMacro(mnemonic, macro_config_list, operand_set_collection, default_endian, registers)
                )
            for macro in macro_list:
                self[macro.mnemonic] = macro

    def get(self, mnemonic:str) -> InstructionBase:
        return super().get(mnemonic, None)