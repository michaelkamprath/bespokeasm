import os
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import click
from bespokeasm import BESPOKEASM_VERSION_STR
from bespokeasm.cli_completion import AutoOptionGroup
from bespokeasm.cli_completion import OptionForwardingCommand
from click.shell_completion import get_completion_class


SUPPORTED_COMPLETION_SHELLS = ('bash', 'zsh', 'fish')
VERBOSE_HELP = 'Verbosity of logging (counting flag: -v, -vv, -vvv or --verbose <n>).'


@dataclass(frozen=True)
class CommandHandlers:
    compile: Callable[..., Any]
    docs: Callable[..., Any]
    vscode: Callable[..., Any]
    sublime: Callable[..., Any]
    vim: Callable[..., Any]


def _detect_shell():
    """Infer the user's shell name if possible."""
    shell_path = os.environ.get('SHELL', '')
    if shell_path:
        detected_shell = os.path.basename(shell_path)
        if detected_shell in SUPPORTED_COMPLETION_SHELLS:
            return detected_shell
    if os.environ.get('PSModulePath'):
        return None
    return None


def _default_completion_path(shell: str, prog_name: str) -> Path:
    """Return the default completion file path for the program name and shell."""
    if shell == 'bash':
        return Path(os.path.expanduser('~/.local/share/bash-completion/completions')) / prog_name
    if shell == 'zsh':
        return Path(os.path.expanduser('~/.zfunc')) / f'_{prog_name}'
    if shell == 'fish':
        return Path(os.path.expanduser('~/.config/fish/completions')) / f'{prog_name}.fish'
    raise ValueError(f'Unsupported shell: {shell}')


def _is_completion_invocation():
    """Detect if Click is invoking completion; avoid extra output in that case."""
    return any(name.endswith('_COMPLETE') for name in os.environ.keys())


def _inject_zsh_nosort(script: str) -> str:
    """Ensure zsh completion function preserves provided order and uses stable compadd."""
    lines = script.splitlines()
    injected_compstate = False
    for idx, line in enumerate(lines):
        if line.strip().startswith('local -a completions') and not injected_compstate:
            lines.insert(idx, '    compstate[nosort]=true')
            injected_compstate = True
        if (
            line.strip()
            == 'if [ -n "$completions_with_descriptions" ]; then'
            and idx + 2 < len(lines)
            and '_describe -V unsorted completions_with_descriptions -U' in lines[idx + 1]
        ):
            lines[idx:idx + 3] = [
                '    if [ -n "$completions_with_descriptions" ]; then',
                '        local -a _pretty _order',
                '        typeset -A _grouped _primary',
                '        local _cd _name _help _names',
                '        local -i _maxlen=0',
                '        for _cd in "${completions_with_descriptions[@]}"; do',
                '            _name="${_cd%%:*}"',
                '            _help="${_cd#*:}"',
                '            if [[ -z ${_primary[$_help]} && "$_name" == --* ]]; then',
                '                _primary[$_help]="$_name"',
                '            elif [[ -z ${_primary[$_help]} ]]; then',
                '                _primary[$_help]="$_name"',
                '            fi',
                '            if [[ -n ${_grouped[$_help]} ]]; then',
                '                _grouped[$_help]+=" $_name"',
                '            else',
                '                _grouped[$_help]="$_name"',
                '                _order+=("$_help")',
                '            fi',
                '        done',
                '        for _help in "${_order[@]}"; do',
                '            _names="${_primary[$_help]:-${_grouped[$_help]}}"',
                '            if [ ${#_names} -gt $_maxlen ]; then',
                '                _maxlen=${#_names}',
                '            fi',
                '        done',
                '        for _help in "${_order[@]}"; do',
                '            _names="${_primary[$_help]:-${_grouped[$_help]}}"',
                '            _pretty+=("${_names}:$(printf \'%-*s -- %s\' $_maxlen \\"$_names\\" \\"$_help\\")")',
                '        done',
                '        _describe -V unsorted completions_with_descriptions _pretty -l',
                '        completions=()',
                '        return',
                '    fi',
            ]
        if line.strip() == 'if [ -n "$completions" ]; then':
            lines[idx] = '    if [ -n "$completions" ] && [ -z "$completions_with_descriptions" ]; then'
        if 'compadd -U -V unsorted -a completions' in line:
            existing_block = (
                'if [ -n "$completions" ]; then\n'
                '        compadd -U -V unsorted -a completions\n'
                '    fi'
            )
            replacement_block = (
                'if [ -n "$completions" ] && [ -z "$completions_with_descriptions" ]; then\n'
                '        compadd -1 -U -V unsorted -a completions\n'
                '    fi'
            )
            lines[idx] = line.replace(
                existing_block,
                replacement_block,
            ).replace(
                'compadd -U -V unsorted -a completions',
                'compadd -1 -U -V unsorted -a completions',
            )
    return '\n'.join(lines)


