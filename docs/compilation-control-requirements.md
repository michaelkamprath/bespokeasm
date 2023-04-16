# Compilation Control

## Symbol Definition

### In-Code Symbol Definition
`#define <symbol-name> <replacement-value>`

* A symbol has two attributes: the fact it has been defined and what its replacement value is.
* A symbol name is case sensitive, alphanumeric plus `_`, and must not have spaces in it
* The replacement value is all text after the first white space after the symbol name up to either the end of line or a comment start symbol (`;`), which ever comes first. This text will get trimmed of bounding whitespace. The reaplement value may be a zero-length string.
* The replacement value will be lazily evaluated.
* A symbol is in the global scope at the moment it gets defined (when it's line of code is processed) and may be used from that point forward.
* When a defined symbol is present in a line of note (not any preprocessor directive), before that line of code is compiled the symbol with be replaced with its replacement value string.

### Predefined Symbols
Symbols can be predefined in the instruction set configuration YAML file in the `predefined` section. It will be a list of dictionaires under the `symbols` key, and each listry entry will name at a minimum a `name` key with a value of the symbol name. An optional `value` key will have a value of the replacement value for the symbol. If `value` is not present, the replacement value will be a zero-length string.

All predefined symbols will be defined when code compilation starts.

### Compile Command Symbol Definition
The BespokeASM command line `compile` compand with be able to take zero or more of the `-D` option to define symbols at compile time. The value of this option may be either `<symbol-name>` or `<symbol-name>=<reaplcement-value>`.

### Multiple Symbol Definitions
A symbol may only be defined once. If a symbol is defined more than once, an error will be generated.

## Compilation Control Blocks
Contiguous lines of code may be conditionally compiled based on the value of a symbol. The symbol may be defined in the code, in the instruction set configuration YAML file, or on the command line. The symbol may be used in a comparison with another symbol or a numeric value. The contiguous lines of code are bounded by a `#if` and `#endif` directive. The `#if` directive may be followed by an `#else` directive, which will be followed by a `#endif` directive. The `#else` directive is optional. The lines of code between the `#if` and `#else` directives will be compiled if the boolean comparison is true. The lines of code between the `#else` and `#endif` directives will be compiled if the boolean comparison is false. If there is no `#else` directive, the lines of code between the `#if` and `#endif` directives will be compiled if the boolean comparison is true. The `#ifdef` and `#ifndef` directives are an alternative to the `#if` directive that will only compile the lines of code if the symbol is defined.

### Symbol Status Bolean
`#ifdef <symbol-name>`

When a `#ifdef` directive is encountered, the symbol will be checked for a defined status. If the symbol is defined, the lines of code between the `#ifdef` and `#endif` directives will be compiled. If the symbol is not defined, the lines of code between the `#ifdef` and `#endif` directives will not be compiled.

### Symbol Value Comparison
`#if <symbol-expression> [<comparison-operator> <symbol-expression>]`

* A symbol expression is any combination of preprocessor symbols, numeric values, and mathemtical operators.
* The comparison operator and right side symbol expression is optional. If not present, the comparison operator and right side symbol expression is assumed to be `!= 0`
* If both symbol expressions value and the comparison value can be converted to an integer, they will be and the comparison will be made based on theirinterger values.
* If a symbol used in the symbol expression is undefined at the time of evaluation, the boolean comparison will always evaluate to `false`. If a label or constant used in the symbol expression, an error will be generated.
* The comparison operator may be one of the following:
  * `==` - equal to
  * `!=` - not equal to
  * `>` - greater than
  * `<` - less than
  * `>=` - greater than or equal to
  * `<=` - less than or equal to
* If the boolean comparison is true, the lines of code between the `#if` and `#else` directives will be compiled, and the lines of code between the `#else` and `#endif` directives will not be compiled. If the boolean comparison is false, the lines of code between the `#else` and `#endif` directives will be compiled, and the lines of code between the `#if` and `#else` directives will not be compiled. Tf there is no `#else` directive, the lines of code between the `#if` and `#endif` directives will be compiled if the comparison is true.
* The `#if` directive may be followed by an `#else` directive, which will be followed by a `#endif` directive. The `#else` directive is optional.
* `#if` directives may be nested. The outer most `#if` directive will be evaluated first, and the inner most `#if` directive will be evaluated last. If an `#if` block is contained within another `#if` block, the inner `#if` block will be evaluated if the outer `#if` block is compiled. If the outer `#if` block is not compiled, the inner `#if` block will not be evaluted.
* The `#if` directive may be followed by an `#elif` directive, which will be followed by another `#elif`, an `#else`, or an `#endif` directive. The `#elif` directive is shorthand for embedded another `#if` directive in the current `#if` block. The `#elif` directive is optional. In an `#if` / `#elif` / `#else` / `#endif` block, there can be only one `#if` at the start, and only zero or one `#else` at the end. There can be zero or more `#elif` directives in between the `#if` and `#else` directives. In an `#if` / `#elif` / `#else` / `#endif` block, only one of the `#if`, `#elif`, and `#else` directives will be compiled.

## In-code Symbol Replacement

* If a symbol is used in the code, it will be replaced with its replacement value string before the line of code is compiled.
* If a symbol is undefined at the time a line of code is being evaluated, an error will be generated indicating an undefined symbol in code.
