# Bespoke ASM
This is a customizable byte code assembler that allows for the definition of custom instruction set architecture.

**NOTE - This is very much a work in progress**

## Usage
To install, clone this repository and install using `pip`. Preferably, you have a `python` virtual environment set up when you do this.

```sh
git clone git@github.com:michaelkamprath/bespokeasm.git
pip install ./bespokeasm/
```

Once installed, assembly code can be compiled in this manner:

```sh
 bespokeasm compile -c isa-config.yaml awesome-code.asm
```

Note that supplying an instruction set configuration file is required via the `-c` option. The binary byte code image will be written to `<asm-file-basename>.bin`, though this can be changed with the `-o` option. Add `--pretty-print` to the command to get a human readable output.

### Installing Systax Highlighting
BespokeASM can generate a sytax highlighting extension for [Visual Studio Code](https://code.visualstudio.com) that will properly highlight the instruction mnomics and other aspects of the assembly language configured in the instruction set architecture configuration file. To install:
```sh
bespokeasm generate-extension vscode -c isa-config.yaml
```

# Documentation
Documentation is availabe on the [Bespoke ASM Wiki](https://github.com/michaelkamprath/bespokeasm/wiki).

# License
Bespoke ASM is released under [the GNU GPL v3 license](./LICENSE).