def build_cli(handlers: CommandHandlers) -> click.Group:
    @click.group(cls=AutoOptionGroup)
    @click.version_option(BESPOKEASM_VERSION_STR)
    def main():
        """A Bespoke ISA Assembler"""
        pass

    @main.command(short_help='compile an assembly file into bytecode')
    @click.argument('asm_file', type=click.Path(dir_okay=False, allow_dash=True))
    @click.option(
            '--config-file', '-c', required=True,
            type=click.Path(dir_okay=False, exists=True),
            help='The filepath to the instruction set configuration file,'
        )
    @click.option(
            '--binary/--no-binary', '-b/-n',
            default=True,
            help='Indicates whether a binary image of the compiled bytecode should be generated.'
        )
    @click.option(
            '--output-file', '-o',
            type=click.Path(dir_okay=False),
            help='The filepath to where the binary image will be written. Defaults to '
                 'the input file name with a *.bin extension.'
        )
    @click.option(
            '--binary-min-address', '-s', default=0,
            help='The start address that will be included in the binary output. '
                 'Useful for building ROM images in a given address range. Defaults to 0.'
        )
    @click.option(
            '--binary-max-address', '-e', default=-1,
            help='The maximum address that will be included in the binary output. Useful '
                 'for building ROM images in a given address range. Defaults to address of last generated byte code.'
        )
    @click.option(
            '--binary-fill', '-f', default=0,
            help='The word value that should be used to fill empty addresses when generating binary image of '
                 'a specific size.'
        )
    @click.option(
            '--pretty-print', '-p',
            is_flag=True, default=False,
            help='if present, a pretty print version of the compilation will be produced.'
        )
    @click.option(
            '--pretty-print-format', '-t',
            type=click.Choice(['minhex', 'hex', 'intel_hex', 'listing'], case_sensitive=False),
            default='listing',
            help='The format that should be used when pretty printing.',
    )
    @click.option(
            '--pretty-print-output',  default='stdout',
            type=click.Path(dir_okay=False),
            help='if pretty-print is enabled, this specifies the output file. Defaults to stdout.'
        )
    @click.option('--verbose', '-v', count=True, help=VERBOSE_HELP)
    @click.option(
            '--include-path', '-I', multiple=True, default=[],
            type=click.Path(file_okay=False),
            help='Path to use when searching for included asm files. Multiple paths can be seperately specified.'
        )
    @click.option(
            '--macro-symbol', '-D', multiple=True, default=[],
            help='Predefine name as macro. Assigning name with value may be done with "name=value" syntax. '
                 'Multiple can be seperately specified.'
        )
    @click.option(
            '--warnings-as-errors', '-W',
            is_flag=True,
            default=False,
            help='Treat warnings as errors and stop compilation.'
        )
    def compile(
                asm_file,
                config_file,
                binary,
                output_file,
                binary_min_address,
                binary_max_address,
                binary_fill,
                pretty_print,
                pretty_print_format,
                pretty_print_output,
                verbose,
                include_path,
                macro_symbol,
                warnings_as_errors,
            ):
        return handlers.compile(
            asm_file,
            config_file,
            binary,
            output_file,
            binary_min_address,
            binary_max_address,
            binary_fill,
            pretty_print,
            pretty_print_format,
            pretty_print_output,
            verbose,
            include_path,
            macro_symbol,
            warnings_as_errors,
        )

    @main.command(cls=OptionForwardingCommand, short_help='generate markdown documentation for an ISA')
    @click.option(
        '--config-file', '-c', required=True,
        type=click.Path(dir_okay=False, exists=True),
        help='The filepath to the instruction set configuration file (YAML or JSON).'
    )
    @click.option(
        '--output-file', '-o',
        type=click.Path(dir_okay=False),
        help='The filepath to write the markdown documentation. Defaults to same directory as config file with .md extension.'
    )
    @click.option('--verbose', '-v', count=True, help=VERBOSE_HELP)
    def docs(config_file, output_file, verbose):
        return handlers.docs(config_file, output_file, verbose)

    @main.group(cls=AutoOptionGroup, short_help='generate a language syntax highlighting extension')
    def generate_extension():
        pass

    @generate_extension.command(cls=OptionForwardingCommand, short_help='generate for VisualStudio Code')
    @click.option(
            '--config-file', '-c', required=True,
            type=click.Path(dir_okay=False, exists=True),
            help='The filepath to the instruction set configuration file,'
        )
    @click.option('--verbose', '-v', count=True, help=VERBOSE_HELP)
    @click.option(
            '--editor-config-dir', '-d', default='~/.vscode/',
            type=click.Path(file_okay=False),
            help='The file path the Visual Studo Code configuration directory containing the extensions directory.'
        )
    @click.option(
            '--language-name', '-l',
            help='The name of the language in the Visual Studio Code configuration file. Defaults to value '
                 'provide in instruction set configuration file.'
        )
    @click.option(
            '--language-version', '-k',
            help='The version of the language in the Visual Studio Code configuration file. Defaults to '
                 'value provide in instruction set configuration file.'
        )
    @click.option(
            '--code-extension', '-x',
            help='The file extension for asssembly code files for this language configuraton.'
        )
    def vscode(config_file, verbose, editor_config_dir, language_name, language_version, code_extension):
        return handlers.vscode(config_file, verbose, editor_config_dir, language_name, language_version, code_extension)

    @generate_extension.command(cls=OptionForwardingCommand, short_help='generate for Sublime text editor')
    @click.option(
            '--config-file', '-c', required=True,
            type=click.Path(dir_okay=False, exists=True),
            help='The filepath to the instruction set configuration file,'
        )
    @click.option('--verbose', '-v', count=True, help=VERBOSE_HELP)
    @click.option(
            '--editor-config-dir', '-d', default='~/',
            type=click.Path(file_okay=False),
            help='The directory into which the generated configuration file should be saved.'
        )
    @click.option(
            '--language-name', '-l',
            help='The name of the language in the Sublime configuration file. Defaults to value '
                 'provide in instruction set configuration file.'
        )
    @click.option(
            '--language-version', '-k',
            help='The version of the language in the Sublime configuration file. Defaults to '
                 'value provide in instruction set configuration file.'
        )
    @click.option(
            '--code-extension', '-x',
            help='The file extension for asssembly code files for this language configuraton.'
        )
    def sublime(config_file, verbose, editor_config_dir, language_name, language_version, code_extension):
        return handlers.sublime(config_file, verbose, editor_config_dir, language_name, language_version, code_extension)

    @generate_extension.command(cls=OptionForwardingCommand, short_help='generate for Vim editor (syntax only)')
    @click.option(
            '--config-file', '-c', required=True,
            type=click.Path(dir_okay=False, exists=True),
            help='The filepath to the instruction set configuration file,'
        )
    @click.option(
            '--verbose', '-v', count=True,
            help='Verbosity of logging (counting flag: -v, -vv, -vvv or --verbose <n>).'
        )
    @click.option(
            '--editor-config-dir', '-d', default='~/.vim/',
            type=click.Path(file_okay=False),
            help='The Vim configuration root directory containing syntax/ and ftdetect/.'
        )
    @click.option(
            '--language-name', '-l',
            help='The name of the language (used in filetype). Defaults to ISA name.'
        )
    @click.option(
            '--language-version', '-k',
            help='The version of the language. Unused by Vim but kept for parity.'
        )
    @click.option(
            '--code-extension', '-x',
            help='The file extension for asssembly code files for this language configuraton.'
        )
    def vim(config_file, verbose, editor_config_dir, language_name, language_version, code_extension):
        return handlers.vim(config_file, verbose, editor_config_dir, language_name, language_version, code_extension)

    @main.command(cls=OptionForwardingCommand, short_help='install shell tab completions for bespokeasm')
    @click.option(
        '--shell', 'target_shell',
        type=click.Choice(SUPPORTED_COMPLETION_SHELLS, case_sensitive=False),
        help='Shell to install completions for. Defaults to your current shell.',
    )
    @click.option(
        '--path', 'destination',
        help='Optional path to write the completion script. Defaults to a standard user location per shell.',
    )
    @click.option(
        '--prog-name',
        help='Program name to generate completions for. Defaults to the current executable name.',
    )
    def install_completion(target_shell, destination, prog_name):
        """Write a shell completion script to a standard location for the chosen shell."""
        resolved_shell = target_shell.lower() if target_shell else _detect_shell()
        if not resolved_shell:
            click.echo('ERROR: Could not detect shell. Please specify --shell.', err=True)
            sys.exit(1)
        if resolved_shell not in SUPPORTED_COMPLETION_SHELLS:
            click.echo(
                f'ERROR: Shell "{resolved_shell}" is not supported. '
                f'Choose from: {", ".join(SUPPORTED_COMPLETION_SHELLS)}.',
                err=True,
            )
            sys.exit(1)

        resolved_prog_name = prog_name or Path(sys.argv[0]).name
        completion_path = Path(destination).expanduser() \
            if destination else _default_completion_path(resolved_shell, resolved_prog_name)
        completion_path.parent.mkdir(parents=True, exist_ok=True)
        comp_cls = get_completion_class(resolved_shell)
        if comp_cls is None:
            click.echo(
                f'ERROR: Completion generation for "{resolved_shell}" is unavailable in this version of click.',
                err=True,
            )
            sys.exit(1)

        complete_var = f'_{resolved_prog_name.upper().replace("-", "_")}_COMPLETE'
        comp = comp_cls(main, {}, resolved_prog_name, complete_var)
        script = comp.source()
        if resolved_shell == 'zsh':
            script = _inject_zsh_nosort(script)
            script += (
                f'\n# bespokeasm completion preferences\n'
                f"zstyle ':completion:*:*:{resolved_prog_name}:*' sort false\n"
                f"zstyle ':completion:*:*:{resolved_prog_name}:*' list-packed true\n"
                f"zstyle ':completion:*:*:{resolved_prog_name}:*:commands' list-packed true\n"
                f"zstyle ':completion:*:*:{resolved_prog_name}:*' group-order ''\n"
            )
        completion_path.write_text(script)

        click.echo(f'Installed {resolved_shell} completions at {completion_path}')
        if resolved_shell == 'bash':
            click.echo(
                'Bash will load this from bash-completion. Restart your shell or run '
                f'`source {completion_path}` to activate now.'
            )
        elif resolved_shell == 'zsh':
            click.echo(
                'Ensure the directory is in your $fpath, then run '
                f'`fpath=({completion_path.parent} $fpath); autoload -U compinit; compinit` '
                'or restart your shell.'
            )
        elif resolved_shell == 'fish':
            click.echo('Fish auto-loads completions from ~/.config/fish/completions; restart fish if needed.')
        else:
            click.echo('Restart your shell to pick up the new completions.')

    return main
