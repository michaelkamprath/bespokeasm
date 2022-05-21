import sys

from bespokeasm.assembler.line_identifier import LineIdentifier
from bespokeasm.assembler.byte_code.assembled import AssembledInstruction

class InstructionBase:
    def __init__(
                self,
                mnemonic: str,
                default_endian: str,
                registers: set[str]
            ) -> None:
        self._mnemonic = mnemonic


    def __repr__(self) -> str:
        return str(self)

    def __str__(self) -> str:
        return f'BaseInstruction<{self._mnemonic}>'

    @property
    def mnemonic(self) -> str:
        return self._mnemonic

    def generate_bytecode_parts(
        self,
        line_id: LineIdentifier,
        mnemonic: str,
        operands: str,
        default_endian: str,
        register_labels: set[str],
    ) -> AssembledInstruction:
        if mnemonic != self.mnemonic:
            # this shouldn't happen
            sys.exit(f'ERROR: {line_id} - INTERNAL - Asked instruction {self} to parse mnemonic "{mnemonic}"')

        sys.exit(f'INTERNAL ERROR: {line_id} - Instruction "{mnemonic}" is not implemented.')
