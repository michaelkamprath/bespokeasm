# Bespoke ASM
This is a customizable byte code assembler that allows for the definition of custom instruction set architecture. 

**NOTE - This is very much a work in progress**

## Usage
To install, clone this repository and install using `pip`. Preferably, you have a `python` virtual environment set up when you do this.
```
git clone git@github.com:michaelkamprath/bespokeasm.git
pip install ./bespokeasm/
```
Once installed, assembly code can be compiled in this manner:
```
 bespokeasm compile -c isa-config.json awesome-code.asm
```
Note that supplying a instruction set configuration is required via the `-c`/`--config-file` option.

# Documentation
## Assembler Syntax
* Each line pertains to at most one instruction or label
* Whitespace is generally ignored except for the minimal amount required to seperate parts of an instruction.
* Any characters after and including a semicolon `;` on any given line are consider to be comments

### Numeric Values
Anytime a numeric values is to be expressed, whether it be a immediate value or a memory address, it can be written in decimal, hex, or binary form  as shown here:
| Type | Syntax |
|:--|--:|
| Decimal | 124 |
| Hex | $7C |
| Hex | 0x7C |
| Binary | b01111100 |

## Assembly Syntax

### Instruction
And instruction has the format of:

```
INSTRUCTION [ARG1[,ARG2[...]]]
```

#### Instruction Arguments
* Instruction arguments are seperated by a comma
* Instruction arguments may be either a label, a constant, or a numeric value

### Label
A label represents a specific address in the byte sequence being assembled. A label does not have a size or sequence of bytes pertaining to it. A label's value is implied by its relative location among the lines to be assembled.

A label is represented by any alphanumeric character string the immediately precedes a colon `:`. There will be only one label allowed per line.

All labels must be distinct.

### Constant
A constant is a label that has an explicitely assigned value.

```
constant_var = 10204
```

### Data
TBC

## Instruction Set Architecture Definition Syntax
The Instruction Set Architecture (ISA) defintion is provided in JSON format.