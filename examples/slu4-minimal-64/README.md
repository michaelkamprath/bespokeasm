# Minimal 64 Home Computer
*Current as of v1.2.x of the Minimal 64 Home Computer*

The Minimal 64 Home Computer (Minimal 64) is TTL CPU designed by Carsten Herting (slu4). Carsten has made his [Minimal 64 design open and available to others](https://github.com/slu4coder/The-Minimal-64-Home-Computer/) to build. The Minimal 64 is is well documented, and even has [a YouTube video series](https://www.youtube.com/watch?v=3zGTsi4AYLw&list=PLYlQj5cfIcBVrKpKJ-Sj68nkw6IRb9KOp) dedicated to it.

As part of his effort to demonstrate the "minimal effort" needed to make a working computer, Cartsen has already implemented a simple yet solid assembler for the Minimal 64 Home Computer. So the question might be asked, "Why port the Minimal 64 to BespokeASM?" Simply put, to have a more robust assembler for the Minimal 64. For example, the instruction set for the Minimal 64 is simple (no overly complex instructions), and so actions like pushing a value on the stack takes at least two instructions to complete. In scenarios like this, BespokeASM's instruction macros can simplify the code needed to accomplish common tasks.

So the goal of this port to **BespokeASM** is to first support the basic instruction set of the Minimal 64 in its original form, but then build on that with richer features such as instruction macros to make assembly coding for the Minimal CPU more productive.

## Minimal 64 Assembly
The **BespokeASM** instruction set configration file `slu4-minimal-64.yaml` is available in this directory. Assuming that **BespookeASM** is [properly installed in the current python environment](https://github.com/michaelkamprath/bespokeasm/wiki/Installation-and-Usage#installation), to compile Minimal 64 assembly into a Intel Hex representation that the Minimal 64 OS's `receive` instruction can take, use the following command:

```sh
bespokeasm compile -n -p -t intel_hex -c /path/to/slu4-minimal-64.yaml /path/to/my-code.min64
```

The arguments to the command above are:

* `-n` - Indicates that no binary image should be generated.
* `-p` - indicates that a textual representation of the assembled code should be emitted.
* `-t intel_hex` - Specifies the format of the textual rerpesentation of the compiled code, in this case being Intel Hex. If you ommit this option, the default textual representation of an human-readable listing will be used.
* `-c /path/to/slu4-minimal-64.yaml` - The file path to the **BespokeASM** instruction set configuration for the Minimal 64.
* `/path/to/my-code.min64` - The file path to the Minimal 64 assembly code to be compiled. Here by convention the assembly code has a file extension of `.min64`. While **BespokeASM** can work with any file extension for the code, the convention is used so that code editors know what file type they are editing and thus are able to support syntax highlighting specific to the Minimal 64 assembly syntax. See **BespokeASM**'s documentation on syntax highlighting support for more information.

### Instruction Set
Carsten Heating thoroughly documents [the instruction set for the Minimal 64 in his user guide](https://docs.google.com/document/d/1e4hL9Z7BLIoUlErWgJOngnSMYLXjfnsZB9BtlwhTC6U/edit?usp=sharing). All of the documented instructions in their original syntax are implemented in in this **BespokeASM** port. However, **BespokeASM** will be case insensitive when matching instruction mnemonics.

### Instruction Macros
The following instruction macros have been added in the ISA confutation file for the Minimal 64. All macros that interact with the stack maintain byte order according to Min64 OS calling convention, which pushes the LSB of the value first despite the system otherwise using little endian byte ordering. Not that this means multibyte values on the stack cannot be used directly art their stack memory address and must be "pulled" from the stack to another memory location where they can be represented in little endian byte ordering.

| Macros Instruction | Operand 1 | Operand 2 | Description |
|:-:|:-:|:-:|:--|
| `spinit` | - | - | Init the stack popint to a value of `0xFFFE`. Modifies A register. |
| `phs2` | 2 bytes | - | Pushes a 2 byte value onto the stack. . |
| `pls2` | - | - | Pull 2 bytes from stack. Last byte pulled will be in A register. |


### Assembly Syntax
**BespokeASM**'s syntax is close to the syntax that Carsten used for the Minimal CPU's assembly language. However, there are some differences:

* **BespokeASM** used a different syntax for some directives, notably the `.org` directive, which has the `#org` syntax in the Minimal CPU assembly. **BespokeASM** also has [a richer set of directives available](https://github.com/michaelkamprath/bespokeasm/wiki/Assembly-Language-Syntax#directives).
* The Minimal CPU's assembler has no data type directives. Instead, the assembler directly converts numeric values and strings to byte code exactly where it sits in the code. In **BespokeASM** one must declare a data type using [a data directive](https://github.com/michaelkamprath/bespokeasm/wiki/Assembly-Language-Syntax#data) when defining data in the byte code.
* The Minimal CPU assembler emits byte code in the order it was in the original assembly code, while **BespokeASM** emits byte code in address order. For the most part, these two orderings can be pretty much the same, however, differences will show up if multiple `.org` directives are use or multiple additional source files are included.
* The Minimal CPU uses a `<` and `>` to do byte slicing of constant values, with `<` meaning least significant byte and `>` meaning most significant byte. **BespokeASM** using `BYTE0(..)` and `BYTE1(..)` [to accomplish the same goals](https://github.com/michaelkamprath/bespokeasm/wiki/Assembly-Language-Syntax#numeric-expressions) (respectively).

There are several other features that **BespokeASM** provides over the Minimal CPU assembly syntax such as math expressions for constant values, but the differences listed above are the ones that require code written for the Minimal CPU assembler to be altered to be assembled with **BespokeASM**.

### Predefined Compiler Constants
The Minimal 64 operating system provided call vectors for a suite of API functions and system subroutines that are made available to user written programs. These API function labels are documented in the "API Functions" section of the Minimal 64 user guide. All documented API functions are implemented as predefined constants in this **BepsokeASM** port.
