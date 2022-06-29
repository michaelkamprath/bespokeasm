# Minimal UART CPU System
*Current as of v1.5.x of the Minimal UART CPU System*

The Minimal UART CPU System (Minimal CPU) is TTL CPU designed by Carsten Herting (slu4). Carsten has made his [MinCPU design open and available to others](https://github.com/slu4coder/Minimal-UART-CPU-System/) to build. The MinCPU is is well documented, and even has [a MinCPU YouTube video series](https://youtube.com/playlist?list=PLYlQj5cfIcBU5SqFe6Uz4Q31_6VZyZ8h5) dedicated to it. 

As part of his effort to demonstrate the "minimal effort" needed to make a working computer, Cartsen has already implemented a simple yet solid assembler for the Minimal CPU. So the question might be asked, "Why port the Minimal CPU to BespokeASM?" Simply put, to have a more robust assembly for the Minimal CPU. The instruction set for the Minimal CPU is simple (no overly complex instructions), an so actions like pushing a value on the stack takes at least two instructions to complete. In scenarios like this, BespokeASM's instruction macros can simplify the code needed to accomplish common tasks.

So the goal of this port to **BespokeASM** is to first support the basic instruction set of the Minimal CPU in its original form, but then build on that with richer features such as instruction macros to make assembly coding for the Minimal CPU more productive. 

## Minimal CPU Assembly

### Instruction Set
Carsten Heating thorough documents [the instruction set for the Minimal CPU in his user guide](https://docs.google.com/document/d/1c2ZHtLd1BBAwcBAjBZZJmCA3AXpbpv80dlAtsMYpuF4/edit?usp=sharing). All of the documented instructions in their original syntax are implemented in in this **BespokeASM** port. However, **BespokeASM** will be case insensitive when matching instruction mnemonics.

### Instruction Macros
The following instruction macros have been added in the ISA confutation file for the Minimal CPU:

| Macros Instruction | Operand 1 | Operand 2 | Description|
|:-:|:-:|:-:|:--|
| `pushi` | immediate | - | Push onto stack immediate 1 byte value |
| `pusha` | absolute address | - | Push onto stack 1 byte value at absolute address |
| `pushr` | relative address | - | Push onto stack 1 byte value at relative address |
| `push2i` | immediate | - | Push onto stack immediate 2 byte value |
| `push2a` | absolute address | - | Push onto stack 2 byte value at absolute address |
| `push2s` | stack offset | - | Push onto stack 2 byte value currently found at indicated stack offset |
| `push4i` | immediate | - | Push onto stack immediate 4 byte value |
| `push4a` | absolute address | - | Push onto stack 4 byte value at absolute address |
| `push4s` | stack offset | - | Push onto stack 4 byte value currently found at indicated stack offset |
| `pull2` | - | - | Pull 2 bytes off the stack |
| `pull4` | - | - | Pull 4 bytes off the stack |
| `cpy2as` | absolute address | stack offset | Copy 2 bytes of data sourced from indicated stack offset to memory starting at indicated absolute address. Convert from stack big endian ordering to RAM little endian ordering. |
| `cpy2sa` | stack offset | absolute address | Copy 2 bytes of data sourced from absolute address to stack at indicated offset. Convert from RAM little endian to stack big endian ordering ordering. |
| `cpy4as` | absolute address | stack offset | Copy 4 bytes of data sourced from indicated stack offset to memory starting at indicated absolute address. Convert from stack big endian ordering to RAM little endian ordering. |
| `cpy4sa` | stack offset | absolute address | Copy 4 bytes of data sourced from absolute address to stack at indicated offset. Convert from RAM little endian to stack big endian ordering ordering. |
| `cpy4ai` | absolute address | immediate | Copy 4 bytes of immediate value to memory starting at indicated absolute address. Preserves endian ordering. |
| `cpy4si` | stack offset | immediate | Copy 4 bytes of immediate value to stack at indicated offset. Convert from RAM little endian to stack big endian ordering ordering. |
| `cpy4ss` | stack offset | stack offset | Copy 4 bytes of data from stack starting at indicated offset (2nd operand) to another location in stack starting at indicated offset (1rst operand). Byte ordering is preserved. |

The operand descriptions use the definitions provided by documentation for Minimal CPU.

One important note here is that the calling convention that was designed for the Minimal CPU places multibyte values in the stack using big endian, and values stored in RAM are in little endian. This was defined in the way the operating system API functions are called. The above macros account for this endian difference when moving data from RAM to the stack and vice versa.

### Assembly Syntax
**BespokeASM**'s syntax is close to the syntax that Carsten used for the Minimal CPU's assembly language. However, there are some differences:

* **BespokeASM** used a different syntax for some directives, notably the `.org` directive, which has the `#org` syntax in the Minimal CPU assembly. **BespokeASM** also has [a richer set of directives available](https://github.com/michaelkamprath/bespokeasm/wiki/Assembly-Language-Syntax#directives).
* The Minimal CPU's assembler has no data type directives. Instead, the assembler directly converts numeric values and strings to byte code exactly where it sits in the code. In **BespokeASM** one must declare a data type using [a data directive](https://github.com/michaelkamprath/bespokeasm/wiki/Assembly-Language-Syntax#data) when defining data in the byte code.
* The Minimal CPU assembler emits byte code in the order it was in the original assembly code, while **BespokeASM** emits byte code in address order. For the most part, these two orderings can be pretty much the same, however, differences will show up if multiple `.org` directives are use or multiple additional source files are included.
* The Minimal CPU uses a `<` and `>` to do byte slicing of constant values, with `<` meaning least significant byte and `>` meaning most significant byte. **BespokeASM** using `BYTE0(..)` and `BYTE1(..)` [to accomplish the same goals](https://github.com/michaelkamprath/bespokeasm/wiki/Assembly-Language-Syntax#numeric-expressions) (respectively).

There are several other features that **BespokeASM** provides over the Minimal CPU assembly syntax such as math expressions for constant values, but the differences listed above are the ones that require code written for the Minimal CPU assembler to be altered to be assembled with **BespokeASM**.

### Predefined Compiler Constants
The standard operating system provided call vectors for a suite of API functions and system subroutines that are made available to user written programs. These API function labels are documented in the "API Functions" section of the Minimal CPU user guide. All documented API functions are implemented as predefined constants in this **BepsokeASM** port.

However, there is one important change. In the Minimal CPU documentation, all API function labels begin with an underscore `_`. However, in **BespokeASM**, labels that begin with an underscore are limited to [the defining file scope](https://github.com/michaelkamprath/bespokeasm/wiki/Assembly-Language-Syntax#label-scope). So, the API function labels defined to start with an `os_` instead. Other than this small naming difference, all API function labels can be used as described in the Minimal CPU user documentation.

## Compiling Minimal CPU Assembly with BespokeASM
Assuming the assembly code being provided to **BespokeASM** accounts for the syntax differences described above and [**BespokeASM** is properly installed](https://github.com/michaelkamprath/bespokeasm/wiki/Installation-and-Usage), the assembly code can be compiled with the following command:

```sh
bespokeasm compile -c path/to/slu5-minimal-cpu.yaml -p -t minhex --no-binary path/to/source.min-asm
```

Where each option means:

* `-c path/to/slu5-minimal-cpu.yaml` - Provides the path to the ISA configuration that defines the instruction set to be used when assembling. The Minimal CPU ISA configuration file [is provided here](./slu4-minimal-cpu.yaml).
* `-p` - Tells **BespokeASM** to pretty print the results to a human usable format.
* `-t minhex` - Configured the format of the pretty printing. In this case, the `minhex` format is the same as the format that the Minimal CPU assembler emits, and can be directly copy/pasted into a terminal session with the Minimal CPU for uploading.
* `--no-binary` - Tells **BespokeASM** to not emit a binary file containing the byte code. For the most part, the Minimal CPU does not use binary files in its day-to-day usage.
* `path/to/source.min-asm` - The assembly source file to compile. By convention for **BespokeASM**, Minimal CPU assembly files have the extension of `*.min-cpu`. The only impact of this file extension is to signal to various editors what [syntax highlighting to be used](https://github.com/michaelkamprath/bespokeasm/wiki/Installation-and-Usage#installing-language-extensions). 