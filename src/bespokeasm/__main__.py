import sys

from bespokeasm.cli import _inject_zsh_nosort  # noqa: F401
from bespokeasm.cli import _is_completion_invocation
from bespokeasm.cli import build_cli
from bespokeasm.cli import CommandHandlers


def _compile_handler(
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
    import os

    import click
    from bespokeasm.assembler.engine import Assembler

    if output_file is None:
        output_file = os.path.splitext(asm_file)[0] + '.bin'
    if verbose:
        click.echo(f'The file to assemble is: {asm_file}')
        if binary:
            click.echo(f'The binary image will be written to: {output_file}')
        if int(binary_min_address) > 0:
            click.echo(f'  with the starting address written: {binary_min_address}')
        if int(binary_max_address) >= 0:
            click.echo(f'  with the maximum address written: {binary_max_address}')

    asm = Assembler(
        asm_file, config_file,
        binary, output_file,
        int(binary_min_address), int(binary_max_address) if int(binary_max_address) >= 0 else None,
        binary_fill,
        pretty_print, pretty_print_format, pretty_print_output, verbose,
        include_path,
        macro_symbol,
        warnings_as_errors,
    )
    asm.assemble_bytecode()


def _docs_handler(config_file, output_file, verbose):
    import os

    import click
    from bespokeasm.docsgen import DocumentationGenerator

    config_file = os.path.abspath(os.path.expanduser(config_file))

    if not os.path.exists(config_file):
        click.echo(f'ERROR: Configuration file not found: {config_file}', err=True)
        sys.exit(1)

    generator = DocumentationGenerator(config_file, verbose)
    try:
        output_path = generator.generate_markdown_documentation(output_file)
        click.echo(f'Documentation generated: {output_path}')
    except SystemExit:
        # Re-raise SystemExit from the generator (contains proper error messages)
        raise
    except Exception as e:
        click.echo(f'ERROR: Failed to generate documentation: {e}', err=True)
        sys.exit(1)


def _vscode_handler(config_file, verbose, editor_config_dir, language_name, language_version, code_extension):
    import os

    from bespokeasm.configgen.vscode import VSCodeConfigGenerator

    config_file = os.path.abspath(os.path.expanduser(config_file))
    vscode_config_dir = os.path.abspath(os.path.expanduser(editor_config_dir))
    generator = VSCodeConfigGenerator(config_file, verbose, vscode_config_dir, language_name, language_version, code_extension)
    generator.generate()


def _sublime_handler(config_file, verbose, editor_config_dir, language_name, language_version, code_extension):
    import os

    from bespokeasm.configgen.sublime import SublimeConfigGenerator

    config_file = os.path.abspath(os.path.expanduser(config_file))
    save_config_dir = os.path.abspath(os.path.expanduser(editor_config_dir))
    generator = SublimeConfigGenerator(config_file, verbose, save_config_dir, language_name, language_version, code_extension)
    generator.generate()


def _vim_handler(config_file, verbose, editor_config_dir, language_name, language_version, code_extension):
    import os

    from bespokeasm.configgen.vim import VimConfigGenerator

    config_file = os.path.abspath(os.path.expanduser(config_file))
    vim_config_dir = os.path.abspath(os.path.expanduser(editor_config_dir))
    generator = VimConfigGenerator(config_file, verbose, vim_config_dir, language_name, language_version, code_extension)
    generator.generate()


main = build_cli(
    CommandHandlers(
        compile=_compile_handler,
        docs=_docs_handler,
        vscode=_vscode_handler,
        sublime=_sublime_handler,
        vim=_vim_handler,
    )
)


def entry_point():
    # Preserve completion calls without modifying argv
    if _is_completion_invocation():
        from bespokeasm import completion_cli

        return completion_cli.entry_point()

    args = sys.argv[1:]
    # Friendly banner for bare --help or no args
    if '--help' in args or not args:
        import click

        click.echo('bespokeasm')
        return main(auto_envvar_prefix='BESPOKEASM')

    # If a known subcommand is present, run as-is; otherwise assume compile by default.
    known_subcommands = {
        'compile',
        'docs',
        'generate_extension',
        'generate-extension',
        'vscode',
        'sublime',
        'vim',
        'install_completion',
        'install-completion',
    }
    first_non_option = next((arg for arg in args if not arg.startswith('-')), None)
    if first_non_option is None or first_non_option in known_subcommands:
        return main(auto_envvar_prefix='BESPOKEASM')

    # Inject default subcommand for backward compatibility
    sys.argv = [sys.argv[0], 'compile', *args]
    return main(auto_envvar_prefix='BESPOKEASM')


if __name__ == '__main__':
    sys.exit(entry_point())
