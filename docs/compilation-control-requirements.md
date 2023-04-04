# Compilation Control


## Symbol Definition

### In-Code Symbol Definition
`#define <symbol-name> <replacement-value>`

* A symbol has two attributes: the fact it has been defined and what its replacement value is.
* A symbol name is case sensitive, alphanumeric plus `_`, and must not have spaces in it

### Predefined Symbols

### Compile Command Symbol Definition

## Compilation Control Blocks


### Symbol Status Bolean
`#ifdef <symbol-name>`

### Symbol Replacement Value Comparison
`#if <symbol-name> <comparison-operator> <comparison-value>`

* If both the symbol replacement value and the comparison value can be converted to an integer, they will be and the comparison will be made based on interger values.
* If a symbol is undefined at the time of evaluation, the boolean comparison will alwys evaluate to `false`.

### Else Case
`#else`

### Block Termination
`#endif`

## In-code Symbol Replacement

* If a symbol is undefined at the time a line of code is being evaluated, an error will be generated indicating an undefined symbol in code.
