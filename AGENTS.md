# BespokeASM
**BespokeASM** is a customizable byte code assembler that allows for the definition of custom instruction set architectures (ISA). It was originally designed to enable the easy assembly of byte code for a custom-made TTL CPU with an evolving instruction set architecture (ISA). Given that, it was advantageous to make the ISA configurable so that updates can easily be made. The project is written in Python 3.11+ and follows a modular architecture.

## Quickstart

Requires Python 3.11+ and a virtual environment. From the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install .
mkdir -p build
bespokeasm -c examples/slu4-minimal-cpu/slu4-minimal-cpu.yaml examples/slu4-minimal-cpu/hello.min-asm -n -p
```
This will compile the `hello.min-asm` file into a pretty printed listing of the bytecode and not emit a binary file.

## Key Wiki Pages
The most recent version of documentation can be found at the [BespokeASM Wiki](https://github.com/michaelkamprath/bespokeasm/wiki).

- [Installation and Usage](https://github.com/michaelkamprath/bespokeasm/wiki/Installation-and-Usage)
- [Assembly Language Syntax](https://github.com/michaelkamprath/bespokeasm/wiki/Assembly-Language-Syntax)
- [Instruction Set Configuration File](https://github.com/michaelkamprath/bespokeasm/wiki/Instruction-Set-Configuration-File)

## General Architecture
**BespokeASM** is organized into the following modules:

- `bespokeasm`: The main module containing the CLI and entry point.
- `bespokeasm.assembler`: The core assembly engine.
- `bespokeasm.assembler.model`: Responsible for loading the ISA configuration file and then creating the parsers to convert assembly language source code into structured objects representing instructions, directives, labels, etc.
- `bespokeasm.assembler.label_scope`: Responsible for managing the visibility of labels, constants, and other symbols across code files and their lines of code.
- `bespokeasm.assembler.line_object`: Represents a parsed source code line of a specific type.
- `bespokeasm.assembler.bytecode`: Converts parsed source code line objects to bytecode.
- `bespokeasm.assembler.memory_zone`: Manages memory zones and address allocation.
- `bespokeasm.assembler.preprocessor`: Implements various preprocessor functionality such as including files, conditional compilation, and version control.
- `bespokeasm.configgen`: Generates syntax highlighting and other functionality for VS Code, Sublime Text, and Vim.
- `bespokeasm.expression`: Handles mathematical expressions and symbol resolution.

### Key Patterns

- **Multi-pass Assembly**: The assembler uses multiple passes to resolve forward references and optimize bytecode
- **ISA Configuration**: Assembly behavior is driven by YAML or JSON configuration files that define the instruction set
- **Operand Types**: Extensible operand type system supporting registers, immediate values, addresses, relative addresses, etc.
- **Memory Zones**: Flexible memory management allowing code to be placed in specific memory regions
- **Conditional Assembly**: Preprocessor directives for conditional compilation

### Assembly Flow Snapshot
- CLI (`src/bespokeasm/__main__.py`) invokes the `Assembler`, which performs a two-pass build (address assignment, then byte emission) driven by the ISA model.
- `AssemblyFile` and `LineObjectFactory` parse source lines (honoring `#include` and conditionals) into typed line objects; instruction lines delegate to `InstructionLine` and the `BytecodeGenerator` to produce `Word` values.
- Configured pretty-printer implementations can emit listing/intel-hex outputs alongside binaries.

### Configuration Features
- ISA configs seed predefined constants, data blocks, memory zones, and preprocessor symbols; these are injected into global label scope before compilation.

### Entry Point
- Main entry: `src/bespokeasm/__main__.py` (builds the CLI via `src/bespokeasm/cli.py` and lazy-imported handlers)
- Completion entry: `src/bespokeasm/completion_cli.py` (used when `_is_completion_invocation()` is set for fast shell completion)
- Primary commands: `compile`, `docs`, `generate-extension`, `install-completion` (with `vscode`, `sublime`, `vim` under `generate-extension`)
- Backward-compat: if no subcommand is provided, `compile` is injected
- CLI implementation uses [Click](https://click.palletsprojects.com/en/stable/) (`click`) for command parsing and shell completion support

### Versioning
When updating the release version, the version numbers in the following files should be updated:
- `src/bespokeasm/__init__.py`
- `pyproject.toml`

Furthermore, the `CHANGELOG.md` file should be updated to reflect the changes made.

Release checklist:
- Update versions in `src/bespokeasm/__init__.py` and `pyproject.toml`
- Update `CHANGELOG.md`
- Run tests: `pytest -q`
- Run `pre-commit run --all-files` and fix any issues
- Tag the release and push

## Development Rules

### Use Virtual Environment
- Use the Python virtual environment at project root: `.venv`, If this does not exist, create it with `python3 -m venv .venv` from the root of the project.
- Activate with: `source .venv/bin/activate` (Linux/macOS) or `.venv\Scripts\activate` (Windows)
- If the virtual environment is new, install the dependencies with `pip install -r requirements.txt` from the root of the project.
- IMPORTANT: The virtual environment is used for all development activities. Always activate the virtual environment before running any development commands.

### Project Coding Best Practices
- Keep shell completion paths lightweight by avoiding heavy imports at CLI import time; route completion invocations to `completion_cli.entry_point()` and lazily import heavy modules inside command handlers.
- If helpers move between modules, update tests to import from the new module rather than re-exporting unused symbols just for tests.
- Always run `pre-commit run --all-files` and `pytest -q` after changes to properly lint and test the code. Ensure the Python virtual environment is active before running them.
