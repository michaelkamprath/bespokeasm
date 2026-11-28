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

### Flow Counters
The ISA configuration declares a `stack` [flow counter](https://github.com/michaelkamprath/bespokeasm/wiki/Instruction-Set-Configuration-File#flow-counters) class that lets **BespokeASM** track MinOS hardware stack depth at assembly time. Code that opts in with `#track stack ...` gets push/pull balance checking on every execution path, and can name stack slots with `.name := COORDINATE(stack, N)` so that a bare `.name` reference always resolves to the slot's current `sp`-relative offset — inserting or removing a `phs` no longer requires hand-fixing every `lds`/`sds` offset below it. The metadata is analysis-only: it changes no emitted byte code, and existing programs that do not use the feature assemble exactly as before. Because the stack pointer is memory-mapped at `0xffff`, the class also watches writes to that address: every instruction that writes memory through a compile-time absolute-address operand (the direct stores, clears, increments/decrements, read-modify-write forms, and the immediate/memory move families, in both their absolute and zero-page addressings) declares its write-target operand with `flow_write_operands`, so any such write that resolves to `0xffff` — `spinit`, a direct `mib ...,0xffff`, `sdb 0xffff`, `clb 0xffff`, `miw ...,0xffff`, and so on — makes an active stack counter indeterminate and invalidates its prior coordinates; use `#resume stack = <value>` afterward when deliberately reinitializing the stack inside a region. Two deliberate limits: register-indirect/pointer stores (the `**Z`/`**addr` forms, `szp`, and SP-relative `sds`) are not watched — code that rewrites the SP cell through a pointer must bracket it with `#suspend`/`#resume` itself — and matching is exact on the write's start address, so a multi-word write beginning below `0xffff` (e.g. `miw` to `0xfffe`) is not detected.

See [`software/flow-stack-demo.min64x4r`](software/flow-stack-demo.min64x4r) for a small, heavily commented demonstration: a caller that pushes two arguments under a tracked region, and a `#track stack mode=called` subroutine that names its caller-argument coordinates (accounting for the 2-byte return address `jps` pushes at `sp+1..sp+2`), pushes a local so the argument offsets demonstrably shift, and returns through the `rts` balance check.

### Extended Min (xmin) Export
The ISA configuration declares an `xmin` annotation and an `xmin` output format. Source marks each label or constant to export with `#annotate xmin ...` on the line above it, and compiling with `-p -t xmin` writes an [Extended Min (xmin)](https://github.com/michaelkamprath/extended-min) source file: an `asm` block holding the machine code as Intel HEX records, followed by one declaration per exported symbol. An xmin script loads the file with `use` and can then `call` the routine and read or write its variables. A variable is a `char`, `int` or `long`, or an array of one with `count=N`; with `array` instead of `count`, the data sets the count. A string is `type=str` above a `.cstr`: `#annotate xmin kind=var type=str` above `msg: .cstr "hello"` exports `char msg[5]`, because xmin strings carry a length rather than a terminator. `description="..."` writes `#` comment lines above a declaration, such as how to call a routine; `\n` starts a new line. The `XMIN_USER_CODE` (`0x0100`–`0x0FFF`) and `XMIN_USER_CODE_HI` (`0xED80`–`0xEFFF`) memory zones exist only while the `xmin` or `xmin_listing` format is selected. Annotations emit no bytes, so programs that do not use them assemble exactly as before.

See [`software/xmin-addb.min64x4r`](software/xmin-addb.min64x4r) for an 8-bit add routine with its parameter block, compiled with:

```sh
bespokeasm compile -c slu4-minimal-64x4-redux.yaml -n -p -t xmin --pretty-print-output addb.xmin software/xmin-addb.min64x4r
```

To check what was exported, `-p -t xmin_listing` prints the normal listing followed by a table of the exported symbols with their kind, type, address, size and value:

```sh
bespokeasm compile -c slu4-minimal-64x4-redux.yaml -n -p -t xmin_listing software/xmin-addb.min64x4r
```

### Assembly Syntax
**BespokeASM**'s syntax is close to the syntax that Carsten used for the Minimal 64x4's assembly language. However, there are some differences:

* **BespokeASM** used a different syntax for some Minimal 64x4 Redux directives:
  * The `#org` directive, which sets the next byte code address to a specific value, is replicated in **BespokeASM** with the `.org` directive.
  * The `#page` directive, which aligns the next byte code address to a page boundarry, is replicated in **BespokeASM** with the `.align` directive.
  * In general **BespokeASM** also has [a richer set of directives available](https://github.com/michaelkamprath/bespokeasm/wiki/Assembly-Language-Syntax#directives).
* The Minimal 64x4 Redux's assembler has no data type directives. Instead, the assembler directly converts numeric values and strings to byte code exactly where it sits in the code. In **BespokeASM** one must declare a data type using [a data directive](https://github.com/michaelkamprath/bespokeasm/wiki/Assembly-Language-Syntax#data) when defining data in the byte code.
  * Highly related to this is that the Minimal 64x4Redux assembler allows the direct placement of bytes using an "embedded string". That is, a string of characters surrounded by quotes that are not part of an instruction or directive. **BespokeASM** allows something similar with it's [embedded string]() data type. The main difference is that **BespokeASM**'s embedded string feature behaves similar to it's `.cstr` data directive, which means it will automatically appended a terminating character. For the Minimal 64x4 Redux ISA configation, the terminating character has been set to `0`. In the Minimal 64x4 Redux assembler, the terminating character must be explicitly added, and if you review Carsten's code, you will see that he does this where embedded strings are used in conjuction with the `_Print` routine.
* The Minimal 64x4 Redux assembler emits byte code in the order it was in the original assembly code, while **BespokeASM** emits byte code in address order. For the most part, these two orderings can be pretty much the same, however, differences will show up if multiple `.org` directives are use, memory zones are used, or multiple additional source files are included.
* Carsten's `<` and `>`, the low and high byte of everything after them (`<label+1` is the low byte of `label+1`), work the same way in this configuration. `BYTE0(..)` and `BYTE1(..)` [do the same](https://github.com/michaelkamprath/bespokeasm/wiki/Assembly-Language-Syntax#numeric-expressions).
  * It's worth noting that Minimal 64x4 Redux's assembler frequently uses the `<` operator to slice a zero page address to just it's LSB. That is, it converts the word `0x0080` to the byte `0x80`, removing the zero-valued MSB. The Minimal 64x4 Redux ISA configuration for **BespokeASM** is set up to do this LSB byte slicing automatically for zero page addresses operands in instructions that expects a zero page address. For example, in Minimal 64x4 Redux assembly, you might write `STZ <_Xpos` to store the `A` register value in the zero page address defined by the MinOS constant `_Xpos`, which has the value of `0x00C0`. In **BespokeASM** you can write `STZ _Xpos` to accomplish the same thing as the operand to `STZ` is configured to automatically slice the passed address value to just it's LSB, plus it will also ensure that the MSB of the operand value is zero producing an error if it is not thus ensuring you actually passed a zero page address.


There are several other features that **BespokeASM** provides over the Minimal 64x4 Redux assembly syntax, such as richer math expressions for constant values and [several preprocessor directives](https://github.com/michaelkamprath/bespokeasm/wiki/Assembly-Language-Syntax#preprocessor), but the differences listed above are the ones that require code written for the Minimal 64x4 Redux assembler to be altered to be assembled with **BespokeASM**.

### Migrating Carsten Herting's Programs
`bespokeasm migrate` converts programs written for his assembler for Revision 1.4 Redux (`asm.cpp`) to this configuration's syntax:

```sh
bespokeasm migrate -c slu4-minimal-64x4-redux.yaml --from slu4 os.asm -o os.min64x4r
```

The `slu4` dialect puts each directive, run of data and label that shares a line with other statements on a line of its own; gives data its `.byte` or `.2byte` directive, sized the way his assembler sizes it; converts `"a"` character literals and backslashes in strings; writes a string ending in 0 as an embedded string or `.cstr`, so `JPS _Print "Hi", 10, 0` becomes `JPS _Print "Hi\n"`; and turns `#mute #org 0xfc00 #emit`, which assembles what follows for 0xfc00 while storing it where the bytes were going, into [`.phase 0xfc00`](https://github.com/michaelkamprath/bespokeasm/wiki/Assembly-Language-Syntax#phase). `#page` becomes `.align`, and a program that emits bytes before its first `#org` gets the `.org 0x2000` his assembler starts at. All 14 programs in the repository's `Revision 1.4 Redux/Programs/asm` directory, MinOS included, migrate with nothing reported and assemble to the same bytes as his assembler. A label that self-modifying code puts on an instruction's operand becomes an [operand label](https://github.com/michaelkamprath/bespokeasm/wiki/Assembly-Language-Syntax#operand-labels), `LDI @value: 0xff`, and a mnemonic used as a value becomes its opcode, which the command's summary notes.
