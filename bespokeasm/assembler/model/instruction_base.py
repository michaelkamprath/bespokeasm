import sys

class InstructionBase:
    def __init__(
                self,
                mnemonic: str,
                default_endian: str,
                registers: set[str]
            ) -> None:
        self._mnemonic = mnemonic
        self._default_endian = default_endian
        self._registers = registers

    def __repr__(self) -> str:
        return str(self)

    def __str__(self) -> str:
        return f'BaseInstruction<{self._mnemonic}>'

    @property
    def mnemonic(self) -> str:
        return self._mnemonic
