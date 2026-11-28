"""The compile command's binary address and fill options accept any BespokeASM numeric literal."""
import pytest
from bespokeasm.cli import build_cli
from bespokeasm.cli import CommandHandlers
from click.testing import CliRunner


def _compile_arguments(tmp_path, *options: str):
    """The binary min address, max address and fill that `compile` passes to its handler."""
    received = {}

    def compile_handler(*args):
        received['addresses'] = args[4:7]

    def unused(*_args):
        return None

    cli = build_cli(CommandHandlers(compile=compile_handler, docs=unused, vscode=unused, sublime=unused, vim=unused))
    (tmp_path / 'isa.yaml').write_text('')
    (tmp_path / 'main.asm').write_text('')
    result = CliRunner().invoke(
        cli, ['compile', '-c', str(tmp_path / 'isa.yaml'), *options, str(tmp_path / 'main.asm')],
    )
    return result, received.get('addresses')


@pytest.mark.parametrize('start', ['32768', '0x8000', '$8000', '8000H', '0o100000', '%1000000000000000'])
def test_binary_addresses_accept_numeric_literals(tmp_path, start):
    result, addresses = _compile_arguments(tmp_path, '-s', start, '-e', '0xFFFF', '-f', '$FF')
    assert result.exit_code == 0, result.output
    assert addresses == (0x8000, 0xFFFF, 0xFF)


def test_binary_options_keep_their_defaults(tmp_path):
    result, addresses = _compile_arguments(tmp_path)
    assert result.exit_code == 0, result.output
    assert addresses == (0, -1, 0)


def test_a_value_that_is_not_a_number_is_an_error(tmp_path):
    result, addresses = _compile_arguments(tmp_path, '-s', '0x80G0')
    assert result.exit_code != 0
    assert addresses is None
    assert "'0x80G0' is not a number; write it in decimal or as a numeric literal such as 0x8000" in result.output
