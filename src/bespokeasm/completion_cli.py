from bespokeasm.cli import build_cli
from bespokeasm.cli import CommandHandlers


def _noop(*_args, **_kwargs):
    return None


main = build_cli(
    CommandHandlers(
        compile=_noop,
        docs=_noop,
        vscode=_noop,
        sublime=_noop,
        vim=_noop,
    )
)


def entry_point():
    return main(auto_envvar_prefix='BESPOKEASM')
