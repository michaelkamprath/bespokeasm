from bespokeasm.cli import build_cli
from bespokeasm.cli import CommandHandlers


def _noop(*_args, **_kwargs):
    return None


_NOOP_HANDLERS = CommandHandlers(
    compile=_noop,
    docs=_noop,
    vscode=_noop,
    sublime=_noop,
    vim=_noop,
)


def completion_entry_point(handlers: CommandHandlers | None = None):
    """Entry point for shell completion.

    When *handlers* are provided (from __main__), they are used to build
    the CLI so that completions reflect the real command signatures.
    When called standalone (legacy path), lightweight noop handlers are
    used instead.
    """
    main = build_cli(handlers or _NOOP_HANDLERS)
    return main(auto_envvar_prefix='BESPOKEASM')


def entry_point():
    """Legacy entry point kept for backward compatibility."""
    return completion_entry_point()
