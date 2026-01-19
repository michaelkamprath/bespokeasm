import importlib.util
import pathlib as pl
import sys
import tempfile
import types


def _load_sublime_hover_module():
    sys.modules.setdefault('sublime', types.SimpleNamespace())
    sys.modules.setdefault('sublime_plugin', types.SimpleNamespace(EventListener=object))
    repo_root = pl.Path(__file__).resolve().parents[1]
    module_path = repo_root / 'src' / 'bespokeasm' / 'configgen' / 'sublime' / 'resources' / 'bespokeasm_hover.py'
    spec = importlib.util.spec_from_file_location('bespokeasm_hover', str(module_path))
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_sublime_mnemonic_hover_table_renders_div_table():
    hover = _load_sublime_hover_module()
    markdown = (
        '### `LDA` : Load A immediate\n\n'
        '| Operand | Type | Value | Description |\n'
        '| --- | --- | --- | --- |\n'
        '| `zp_addr` | address | numeric | 8-bit value |\n'
    )

    html = hover._markdown_to_minihtml(markdown, {})

    assert '<div style="font-family: monospace;">' in html
    assert 'font-weight:500' in html
    assert 'border-right:2px solid' in html
    assert '&nbsp;' in html
    assert '<code' in html
    assert 'zp_addr' in html


def test_sublime_hover_wraps_only_for_description_overflow():
    hover = _load_sublime_hover_module()
    markdown = (
        '| Operand | Type | Description |\n'
        '| --- | --- | --- |\n'
        '| `op` | register | short |\n'
        '| `op2` | register | this description is intentionally long and should wrap |\n'
    )

    html = hover._markdown_to_minihtml(markdown, {})

    assert '<div style="font-family: monospace;">' in html
    assert 'description' in html.lower()
    assert '&nbsp;' in html


def test_sublime_collect_includes_transitive():
    hover = _load_sublime_hover_module()
    with tempfile.TemporaryDirectory() as temp_dir:
        base_dir = pl.Path(temp_dir)
        main_path = base_dir / 'main.asm'
        first_path = base_dir / 'first.asm'
        second_path = base_dir / 'second.asm'
        unrelated_path = base_dir / 'unrelated.asm'

        main_path.write_text('#include "first.asm"\n', encoding='utf-8')
        first_path.write_text('#include "second.asm"\nfirst:\n', encoding='utf-8')
        second_path.write_text('second:\n', encoding='utf-8')
        unrelated_path.write_text('unrelated:\n', encoding='utf-8')

        lines = main_path.read_text(encoding='utf-8').splitlines()
        entries = hover._collect_included_files(lines, str(base_dir))
        paths = {pl.Path(entry['path']).name for entry in entries}

        assert 'first.asm' in paths
        assert 'second.asm' in paths
        assert 'unrelated.asm' not in paths
