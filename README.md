[![Python package](https://github.com/michaelkamprath/bespokeasm/actions/workflows/python-package.yml/badge.svg?branch=main)](https://github.com/michaelkamprath/bespokeasm/actions/workflows/python-package.yml) [![Stand With Ukraine](https://raw.githubusercontent.com/vshymanskyy/StandWithUkraine/main/badges/StandWithUkraine.svg)](https://stand-with-ukraine.pp.ua)

# Bespoke ASM
This is a customizable byte code assembler that allows for the definition of custom instruction set architecture.

**NOTE - This project should be considered to be in "beta" status. It should be stable, but features are subject to change.**

## Usage
To install, clone this repository and install using `pip`.

```sh
git clone git@github.com:michaelkamprath/bespokeasm.git
pip install ./bespokeasm/
```

Preferably, you use a `python` virtual environment to install BespokeASM into. For example:

```sh
git clone git@github.com:michaelkamprath/bespokeasm.git
cd bespokeasm
python3 -m venv .venv/bespokeasm
source .venv/bespokeasm/bin/activate
pip install .
bespokeasm —version
```

Once installed, assembly code can be compiled in this manner:

```sh
 bespokeasm compile -c isa-config.yaml awesome-code.asm
```

Note that supplying an instruction set configuration file is required via the `-c` option. The binary byte code image will be written to `<asm-file-basename>.bin`, though this can be changed with the `-o` option. Add `--pretty-print` to the command to get a human readable output.

### Installing Syntax Highlighting
#### Visual Studio Code
BespokeASM can generate a syntax highlighting extension for [Visual Studio Code](https://code.visualstudio.com) that will properly highlight the instruction mnemonics and other aspects of the assembly language configured in the instruction set architecture configuration file. To install:
```sh
bespokeasm generate-extension vscode -c isa-config.yaml
```
#### Sublime Text
BespokeASM can generate a syntax highlighting extension for [Sublime Text](https://www.sublimetext.com) that will properly highlight the instruction mnemonics and other aspects of the assembly language configured in the instruction set architecture configuration file. To generate the `.sublime-package` file:
```sh
bespokeasm generate-extension sublime -c isa-config.yaml -d /path/to/some/directory
```
Once generated, move the `.sublime-package` file to the `Installed Packages` directory of the Sublime Text application settings directory. On MacOS, this can be found at `~/Library/Application Support/Sublime Text/Installed Packages`, and on Linux this is typically found at `~/.config/sublime-text/Installed\ Packages/`. Of course, this directory can also be used for the `-d` option in the above command.

#### Vim
BespokeASM can generate Vim syntax highlighting and filetype detection files based on your ISA configuration. To generate:
```sh
bespokeasm generate-extension vim -c isa-config.yaml [-d ~/.vim/]
```
This creates `syntax/<language-id>.vim` and `ftdetect/<language-id>.vim` under the specified directory (default `~/.vim/`). For Neovim, you can use `~/.config/nvim/` instead.

See [documentation for more information](https://github.com/michaelkamprath/bespokeasm/wiki/Installation-and-Usage#vim) on how to configure Vim to use the generated files.

# Documentation
Documentation is available on the [Bespoke ASM Wiki](https://github.com/michaelkamprath/bespokeasm/wiki).

# Contributions
Contributions are welcome. All contributions should pass the configured linters. A `pre-commit` hook can be configured to lint all code at commit time. The configuration can be found in the `.pre-commit-config.yaml` file in this repository. To install:

```sh
cd /path/to/bespokeasm/repository
pipenv sync --dev
pre-commit install
```

# License
Bespoke ASM is released under [the GNU GPL v3 license](./LICENSE).
