[![Python package](https://github.com/michaelkamprath/bespokeasm/actions/workflows/python-package.yml/badge.svg?branch=main)](https://github.com/michaelkamprath/bespokeasm/actions/workflows/python-package.yml) [![Stand With Ukraine](https://raw.githubusercontent.com/vshymanskyy/StandWithUkraine/main/badges/StandWithUkraine.svg)](https://stand-with-ukraine.pp.ua)

# Bespoke ASM
This is a customizable byte code assembler that allows for the definition of custom instruction set architecture.

**NOTE - This project should be considered to be in "beta" status. It should be stable, but features are subject to change.**

## Usage
Once installed, assembly code can be compiled in this manner:

```sh
 bespokeasm compile -c isa-config.yaml awesome-code.asm
```

Note that supplying an instruction set configuration file is required via the `-c` option. The binary byte code image will be written to `<asm-file-basename>.bin`, though this can be changed with the `-o` option. Add `--pretty-print` to the command to get a human readable output.

### Installation Options

#### Recommended: pipx install

[`pipx`](https://pipx.pypa.io/) installs BespokeASM into its own isolated environment and makes the `bespokeasm` command available globally -- no virtual environment management needed. This is the fastest and most convenient way to install.

**Prerequisite:** Python 3.11+ and `pipx`. If you don’t have `pipx`: `python3 -m pip install --user pipx && python3 -m pipx ensurepath` (restart your shell).

Install directly from the GitHub repository:

```sh
pipx install git+https://github.com/michaelkamprath/bespokeasm.git
```

Or install from a wheel attached to a [GitHub Release](https://github.com/michaelkamprath/bespokeasm/releases):

```sh
pipx install ./bespokeasm-<version>-py3-none-any.whl
```

After installing, enable shell tab completions for the best experience:

```sh
bespokeasm install-completion
```

To upgrade: `pipx upgrade bespokeasm` (or `pipx install --force` with a new wheel). To remove: `pipx uninstall bespokeasm`.

#### Standalone binary (no Python required)

If you don’t have Python installed, download a standalone binary from the [GitHub Releases](https://github.com/michaelkamprath/bespokeasm/releases) page (e.g., `bespokeasm-<version>-linux-x86_64`, `bespokeasm-<version>-macos-arm64`, `bespokeasm-<version>-macos-x86_64`, or `bespokeasm-<version>-windows-x86_64.exe`).

- On Linux/macOS, make it executable: `chmod +x bespokeasm-*`.
- To place it on your PATH, rename or symlink to `bespokeasm` in a PATH directory (e.g., `ln -sf /path/to/bespokeasm-macos-x86_64 /usr/local/bin/bespokeasm`).
- On Windows, rename to `bespokeasm.exe` and place in a folder on your PATH.
- To upgrade, download the new binary and replace the old one.

Note: the standalone binary has a slightly slower startup than a `pipx` install due to its self-contained packaging.

#### Install from source

Install [uv](https://docs.astral.sh/uv/getting-started/installation/) (on macOS: `brew install uv`), then:

```sh
git clone https://github.com/michaelkamprath/bespokeasm.git
cd bespokeasm
uv tool install .
```

This installs BespokeASM into an isolated tool environment and makes `bespokeasm` available from any directory without activating a virtual environment. If uv reports that its executable directory is missing from your PATH, run `uv tool update-shell` and restart your shell.

```sh
bespokeasm --help
bespokeasm install-completion
```

After updating the checkout, reinstall with `uv tool install --force .` from the repository root. To remove the installation, run `uv tool uninstall bespokeasm`.

#### Development setup

From the repository root, synchronize the development environment:

```sh
uv sync --locked
uv run --locked bespokeasm --help
```

uv manages `.venv` and installs the project in editable mode together with the default `dev` dependency group, including test, lint, and packaging tools. Run project commands through `uv run`; no manual environment activation is needed.

To also make the CLI available from any directory while developing, run this from the repository root:

```sh
uv tool install --editable .
```

This creates a separate tool environment whose `bespokeasm` command reflects source edits without reinstalling. Keep the checkout at its original location, and use `uv tool update-shell` if uv reports that its executable directory is missing from PATH. If you previously installed BespokeASM as a non-editable uv tool, use `uv tool install --force --editable .` to replace it. Continue using `uv sync --locked` and `uv run --locked` for tests, linters, and builds in the project environment.

Dependencies are declared in `pyproject.toml` and locked in the committed `uv.lock`. Add runtime dependencies with `uv add <package>` and development tools with `uv add --dev <package>`. After manually changing dependencies or the project version, run `uv lock` and commit both files. To deliberately upgrade locked dependencies, run `uv lock --upgrade`, then `uv sync --locked` and the checks below.

The Makefile also uses uv: `make tests`, `make coverage`, `make flake8`, `make pipx-wheel`, `make pyinstaller`, and `make nuitka`. Standalone builds additionally require host tools such as ripgrep (PyInstaller) or a C compiler (Nuitka).

### Installing Syntax Highlighting
#### Visual Studio Code
BespokeASM can generate a syntax highlighting extension for [Visual Studio Code](https://code.visualstudio.com) that will properly highlight the instruction mnemonics and other aspects of the assembly language configured in the instruction set architecture configuration file. To install:
```sh
bespokeasm generate-extension vscode -c isa-config.yaml
```

For [Cursor](https://cursor.com/), add the `-d ~/.cursor/` options.
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
uv sync --locked
uv run --locked pre-commit install
```

Before submitting changes, run:

```sh
uv run --locked pre-commit run --all-files
uv run --locked pytest -q
```

# License
Bespoke ASM is released under [the GNU GPL v3 license](./LICENSE).
