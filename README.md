


## General Syntax
* Each line pertains to at most one instruction or label
* Whitespace is generally ignored except for the minimal amount required to seperat parts of an instruction.
* Any characters after and including a semicolon `;` on any given line are consider to be comments
* White space is generally i

### Numeric Values
Anytime a numeric values is to be expressed, whther it be a immediate value or amemory address, it can be written in decimal, hex, or binary form  as shown here:
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
INSTRUCTION [ARG1[,ARG2]]
```

#### Instruction Arguments


### Label
A label represents a specific address in the byte sequence being assembled. A label does not have a size or sequence of bytes pertaining to it. A label's value is implied by its relative location among the lines to be assembled.

A label is represented by any alphanumeric character string the immediately precedes a colon `:`. There will be only one label allowed per line.

### Constant

```
constant_var = 10204
```

### Data

## Instruction Set Definition Syntax