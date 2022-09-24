# MOSTEK 3870 Assembly

This configuration for **BespokeASM** creates a full featured assembler for [the MOSTEK 3870 vintage microcontroller](https://www.cpu-world.com/CPUs/3870/index.html). Theoretically, this should also support the F8 family of CPUs in general, however that has not been tested. This implementation of an assembler for the MOSTEK 3870 uses all the same mnemonics as described in [the original MOSTEK 3870 documentation](./documentation/mostek3870_instructions.pdf), however the rest of the assembly language syntax is defined by **BespokeASM**'s documentation.


## Examples
Examples programs that use the MOSTEK 3870 instruction set can be found in [this directory](./).

### MOSTEK 38P70 Computer
A reference computer has been designed based on the MOSTEK 38P70 programmable microcontroller, and can be found in [this repository](https://github.com/michaelkamprath/mostek-38p70-computer).

## Compiling Code
To compile code for the MOSTEK 3870 family of microprocessors (and possibly other F8-based CPUs), follow the BespokeASM instructions using the `mostek-3870.yaml` BespokeASM configuration file found in this directory. Note that this configuration file defines the file extension for MOSTEK 3870 assembly code to be `.af8`. The typical compilation command will look like:

```sh
bespokeasm compile -e 2047 -p -c mostek-3870.yaml my_code.af8
```

### Syntax Highlighting
BespokeASM has the ability to generate for various popular text editors a syntax highlighting language extension specific to the MOSTEK 3870 F8-based instruction set. [See the documentation](https://github.com/michaelkamprath/bespokeasm/wiki/Installation-and-Usage#installing-language-extensions) for information for on how to install and use the language extensions.
