import shutil
import subprocess
from textwrap import dedent

import click.shell_completion as sc
import pytest
from bespokeasm import completion_cli
from bespokeasm.__main__ import entry_point
from bespokeasm.__main__ import main
from bespokeasm.cli import _inject_zsh_nosort
from click.shell_completion import get_completion_class


def _zsh_completions_for(cli, args, incomplete):
    """Return completion items for given args/incomplete without relying on env vars."""
    comp = sc.ZshComplete(cli, {}, 'bespokeasm', '_BESPOKEASM_COMPLETE')
    return comp.get_completions(args, incomplete)


def _zsh_completions(args, incomplete):
    return _zsh_completions_for(main, args, incomplete)


def test_compile_option_completions_are_unique_and_show_required_metavars():
    items = _zsh_completions(['compile'], '-')
    values = [item.value for item in items]
    assert len(values) == len(set(values))
    config_items = [item for item in items if item.value in {'--config-file', '-c'}]
    assert config_items, 'expected config-file options in completion output'
    for item in config_items:
        assert '[required]' in (item.help or '')
        assert '[FILE]' in (item.help or '')


def test_compile_flag_pair_shows_enable_disable():
    items = _zsh_completions(['compile'], '-')
    binary_help = {item.value: (item.help or '') for item in items if item.value in {'--binary', '-b'}}
    nobinary_help = {item.value: (item.help or '') for item in items if item.value in {'--no-binary', '-n'}}
    assert binary_help, 'expected binary flag completions'
    assert nobinary_help, 'expected no-binary flag completions'
    for text in binary_help.values():
        assert '[enable]' in text
    for text in nobinary_help.values():
        assert '[disable]' in text


def test_docs_options_surface_without_dash():
    items = _zsh_completions(['docs'], '')
    values = {item.value for item in items}
    assert '--config-file' in values
    cfg_help = next(item.help for item in items if item.value == '--config-file')
    assert '[required]' in (cfg_help or '')


def test_generate_extension_vim_options_surface_without_dash():
    items = _zsh_completions(['generate-extension', 'vim'], '')
    values = {item.value: item.help or '' for item in items}
    assert '--config-file' in values
    assert '[required]' in values['--config-file']
    assert '--editor-config-dir' in values
    assert '[optional]' in values['--editor-config-dir']
    # required should appear before optional long options
    order = [item.value for item in items]
    assert order.index('--config-file') < order.index('--editor-config-dir')


def test_generate_extension_vscode_and_sublime_have_required_config_option():
    for sub in ('vscode', 'sublime'):
        items = _zsh_completions(['generate-extension', sub], '')
        values = {item.value: item.help or '' for item in items}
        assert '--config-file' in values
        assert '[required]' in values['--config-file']


def test_completion_cli_matches_main_compile_completions():
    main_items = _zsh_completions_for(main, ['compile'], '-')
    completion_items = _zsh_completions_for(completion_cli.main, ['compile'], '-')
    assert {(item.value, item.help) for item in main_items} == {(item.value, item.help) for item in completion_items}


def test_entry_point_routes_completion_invocations(monkeypatch):
    sentinel = object()
    monkeypatch.setenv('_BESPOKEASM_COMPLETE', 'zsh_complete')
    monkeypatch.setattr(completion_cli, 'entry_point', lambda: sentinel)
    assert entry_point() is sentinel


def test_zsh_completion_script_prettifies_root_commands():
    comp_cls = get_completion_class('zsh')
    comp = comp_cls(main, {}, 'bespokeasm', '_BESPOKEASM_COMPLETE')
    script = _inject_zsh_nosort(comp.source())
    assert 'compstate[nosort]=true' in script
    assert 'local -a _pretty' in script
    assert "printf '%-*s -- %s' $_maxlen" in script
    assert '_describe -V unsorted completions_with_descriptions _pretty -l' in script
    assert 'compadd -1 -U -V unsorted -a completions' in script


def test_zsh_formatting_outputs_rows_per_option_in_zsh():
    if shutil.which('zsh') is None:
        pytest.skip('zsh not available on PATH')
    comp_cls = get_completion_class('zsh')
    comp = comp_cls(main, {}, 'bespokeasm', '_BESPOKEASM_COMPLETE')
    script = _inject_zsh_nosort(comp.source())

    # Short-circuit the completion data inside the generated function to avoid invoking bespokeasm.
    response_stub = 'response=( plain --binary "enable desc" plain -b "enable desc" )'
    script = script.replace(
        'response=("${(@f)$(env COMP_WORDS="${words[*]}" COMP_CWORD=$((CURRENT-1)) '
        '_BESPOKEASM_COMPLETE=zsh_complete bespokeasm)}")',
        response_stub,
    )

    zsh_template = dedent(
        r'''
        typeset -gA compstate
compdef() { :; }
_describe() {
    print -l -- "${_pretty[@]}"
}
compadd() { :; }
__SCRIPT__
    commands[bespokeasm]=/bin/true
words=(bespokeasm compile -)
CURRENT=3
_bespokeasm_completion
'''
    )
    zsh_snippet = zsh_template.replace('__SCRIPT__', script)

    out = (
        subprocess.check_output(['zsh', '-c', zsh_snippet], text=True)
        .strip()
        .splitlines()
    )
    # Entry should contain a single primary option with its description.
    assert any(line.startswith('--binary') and 'enable desc' in line for line in out)
    # No undecorated completions should be emitted when descriptions exist.
    assert all(' -- ' in line for line in out)


def test_zsh_formatting_outputs_rows_per_compile_option_set_in_zsh():
    if shutil.which('zsh') is None:
        pytest.skip('zsh not available on PATH')
    comp_cls = get_completion_class('zsh')
    comp = comp_cls(main, {}, 'bespokeasm', '_BESPOKEASM_COMPLETE')
    script = _inject_zsh_nosort(comp.source())

    # Provide a richer set of compile option completions.
    response_stub = (
        'response=('
        ' plain --config-file "[required] [FILE] config path"'
        ' plain -c "[required] [FILE] config path"'
        ' plain --binary "[optional] [enable] emit binary"'
        ' plain -b "[optional] [enable] emit binary"'
        ' plain --pretty-print "[optional] pretty print output"'
        ' plain -p "[optional] pretty print output"'
        ' )'
    )
    script = script.replace(
        'response=("${(@f)$(env COMP_WORDS="${words[*]}" COMP_CWORD=$((CURRENT-1)) '
        '_BESPOKEASM_COMPLETE=zsh_complete bespokeasm)}")',
        response_stub,
    )

    zsh_template = dedent(
        r'''
        typeset -gA compstate
compdef() { :; }
_describe() {
    print -l -- "${_pretty[@]}"
}
compadd() { :; }
__SCRIPT__
    commands[bespokeasm]=/bin/true
words=(bespokeasm compile -)
CURRENT=3
_bespokeasm_completion
'''
    )
    zsh_snippet = zsh_template.replace('__SCRIPT__', script)

    out = (
        subprocess.check_output(['zsh', '-c', zsh_snippet], text=True)
        .strip()
        .splitlines()
    )
    # Each completion should appear on a single line (primary option only) with its description.
    assert any(line.startswith('--config-file') and 'config path' in line for line in out)
    assert any(line.startswith('--binary') and 'emit binary' in line for line in out)
    assert any(line.startswith('--pretty-print') and 'pretty print output' in line for line in out)
    # Ensure we didn't emit separate description-only entries.
    assert all(' -- ' in line for line in out)
