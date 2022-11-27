This is a **Work in Progress**

## Instruction Set
Generally, the original 8085 opcode mnemonics documented above is replicated in this ISA configuration for **BespokeASM**. However, there are some small modifications and additions to the instructions set syntax:

* The 8-bit data source `m` is a psuedonym for the value at the memory address contined in register pair `hl`. This 8085 ISA configuration supports using either the traditional notation of `m` to indicate the register `hl` indirect addressing more, or the **BespokeASM** syntax of `[hl]` to indicate the indirect register addressing mode. Using either `m` and `[hl]` as an operand produces the same bytecode. The `[hl]` provides a more descriptive syntax as to what is happening that is consistent with **BespokeASM**'s addressing mode syntax.
* Where register names `b`, `d`, and `h` are used to indicated register pairs `bc`, `de`, and `hl` (respectively), the register pair's full name `bc`, `de`, and `hl`) can alternatively be used. This would make thinks more explicit that a register pair is being used.
* Traditional Intel 8085 assemblers support several directives, such as `DB` and `DW`. These are not supported in **BespokeASM**. Insted, use the [**BespokeASM** directives](https://github.com/michaelkamprath/bespokeasm/wiki/Assembly-Language-Syntax#directives) to accomplish similar outcomes.
