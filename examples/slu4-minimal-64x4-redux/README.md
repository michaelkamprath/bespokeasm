# Minimal 64x4 Redux Home Computer
*Current as of v1.4.x of the Minimal 64x4 Redux Home Computer*

The Minimal 64x4 Redux Home Computer (Minimal 64) is TTL CPU designed by Carsten Herting (slu4). Carsten has made his [Minimal 64x4 Redux design open and available to others](https://github.com/slu4coder/Minimal-64x4-Home-Computer) to build. The Minimal 64x4 Redux is an improvedment on The Minimal 64x4 Home Computer. Carsten has done and amazing job [documenting the Minimal 64x4 Redux](https://docs.google.com/document/d/1-nDv_8WEG1FrlO3kEK0icoYo-Z-jlhpCMiCstxGOCjQ/edit?usp=sharing).

## Minimal 64x4 Redux Assembly
The **BespokeASM** instruction set configration file [`slu4-minimal-64x4-redux.yaml`](slu4-minimal-64x4-redux.yaml) is available in this directory. Assuming that **BespookeASM** is [properly installed in the current python environment](https://github.com/michaelkamprath/bespokeasm/wiki/Installation-and-Usage#installation), to compile Minimal 64x4 Redux assembly into a Intel Hex representation that the Minimal 64x4 Redux OS's `receive` instruction can take, use the following command:

```sh
bespokeasm compile -n -p -t intel_hex -c /path/to/slu4-minimal-64x4-redux.yaml /path/to/my-code.min64x4r
```

The arguments to the command above are:

* `-n` - Indicates that no binary image should be generated.
* `-p` - indicates that a textual representation of the assembled code should be emitted.
* `-t intel_hex` - Specifies the format of the textual rerpesentation of the compiled code, in this case being Intel Hex. If you ommit this option, the default textual representation of an human-readable listing will be used.
* `-c /path/to/slu4-minimal-64x4-redux.yaml` - The file path to the **BespokeASM** instruction set configuration for the Minimal 64x4 Redux.
* `/path/to/my-code.min64x4r` - The file path to the Minimal 64x4 Redux assembly code to be compiled. Here by convention the assembly code has a file extension of `.min64x4r`. While **BespokeASM** can work with any file extension for the code, the convention is used so that code editors know what file type they are editing and thus are able to support syntax highlighting specific to the Minimal 64x4 assembly syntax. See [**BespokeASM**'s documentation on syntax highlighting support](https://github.com/michaelkamprath/bespokeasm/wiki/Installation-and-Usage#installing-language-extensions) for more information.

Once compiled, the intel hex output can be copied and pasted into the Minimal 64x4 Redux OS's terminal window to load the code into the Minimal 64x4 Redux's memory using it's `receive` command.

### Instruction Set
Carsten Herting thoroughly documents [the instruction set for the Minimal 64x4 Redux in his user guide](https://docs.google.com/document/d/1-nDv_8WEG1FrlO3kEK0icoYo-Z-jlhpCMiCstxGOCjQ/edit?usp=sharing). All of the documented instructions in their original syntax are implemented in in this **BespokeASM** port. However, **BespokeASM** will be case insensitive when matching instruction mnemonics.

### Instruction Macros
The following instruction macros have been added in the ISA configuration file for the Minimal 64x4 Redux. All macros that interact with the stack maintain byte order according to the Minimal 64x4 Redux OS calling convention, which pushes the LSB of the value first despite the system otherwise using little endian byte ordering. Note that this means multibyte values on the stack cannot be used directly at their stack memory address and must be "pulled" from the stack to another memory location where they can be represented in little endian byte ordering.

| Macros Instruction | Operand 1 | Operand 2 | Description |
|:-:|:-:|:-:|:--|
| `spinit` | - | - | Init the stack popint to a value of `0xFFFE`. |
| `phsi` |  immediate | - | Pushes a 1 byte immediate byte onto the stack. |
| `phs2i` | immediate | - | Pushes a 2 byte immediate word onto the stack. |
| `phs4i` | immediate | - | Pushes a 4 byte immediate long onto the stack. |
| `phs4a` | abs address | - | Pushes a 4 byte long at an absolute address onto the stack. |
| `phsptr` | abs address | - | Pushes a 2 byte immediate absolute address onto the stack per the Min 64x4 calling convention. Similar to `phs2i` but the operand is validated as an address. |
| `phs2s` | offset | - | Pushes a 2 byte word from the stack at the given offset onto stack |
| `phs4s` | offset | - | Pushes a 4 byte long from the stack at the given offset onto stack |
| `phsz` | zero page address | - | Pushes a 1 byte value from the zero page address onto the stack. |
| `phsv` | zero page address | - | Pushes a 2 byte word from the zero page address onto the stack. |
| `phsq` | zero page address | - | Pushes a 4 byte long from the zero page address onto the stack. |
| `pls2` | - | - | Pops a 2 byte value from the stack. |
| `pls4` | - | - | Pops a 4 byte value from the stack. |
| `mws2` | abs address | offset | Copies a 2 byte word from an absolute address to a specific offset on the stack. |
| `ms2w` | offset | abs address | Copies a 2 byte word from a specific offset on the stack to an absolute address. |
| `mvs2` | zero page address | offset | Copies a 2 byte word from a zero page address to a specific offset on the stack. |
| `ms2v` | offset | zero page address | Copies a 2 byte word from a specific offset on the stack to a zero page address. |
| `ms4q` | offset | zero page address | Copies a 4 byte long from a specific offset on the stack to a zero page address. |
| `mqs4` | zero page address | offset | Copies a 4 byte long from a zero page address to a specific offset on the stack. |
| `mls4` | abs address | offset | Copies a 4 byte long from an absolute address to a specific offset on the stack. |
| `ms4l` | offset | abs address | Copies a 4 byte long from a specific offset on the stack to an absolute address. |
| `aqq` | zero page address | zero page address | Adds two 4 byte longs from zero page addresses and stores the result in the second zero page address. |
| `sqq` | zero page address | zero page address | Subtracts the first 4 byte long at a zero page address from the second and stores the result in the second zero page address. |
| `mqq` | zero page address | zero page address | Copies a 4 byte long at the first zero page address to the 4 bytes at the second zero page address |
| `mll` | abs address | abs address | Copies a 4 byte long at the first absolute address to the 4 bytes at the second absolute address |
| `mlq` | abs address | zero page address | Copies a 4 byte long at an absolute address to the 4 bytes at the zero page address |
| `m2iv` | immediate | zero page address | Copies an immediate 2 byte word to a zero page word |
| `m4iq` | immediate | zero page address | Copies an immediate 4 byte long to a zero page long |
| `clc` | - | - | Clears the carry flag. Syntactical sugar for `ADI 0` |
| `sec` | - | - | Sets the carry flag. Syntactical sugar for `SUI 0` |

### Assembly Syntax
**BespokeASM**'s syntax is close to the syntax that Carsten used for the Minimal 64x4's assembly language. However, there are some differences:

* **BespokeASM** used a different syntax for some Minimal 64x4 Redux directives:
  * The `#org` directive, which sets the next byte code address to a specific value, is replicated in **BespokeASM** with the `.org` directive.
  * The `#page` directive, which aligns the next byte code address to a page boundarry, is replicated in **BespokeASM** with the `.align` directive.
  * In general **BespokeASM** also has [a richer set of directives available](https://github.com/michaelkamprath/bespokeasm/wiki/Assembly-Language-Syntax#directives).
* The Minimal 64x4 Redux's assembler has no data type directives. Instead, the assembler directly converts numeric values and strings to byte code exactly where it sits in the code. In **BespokeASM** one must declare a data type using [a data directive](https://github.com/michaelkamprath/bespokeasm/wiki/Assembly-Language-Syntax#data) when defining data in the byte code.
  * Highly related to this is that the Minimal 64x4Redux assembler allows the direct placement of bytes using an "embedded string". That is, a string of characters surrounded by quotes that are not part of an instruction or directive. **BespokeASM** allows something similar with it's [embedded string]() data type. The main difference is that **BespokeASM**'s embedded string feature behaves similar to it's `.cstr` data directive, which means it will automatically appended a terminating character. For the Minimal 64x4 Redux ISA configation, the terminating character has been set to `0`. In the Minimal 64x4 Redux assembler, the terminating character must be explicitly added, and if you review Carsten's code, you will see that he does this where embedded strings are used in conjuction with the `_Print` routine.
* The Minimal 64x4 Redux assembler emits byte code in the order it was in the original assembly code, while **BespokeASM** emits byte code in address order. For the most part, these two orderings can be pretty much the same, however, differences will show up if multiple `.org` directives are use, memory zones are used, or multiple additional source files are included.
* The Minimal 64x4 Redux uses a `<` and `>` to do byte slicing of constant values, with `<` meaning least significant byte and `>` meaning most significant byte (and it assumes a 2 byte value). **BespokeASM** using `BYTE0(..)` and `BYTE1(..)` [to accomplish the same goals](https://github.com/michaelkamprath/bespokeasm/wiki/Assembly-Language-Syntax#numeric-expressions) (respectively).
  * It's worth noting that Minimal 64x4 Redux's assembler frequently uses the `<` operator to slice a zero page address to just it's LSB. That is, it converts the word `0x0080` to the byte `0x80`, removing the zero-valued MSB. The Minimal 64x4 Redux ISA configuration for **BespokeASM** is set up to do this LSB byte slicing automatically for zero page addresses operands in instructions that expects a zero page address. For example, in Minimal 64x4 Redux assembly, you might write `STZ <_Xpos` to store the `A` register value in the zero page address defined by the MinOS constant `_Xpos`, which has the value of `0x00C0`. In **BespokeASM** you can write `STZ _Xpos` to accomplish the same thing as the operand to `STZ` is configured to automatically slice the passed address value to just it's LSB, plus it will also ensure that the MSB of the operand value is zero producing an error if it is not thus ensuring you actually passed a zero page address.


There are several other features that **BespokeASM** provides over the Minimal 64x4 Redux assembly syntax, such as richer math expressions for constant values and [several preprocessor directives](https://github.com/michaelkamprath/bespokeasm/wiki/Assembly-Language-Syntax#preprocessor), but the differences listed above are the ones that require code written for the Minimal 64x4 Redux assembler to be altered to be assembled with **BespokeASM**.
