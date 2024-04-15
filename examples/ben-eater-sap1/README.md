# Ben Eater SAP-1 Assembler
This example configuration for BespokeASM creates a full featured assembler for [the Ben Easter SAP-1 breadboard CPU](https://eater.net/8bit).

## Instruction Set
### Syntax Notation
The general syntax of BespokeASM is explained in its wiki. This document will not replicate that. However, what is illustrated here is how that syntax is employed for the SAP-1

#### Registers
The Ben Eater SAP-1 does not use explicit registers in its instruction syntax. Instead, the sole registers that can be manipulated is the `A` and display registers, and instruction that would interact with either of these registers imply which one in their mnemonic.

### Addressing Modes
The Ben Eater SAP-1 supports only the immediate addressing mode. However, in some cases the immediate value is a memory address at which the value being operated on resides. In this sense, the immediate value operand can behave like [BespokeASM's indirect addressing mode](https://github.com/michaelkamprath/bespokeasm/wiki/Assembly-Language-Syntax#addressing-modes).

It's important to note that the SAP-1 uses a 4-bit memory address and thus has only 16 bytes of memory.
### Instructions

All instructions are expressed by the following notation:

```asm
mnemonic operand1
```

| Instruction Mnemonic | Operand | Description |
|:-:|:-:|:--|
| `nop` | - | Performs no action except advance the program counter. |
| `lda` | ***address*** | Loads the value at the memory address provided by the immediate operand into register `A`. |
| `add` | ***address*** | Adds the value at the memory address provided by the immediate operand to the value in register `A` and places results in register `A`. Sets flags. |
| `sub` | ***address*** | Subtracts the value at the memory address provided by the immediate operand from the value in register `A` and places results in register `A`. Sets flags. |
| `sta` | ***address*** | Copies the value in register `A` to the memory address provided by the immediate operand. |
| `ldi` | ***immediate*** | Loads the immediate operand into register `A`. |
| `jmp` | ***address*** | Update the program counter to the address value given by the immediate operand. |
| `jc` | ***address*** | Update the program counter to the address value given by the immediate operand if the carry flag is set. |
| `jz` | ***address*** | Update the program counter to the address value given by the immediate operand if the carry zero is set. |
| `out` | - | Copies the value in register `A` to the display register. |
| `hlt` | - | Stops the system clock. |

## Examples
Examples programs that use the syntax defined here can be found in [this directory](./).

## Compiling Code
To compile the code, follow the BespokeASM instructions using the `eater-sap1-isa.yaml` BespokeASM configuration file found in this directory. Note that this configuration file defines the file extension for Ben Easter SAP-1 assembly code to be `.sap1`. The typical compilation command will look like:

```sh
bespokeasm compile -p -c eater-sap1-isa.yaml my_code.sap1
```

### Syntax Highlighting
BespokeASM has the ability to generate for various popular text editors a syntax highlighting language extension specific to this Ben Easter SAP-1 instruction set. [See the documentation](https://github.com/michaelkamprath/bespokeasm/wiki/Installation-and-Usage#installing-language-extensions) for information for on how to install and use the language extensions.
