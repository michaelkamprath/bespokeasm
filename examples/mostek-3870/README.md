# MOSTEK 3870 Assembly

This configuration for **BespokeASM** creates a full featured assembler for [the MOSTEK 3870 vintage microcontroller](https://www.cpu-world.com/CPUs/3870/index.html). Theoretically, this should also support the F8 family of CPUs in general, however that has not been tested. This implementation of an assembler for the MOSTEK 3870 (MK3870) uses all the same mnemonics as described in [the original MOSTEK 3870 documentation](./documentation/mostek3870_instructions.pdf), however the rest of the assembly language syntax is defined by **BespokeASM**'s documentation.

## Instruction Set
The instruction set for the MOSTEK 3870 is documented in these two vintage documents:

* [3870/F8 Microcomputer Data Book](http://www.bitsavers.org/components/mostek/f8/1981_3870_F8_Microcomputer_Data_Book.pdf) - Everything you need to know about the MOSTEK 3870. The instruction set description starts on page III-47 (PDF page 72), and programming examples are given on page III-67 (PDF page 92). The programming examples uses an assembler syntax different from **BespokeASM** (e.g.,the vintage MK3870 assembler didn't require a `:` at the end of label definitions), however since the mnemonic usage is the same, one should be able to apply insights gained from this document to coding for the MK3870 using **BespokeASM**.
* [MOSTEK 3870 Instructions](./documentation/mostek3870_instructions.pdf) - This document is an extract from the _3870/F8 Microcontroller Data Book_ covering just the instruction set.
* [F8 Guide to Programming](./documentation/F8_Guide_To_Programming_1977.pdf) - This document covered the F8 instruction set, which the MK3870 uses, and provides several programming techniques for the F8 family of CPUs. Some of this document was written for F8-based CPUs other than the MK3870 as it discusses hardware capabilities the MK3870 doesn't have. However, it does a more thorough job of explaining the instruction set.

Generally, the mnemonics documented above is replicated in this ISA configuration for **BespokeASM**, However, there are some small modifications to the instructions set syntax:

* The `LR r,A` and `LR A,r` instructions allow data movement between the accumulator and scratch pad registers `0` through `11` (`$B`). However the value `12` can be used for `r` and this represents the scratchpad registers pointed to by the `IS` register, similarly for `13` and `14`. The various F8 documents are inconsistent on the syntax for how use the `LR` instruction with the indirect `IS` register. Given that, this ISA implementation will use the **BespokeASM** syntax for indirect registers. That is, moving data between A and the scratch pad register pointed to by the `IS` register will take the following form:
  * `lr [is],a` : Move data from accumulator `A` to scratch pad register pointed to by register `IS`. This results in bytecode value `$5C`.
  * `lr [is]+,a` : Move data from accumulator `A` to scratch pad register pointed to by register `IS`, and then increment the `IS` value. This results in bytecode value `$5D`.
  * `lr [is]-,a` : Move data from accumulator `A` to scratch pad register pointed to by register `IS`, and then decrement the `IS` value. This results in bytecode value `$5E`.
  * `lr a,[is]` : Move data from scratch pad register pointed to by register `IS` to accumulator `A` This results in bytecode value `$4C`.
  * `lr a,[is]+` : Move data from scratch pad register pointed to by register `IS` to accumulator `A`, and then increment `IS`. This results in bytecode value `$4D`.
  * `lr a,[is]-` : Move data from scratch pad register pointed to by register `IS` to accumulator `A`, and then decrement `IS`. This results in bytecode value `$4E`.

### Macros
The MOSTEK 3870 ISA configuration file does define a number of macros to expedite programming some common and useful tasks. The defined macros are:

| Macros Instruction | Operand 1 | Operand 2 | Description|
|:-:|:-:|:-:|:--|
| `jmps` | scratch pad index | - | Set the program counter (jump) to the address value store in the two consecutive scratch pad locations starting at the scratch pad indicated in the operand. _Destroys value in `A` register._ |
|`incs`| scratch pad index | - | Increments the value contained in scratch pad location indicated by operand. _Destroys value in `A` register._ |
|`incs`| `[is]` | - | Increments the value contained in scratch pad location indicated by IS register. _Destroys value in `A` register._ |
|`incs`| `is` | - | Increments the value contained in IS register. _Destroys value in `A` register._ |
| `lris` | `a` register | scratch pad index  | Copies value at scratch pad location indicated in second operand to register `A`. |
| `liis` | scratch pad index | immediate value | Loads the immediate value into the the scratch pad RAM at the indicated scratch pad index |

## Examples
Examples programs that use the MOSTEK 3870 instruction set can be found in [this directory](./).

### MOSTEK 38P70 Computer
A reference computer has been designed based on the MOSTEK 38P70 programmable microcontroller, and can be found in [this repository](https://github.com/michaelkamprath/mostek-38p70-computer).

## Compiling Code
To compile code for the MOSTEK 3870 family of microprocessors (and possibly other F8-based CPUs), follow the BespokeASM instructions using the `mostek-3870.yaml` BespokeASM configuration file found in this directory. Note that this configuration file defines the file extension for MOSTEK 3870 assembly code to be `.af8`. The typical compilation command will look like:

```sh
bespokeasm compile -e 2047 -p -c mostek-3870.yaml my_code.af8
```


Where:

* `-e 2047` : generates a binary image with the maximum address of 2047, thus 2K bytes for a M2716 EPROM.
* `-p` : emit a pretty-print listing of the compiled assembly code.
* `-c /path/to/mostek-3870.yaml` : The path to the MOSTEK 3870 ISA BespokeASM configuration file found in this directory of the **BespokeASM** repository.
* `assembly-code.af8` : The MOSTEK 3870 assembly code to compile.

### Syntax Highlighting
BespokeASM has the ability to generate for various popular text editors a syntax highlighting language extension specific to the MOSTEK 3870 F8-based instruction set. [See the documentation](https://github.com/michaelkamprath/bespokeasm/wiki/Installation-and-Usage#installing-language-extensions) for information for on how to install and use the language extensions.
