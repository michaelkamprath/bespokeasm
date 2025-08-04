import sys
from functools import cached_property
from typing import Literal

from bespokeasm.assembler.keywords import ASSEMBLER_KEYWORD_SET
from bespokeasm.assembler.model.instruction import Instruction
from bespokeasm.assembler.model.instruction_base import InstructionBase
from bespokeasm.assembler.model.instruction_macro import InstructionMacro
from bespokeasm.assembler.model.operand_set import OperandSetCollection


class InstructionSet(dict[str, InstructionBase]):
    def __init__(
                self,
                instructions_config: dict,
                macros_config: dict,
                operand_set_collection: OperandSetCollection,
                default_multi_word_endian: Literal['big', 'little'],
                default_intra_word_endian: Literal['big', 'little'],
                registers: set[str],
                word_size: int,
                word_segment_size: int,
            ):
        self._instructions_config = instructions_config
        self._macros_config = macros_config
        self._instruction_mnemonics: set[str] = set()
        self._macro_mnemonics: set[str] = set()

        lower_keywords = {kw.lower(): kw for kw in ASSEMBLER_KEYWORD_SET}

        # Collect all mnemonics and aliases to check for global uniqueness
        all_mnemonics = set()
        for mnemonic, instr_config in self._instructions_config.items():
            mnemonic_lower = mnemonic.lower()
            if mnemonic_lower in all_mnemonics:
                sys.exit(f'ERROR - Duplicate mnemonic or alias found: "{mnemonic_lower}"')
            all_mnemonics.add(mnemonic_lower)
            aliases = instr_config.get('aliases', [])
            for alias in aliases:
                alias_lower = alias.lower()
                if alias_lower in all_mnemonics:
                    sys.exit(f'ERROR - Duplicate mnemonic or alias found: "{alias_lower}"')
                all_mnemonics.add(alias_lower)

        for mnemonic, instr_config in self._instructions_config.items():
            mnemonic = mnemonic.lower()
            if mnemonic in lower_keywords:
                sys.exit(f'ERROR - ISA configuration defined instruction "{mnemonic}" which is also a BespokeASM keyword')
            instr_obj = Instruction(
                mnemonic,
                instr_config,
                operand_set_collection,
                default_multi_word_endian,
                default_intra_word_endian,
                registers,
                word_size,
                word_segment_size,
            )
            self[mnemonic] = instr_obj
            self._instruction_mnemonics.add(mnemonic)
            # Handle aliases
            aliases = instr_config.get('aliases', [])
            for alias in aliases:
                alias_lower = alias.lower()
                if alias_lower in lower_keywords:
                    sys.exit(f'ERROR - ISA configuration defined alias "{alias_lower}" which is also a BespokeASM keyword')
                if alias_lower in self:
                    sys.exit(
                        f'ERROR - Alias "{alias_lower}" for instruction "{mnemonic}" '
                        f'collides with another instruction or alias.',
                    )
                self[alias_lower] = instr_obj

        if self._macros_config is not None:
            # build a list of macros first so a macro can't be defined based on other macros
            macro_list: list[InstructionMacro] = []
            for mnemonic, macro_config_list in self._macros_config.items():
                mnemonic = mnemonic.lower()
                if mnemonic in lower_keywords:
                    sys.exit(f'ERROR - ISA configuration defined instruction "{mnemonic}" which is also a BespokeASM keyword')
                # check macro mnemonic is not in existing instructions
                if mnemonic in self:
                    sys.exit(f'ERROR - Macro "{mnemonic}" has same mnemonic as a configured instruction.')
                macro_list.append(
                    InstructionMacro(
                        mnemonic,
                        macro_config_list,
                        operand_set_collection,
                        default_multi_word_endian,
                        default_intra_word_endian,
                        registers,
                        word_size,
                        word_segment_size,
                    )
                )
            for macro in macro_list:
                self[macro.mnemonic] = macro
                self._macro_mnemonics.add(macro.mnemonic)

    def get(self, mnemonic: str) -> InstructionBase:
        return super().get(mnemonic, None)

    @cached_property
    def instruction_mnemonics(self) -> set[str]:
        '''returns a set of all instruction mnemonics and their aliases (not including macros)'''
        result = set()
        for mnemonic, instr in self.items():
            if isinstance(instr, Instruction):
                result.add(mnemonic)
        return result

    @property
    def operation_mnemonics(self) -> list[str]:
        '''returns list of all mnemonics, instructions and macros (including aliases)'''
        return list(self.keys())

    @property
    def macro_mnemonics(self) -> set[str]:
        return self._macro_mnemonics
