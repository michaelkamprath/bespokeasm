class InstructionBase:
    def __init__(
                self,
                mnemonic: str,
                default_multi_word_endian: str,
                default_intra_word_endian: str,
                registers: set[str]
            ) -> None:
        self._mnemonic = mnemonic
        self._default_multi_word_endian = default_multi_word_endian
        self._default_intra_word_endian = default_intra_word_endian
        self._registers = registers

    def __repr__(self) -> str:
        return str(self)

    def __str__(self) -> str:
        return f'BaseInstruction<{self._mnemonic}>'

    @property
    def mnemonic(self) -> str:
        return self._mnemonic
