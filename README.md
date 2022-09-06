[![Python package](https://github.com/michaelkamprath/bespokeasm/actions/workflows/python-package.yml/badge.svg?branch=main)](https://github.com/michaelkamprath/bespokeasm/actions/workflows/python-package.yml)

# Bespoke ASM
This is a customizable byte code assembler that allows for the definition of custom instruction set architecture.

**NOTE - This is very much a work in progress**

## Usage
To install, clone this repository and install using `pip`. Preferably, you have a `python` virtual environment set up and it has `pipenv` installed when you do this.

```sh
git clone git@github.com:michaelkamprath/bespokeasm.git
cd bespokeasm
pipenv install
pip install .
```

Once installed, assembly code can be compiled in this manner:

```sh
 bespokeasm compile -c isa-config.yaml awesome-code.asm
```

Note that supplying an instruction set configuration file is required via the `-c` option. The binary byte code image will be written to `<asm-file-basename>.bin`, though this can be changed with the `-o` option. Add `--pretty-print` to the command to get a human readable output.

### Installing Systax Highlighting
#### Visual Studio Code
BespokeASM can generate a syntax highlighting extension for [Visual Studio Code](https://code.visualstudio.com) that will properly highlight the instruction mnemonics and other aspects of the assembly language configured in the instruction set architecture configuration file. To install:
```sh
bespokeasm generate-extension vscode -c isa-config.yaml
```
#### Sublime Text
BespokeASM can generate a syntax highlighting extension for [Sublime Text](https://www.sublimetext.com) that will properly highlight the instruction mnemonics and other aspects of the assembly language configured in the instruction set architecture configuration file. To generate the `.sublime-package` file:
```sh
bespokeasm generate-extension vscode -c isa-config.yaml -d /path/to/some/directory
```
Once generated, move the `.sublime-package` file to the `Installed Packages` directory of the Sublime Text application settings directory. On MacOS, this can be found at `~/Library/Application Support/Sublime Text/Installed Packages`. Of course, this directory can also be used for the `-d` option in the above command.

# Documentation
Documentation is available on the [Bespoke ASM Wiki](https://github.com/michaelkamprath/bespokeasm/wiki).

# Contributions
Contributions are welcome. All contributions should pass the configured linters. A `pre-commit` hook can be configured to lint all code at commit time. The configuration can be found in the `.pre-commit-config.yaml` file in this repository. To install:

```sh
cd /path/to/bespokeasm/repository
pipenv install
pre-commit install
```

# License
Bespoke ASM is released under [the GNU GPL v3 license](./LICENSE).
