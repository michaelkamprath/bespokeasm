# KENBAK-1 Assembler
This example configuration for BespokeASM creates a full featured assembler for [the KENBAK-1 computer](https://en.wikipedia.org/wiki/Kenbak-1), which is considered to be the worlds first personal computer. While this configuration does not use the exact same mnemonics as [the original programming guide for the KENBAK-1](./KENBAK-Programming_Reference.pdf), all the functionality of the instruction set is present. The changes are due to keeping the instruction mnemonics and addressing mode indicators inlined with established syntax enabled by BespokeASM.

## Instruction Set
### Syntax Notation
The general syntax of BespokeASM is explained in its wiki. This document will not replicate that. However, what is illustrated here is how key elements of the KENBAK-1 instruction set architecture is enabled by BespokeASM syntax.
#### Registers
The KENBAK-1 has three actively used registers, `a`, `b`, and `x`. The KENBAK-1 also allows you to directly access the RAM addresses that back those registers. With BespokeASM, these two actions are distinct. When the register is a an enumerated operand for the instruction, for example the `ADD` addition operation where the register dictates the first two bits of the instruction byte code, then the register is referred to by the lower case `a`, `b`, or `x`. If instead you attempting to access the memory address that backs the register via one of the addressing modes operands, then you should use one of the compiler constants that maps to the register's address (see below).

#### Addressing Modes
The KENBAK-1 programming reference describes fie addressing modes to be used as one of the operands in some of the instructions. The below table maps them to BespokeASM syntax.

| KENBAK-1 Addressing Mode | [BespokeASM Addressing Mode](https://github.com/michaelkamprath/bespokeasm/wiki/Assembly-Language-Syntax#addressing-modes) | Bespoke ASM Notation for KENBAK-1 | Descriptions |
|:-:|:-:|:-:|:--|
|**Constant** | **Immediate** | `expression` | The [numerical expression can](https://github.com/michaelkamprath/bespokeasm/wiki/Assembly-Language-Syntax#numeric-values) be any combinations of numbers, labels, and operators that can be resolved at compile time.  |
|**Memory**| **Indirect** | `[expression]` | The value to be used is at location in memory provided by the immediate value of the instruction. This immediate value can be provided by a numerical expression, and is bounded by square brackets, `[` and `]`. |
| **Indirect**/**Deferred**| **Deferred** | `[[expression]]` | The value to be used is at a memory address that is contained at a memory address provided by the immediate value of the instruction. This immediate value can be provided by a numerical expression, and is bounded by two square brackets, `[[` and `]]`. |
| **Indexed** | **Indirect Register** | `[x + expression]` | The value to be used is at an address that is found by adding the value currently in the `x` register to the immediate value of the instruction, also referred to as the offset in BespokeASM parlance. The offset value is provided by a numerical expression. On the KENBAK-1, this addressing mode only works with the `x` register. Nonetheless, the `x` register is always notated in the BespokeASM syntax. |
| **Indirect Indexed** | **Indirect Indexed Register** | `[x + [expression]]`| The value to be used is at an address that is found by adding the value currently in the `x` register to the value at the address provided by the immediate value of the instruction. Similar to the **Indirect Register** addressing mode, but the offset is provided by its own **Indirect** value. Note the square brackets `[` and `]` around the operand as a whole and then another set around the offset expression. |

### Instructions
All instructions are expressed by the following notation:
```asm
mnemonic operand1, operand2
```

The number of operands required depends on the instruction mnemonic. All operands use BespokeASM notation.

| Instruction Mnemonic | Operand 1 | Operand 2 | Description |
|:-:|:-:|:-:|:--|
| `noop` | - | - | The program counter is advanced, but no other operation occurs. |
| `halt` | - | - | Causes the computer to go from run state to halt state. |
| `ld` | ***register*** | ***addressing mode*** | Copies the value indicated by the addressing mode operand to the indicated register. |
| `ld` | ***addressing mode*** | ***register*** | Copies the value in the indicated register to the memory location indicated by the addressing mode. If the Immediate addressing mode is used, actually copies the value to the byte following the instruction. This is the KENBAK-1's `STORE` instruction using a unified notation with the `LOAD` instruction. |
| `jp` | ***immediate value*** or ***deferred value*** | - | Jump direct to the address indicated by the immediate value or the deferred value in the operand. |
| `jpnz` | ***register*** | ***immediate value*** or ***deferred value*** | Jump direct to the address indicated by the immediate value or deferred value if the contents in the indicated register are not equal to zero. |
| `jpz` | ***register*** | ***immediate value*** or ***deferred value*** | Jump direct to the address indicated by the immediate value or deferred value if the contents in the indicated register are equal to zero. |
| `jpn` | ***register*** | ***immediate value*** or ***deferred value*** | Jump direct to the address indicated by the immediate value or deferred value if the contents in the indicated register are less than zero. |
| `jpp` | ***register*** | ***immediate value*** or ***deferred value*** | Jump direct to the address indicated by the immediate value or deferred value if the contents in the indicated register are greater than or equal to zero. |
| `jppnz` | ***register*** | ***immediate value*** or ***deferred value*** | Jump direct to the address indicated by the immediate value or deferred value if the contents in the indicated register are strictly greater than zero. |
| `jm` | ***immediate value*** or ***deferred value*** | - | Jump to the address indicated by the immediate value or the deferred value in the operand and mark the return address in the first byte of the address jumped to. |
| `jmnz` | ***register*** | ***immediate value*** or ***deferred value*** | Jump to the address indicated by the immediate value or the deferred value in the operand and mark the return address in the first byte of the address jumped to if the contents in the indicated register are not equal to zero. |
| `jmz` | ***register*** | ***immediate value*** or ***deferred value*** | Jump to the address indicated by the immediate value or the deferred value in the operand and mark the return address in the first byte of the address jumped to if the contents in the indicated register are equal to zero. |
| `jmn` | ***register*** | ***immediate value*** or ***deferred value*** | Jump to the address indicated by the immediate value or the deferred value in the operand and mark the return address in the first byte of the address jumped to if the contents in the indicated register are less than zero. |
| `jmp` | ***register*** | ***immediate value*** or ***deferred value*** | Jump to the address indicated by the immediate value or the deferred value in the operand and mark the return address in the first byte of the address jumped to if the contents in the indicated register are greater than or equal to zero. |
| `jmpnz` | ***register*** | ***immediate value*** or ***deferred value*** | Jump to the address indicated by the immediate value or the deferred value in the operand and mark the return address in the first byte of the address jumped to if the contents in the indicated register are strictly greater than zero. |
| `skip0` | ***bit index*** | ***indirect value***| Skips the next instruction (2 bytes) if the indicated bit of the value found a the provided memory address is zero. The ***bit index*** can be provided by a numerical expression, but must resolve to a value between 0 and 7. |
| `skip1` | ***bit index*** | ***indirect value***| Skips the next instruction (2 bytes) if the indicated bit of the value found a the provided memory address is one. The ***bit index*** can be provided by a numerical expression, but must resolve to a value between 0 and 7. |
| `set0` | ***bit index*** | ***indirect value***| Sets the indicated bit of the value found a the provided memory address to zero. The ***bit index*** can be provided by a numerical expression, but must resolve to a value between 0 and 7. |
| `set1` | ***bit index*** | ***indirect value***| Sets the indicated bit of the value found a the provided memory address to one. The ***bit index*** can be provided by a numerical expression, but must resolve to a value between 0 and 7. |
| `add` | ***register*** | ***addressing mode*** | Adds the value indicated by the addressing mode of the second operand to the value in the indicated register, replacing the current value in the same register. |
| `sub` | ***register*** | ***addressing mode*** | Subtracts the value indicated by the addressing mode of the second operand from the value in the indicated register, replacing the current value in the same register. |
| `and` | ***addressing mode*** | - | Performs a logical `AND` operation between the value indicated by the operand's addressing mode and the value in the `a` register, replacing the value in the `a` register. |
| `or` | ***addressing mode*** | - | Performs a logical `OR` operation between the value indicated by the operand's addressing mode and the value in the `a` register, replacing the value in the `a` register. |
| `lneg` | ***addressing mode*** | - | The `a` register is loaded with the arithmetic complement of of the value indicated by the operand's addressing mode. |
| `sftl` | ***register `a`*** or ***register `b`***| `1`, `2`, `3`, or `4` | Left shifts the bit value in the indicated register (only `a` or `b`) by the number of bits indicated by the second operand. Note that only certain values are allowed of the second operand, but it can be expressed by a numerical expression. |
| `sftr` | ***register `a`*** or ***register `b`***| `1`, `2`, `3`, or `4` | Right shifts the bit value in the indicated register (only `a` or `b`) by the number of bits indicated by the second operand. Note that only certain values are allowed of the second operand, but it can be expressed by a numerical expression. |
| `rotl` | ***register `a`*** or ***register `b`***| `1`, `2`, `3`, or `4` | Left rotates the bit value in the indicated register (only `a` or `b`) by the number of bits indicated by the second operand. Note that only certain values are allowed of the second operand, but it can be expressed by a numerical expression. |
| `rotr` | ***register `a`*** or ***register `b`***| `1`, `2`, `3`, or `4` | Left rotates the bit value in the indicated register (only `a` or `b`) by the number of bits indicated by the second operand. Note that only certain values are allowed of the second operand, but it can be expressed by a numerical expression. |

### Defined Memory Symbols
The KENBAK-1 configuration file for BespokeASM defines some memory addresses that can be used in code being compiled for the KENBAK-1. All of these predefined memory address symbols may be used in operands anywhere that a memory address can be used. The predefined symbols are:

| Symbol | Memory Address For | Notes |
|:-:|:-:|:-|
|`A_REG`| `a` register | This memory address backs the `a` register |
|`B_REG `| `b` register | This memory address backs the `b` register |
|`X_REG `| `x` register | This memory address backs the `x` register |
|`A_REG_F`| `a` register flags| Overflow and Carry flags for the `a` register.|
|`B_REG_F`| `b` register flags| Overflow and Carry flags for the `b` register.|
|`X_REG_F`| `x` register flags| Overflow and Carry flags for the `x` register.|
|`P_REG `| program counter | Typically the program counter would not be accessed directly. |
|`OUTPUT`|output register| Place data here to be displayed on the KENBAK-1 LEDs.|
|`INPUT`|input register| Where to read data from for user input.|

Note that these symbols are case sensitive.

### Other
The KENBAK-1 configuration for BespokeASM automatically sets the origin for code generation to address value `4`, which is typically where the start of KENBAK-1 programs reside in memory. Use the `.org` directive if you wish you change this.

BespokeASM will issue a warning if the generate code or data addresses should ever overlap with the builtin address values for the defined memory locations described above.

## Examples
Examples programs that use the syntax defined here can be found in [this directory](./).

## Compiling Code
To compile the code, follow the BespokeASM instructions using the `kenbak-1-isa.yaml` BespokeASM configuration file found in this directory. Note that this configuration file defines the file extension for KENBAK-1 assembly code to be `.kb1`. The typical compilation command will look like:

```sh
bespokeasm compile -p -c kenbak-1-isa.yaml my_code.kb
```

### Syntax Highlighting
BespokeASM has the ability to generate for various popular text editors a syntax highlighting language extension specific to this KENBAK-1 instruction set. [See the documentation](https://github.com/michaelkamprath/bespokeasm/wiki/Installation-and-Usage#installing-language-extensions) for information for on how to install and use the language extensions.
