import sys

from bespokeasm.cli import _is_completion_invocation
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
            flow_checks,
            pretty_print_format_explicit=False,
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
        flow_checks=flow_checks,
        pretty_print_format_explicit=pretty_print_format_explicit,
    )
    asm.assemble_bytecode()


def _docs_handler(config_file, output_file, verbose):
    import os

    import click
    from bespokeasm.assembler.diagnostic_reporter import DiagnosticReporter
    from bespokeasm.docsgen import DocumentationGenerator

    config_file = os.path.abspath(os.path.expanduser(config_file))

    if not os.path.exists(config_file):
        click.echo(f'ERROR: Configuration file not found: {config_file}', err=True)
        sys.exit(1)

    generator = DocumentationGenerator(config_file, verbose)
    try:
        with DiagnosticReporter().reporting_errors():
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
    with generator.model.diagnostic_reporter.reporting_errors():
        generator.generate()


def _sublime_handler(config_file, verbose, editor_config_dir, language_name, language_version, code_extension):
    import os

    from bespokeasm.configgen.sublime import SublimeConfigGenerator

    config_file = os.path.abspath(os.path.expanduser(config_file))
    save_config_dir = os.path.abspath(os.path.expanduser(editor_config_dir))
    generator = SublimeConfigGenerator(config_file, verbose, save_config_dir, language_name, language_version, code_extension)
    with generator.model.diagnostic_reporter.reporting_errors():
        generator.generate()


def _vim_handler(config_file, verbose, editor_config_dir, language_name, language_version, code_extension):
    import os

    from bespokeasm.configgen.vim import VimConfigGenerator

    config_file = os.path.abspath(os.path.expanduser(config_file))
    vim_config_dir = os.path.abspath(os.path.expanduser(editor_config_dir))
    generator = VimConfigGenerator(config_file, verbose, vim_config_dir, language_name, language_version, code_extension)
    with generator.model.diagnostic_reporter.reporting_errors():
        generator.generate()


def _migrate_handler(source_file, config_file, dialect_name, output_file, verbose):
    import os

    import click
    from bespokeasm.assembler.diagnostic_reporter import DiagnosticReporter
    from bespokeasm.assembler.model import AssemblerModel
    from bespokeasm.migrate.engine import migrate
    from bespokeasm.migrate.isa import migration_context

    model = AssemblerModel(os.path.abspath(os.path.expanduser(config_file)), verbose, DiagnosticReporter())
    dialects = model.migrations
    if dialect_name not in dialects:
        if not dialects:
            raise click.UsageError(f'{os.path.basename(config_file)} declares no dialects to migrate from')
        choices = '\n'.join(
            f'  {name}' + (f': {dialect.description}' if dialect.description else '')
            for name, dialect in dialects.items()
        )
        problem = 'Name' if dialect_name is None else f'"{dialect_name}" is not one of them. Name'
        raise click.UsageError(
            f'{os.path.basename(config_file)} can migrate source from these assemblers. {problem} one '
            f'with --from:\n{choices}'
        )
    if output_file is not None and os.path.exists(output_file) and os.path.samefile(output_file, source_file):
        raise click.UsageError('--output-file is the source file; migrate never overwrites its input')

    with open(source_file, encoding='utf-8', errors='surrogateescape', newline='') as handle:
        text = handle.read()
    result = migrate(text, dialects[dialect_name], migration_context(model))
    if output_file is None:
        click.echo(result.text, nl=False)
    else:
        with open(output_file, 'w', encoding='utf-8', errors='surrogateescape', newline='') as handle:
            handle.write(result.text)

    source_name = os.path.basename(source_file)
    summary = [f'Migrated {source_name} from {dialect_name}: {len(result.lines)} lines']
    summary.extend(f'  {count.kind}: {count.lines} lines' for count in result.rule_counts if count.lines)
    reported = result.reported
    if reported:
        summary.append(
            f'Reported, kept as "; MIGRATE:" comments ({result.reported_line_count} lines; port them by hand):'
        )
        summary.extend(f'  {source_name}:{line.number}: {"; ".join(line.reports)}' for line in reported)
    if result.noted:
        summary.append('Notes:')
        summary.extend(f'  {source_name}:{line.number}: {"; ".join(line.notes)}' for line in result.noted)
    click.echo('\n'.join(summary), err=True)
    if reported:
        sys.exit(1)


_HANDLERS = CommandHandlers(
    compile=_compile_handler,
    docs=_docs_handler,
    vscode=_vscode_handler,
    sublime=_sublime_handler,
    vim=_vim_handler,
    migrate=_migrate_handler,
)


def _build_main():
    from bespokeasm.cli import build_cli
    return build_cli(_HANDLERS)


def entry_point():
    # Preserve completion calls without modifying argv
    if _is_completion_invocation():
        from bespokeasm.completion_cli import completion_entry_point
        return completion_entry_point(_HANDLERS)

    main = _build_main()

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
        'migrate',
    }
    first_non_option = next((arg for arg in args if not arg.startswith('-')), None)
    if first_non_option is None or first_non_option in known_subcommands:
        return main(auto_envvar_prefix='BESPOKEASM')

    # Inject default subcommand for backward compatibility
    sys.argv = [sys.argv[0], 'compile', *args]
    return main(auto_envvar_prefix='BESPOKEASM')


if __name__ == '__main__':
    sys.exit(entry_point())
