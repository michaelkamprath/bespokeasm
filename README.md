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
Note that supplying an instruction set configuration file is required via the `-c` option. The nbinary byte code image will be written to `<asm-file-basename>.bin`, though this can be changed with the `-o` option. Add `--pretty-print` to the command to get a human readable output.

# Documentation
Documentation is availabe on the [Bespoke ASM Wiki](https://github.com/michaelkamprath/bespokeasm/wiki).

# License
Bespoke ASM is released under [the GMU GPL v3 license](./LICENSE).
