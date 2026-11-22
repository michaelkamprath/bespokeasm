"""Tests for the built-in -t symbols JSON format."""
import contextlib
import importlib.resources as pkg_resources
import io
import json

import pytest
from bespokeasm import BESPOKEASM_VERSION_STR
from bespokeasm.assembler.diagnostic_reporter import DiagnosticReporter
from bespokeasm.assembler.engine import Assembler
from bespokeasm.assembler.line_object.instruction_line import InstructionLine
from bespokeasm.assembler.model import AssemblerModel
from bespokeasm.assembler.symbol_scope import SymbolScope
from ruamel.yaml import YAML

from test import config_files

LINKED_ANNOTATION = {
    'arguments': {
        'kind': {'type': 'enum', 'values': ['var', 'addr'], 'required': True},
        'len': {'type': 'symbol'},
    },
    'data_size': {'when': {'kind': ['var']}, 'words': 2},
}


@pytest.fixture(autouse=True)
def _reset_assembler_state():
    InstructionLine.reset_instruction_pattern_cache()
    SymbolScope._global_scope = None
    yield
    SymbolScope._global_scope = None


def _write_config(tmp_path, fixture: str, annotations=None) -> str:
    with open(pkg_resources.files(config_files).joinpath(fixture)) as handle:
        config = YAML(typ='safe').load(handle)
    if annotations is not None:
        config['annotations'] = annotations
    path = tmp_path / 'isa.json'
    path.write_text(json.dumps(config))
    return str(path)


def _symbols(tmp_path, source: str, config_path: str, files: dict[str, str] | None = None) -> dict:
    source_path = tmp_path / 'main.asm'
    source_path.write_text(source)
    for name, text in (files or {}).items():
        (tmp_path / name).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / name).write_text(text)
    output_path = tmp_path / 'main.json'
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        Assembler(
            source_file=str(source_path),
            config_file=config_path,
            generate_binary=False,
            output_file=None,
            binary_start=0,
            binary_end=None,
            binary_fill_value=0,
            enable_pretty_print=True,
            pretty_print_format='symbols',
            pretty_print_output=str(output_path),
            is_verbose=0,
            include_paths=[str(tmp_path / 'lib')],
            predefined=[],
        ).assemble_bytecode()
    return json.loads(output_path.read_text())


def test_document_header(tmp_path):
    document = _symbols(tmp_path, 'start:\n    ld a, b, c\n', _write_config(tmp_path, 'test_instruction_operands.yaml'))
    assert document['format'] == 'bespokeasm-symbols'
    assert document['format_version'] == 1
    assert document['bespokeasm_version'] == BESPOKEASM_VERSION_STR
    assert document['isa'] == {'name': 'bespokeasm-test', 'version': '0.2.0', 'word_size': 8, 'address_size': 16}
    assert document['source_file'] == 'main.asm'


def test_every_label_and_constant_in_definition_order(tmp_path):
    source = '\n'.join([
        '.org $20',
        'start:',
        '    ld a, b, c',
        '.loop:',
        '    ld a, b, c',
        '_hidden: .byte 1',
        '#include "inc.asm"',
        'LIMIT = -3',
        '#ifdef NOT_DEFINED',
        'skipped: .byte 2',
        '#endif',
    ]) + '\n'
    included = 'from_include = 7\n'
    document = _symbols(
        tmp_path, source, _write_config(tmp_path, 'test_instruction_operands.yaml'),
        files={'lib/inc.asm': included},
    )
    summary = [
        (s['name'], s['kind'], s['scope'], s['value'], s['file'], s['line']) for s in document['symbols']
    ]
    assert summary == [
        ('start', 'label', 'global', 0x20, 'main.asm', 2),
        ('.loop', 'label', 'local', 0x23, 'main.asm', 4),
        ('_hidden', 'label', 'file', 0x26, 'main.asm', 6),
        ('from_include', 'constant', 'global', 7, 'lib/inc.asm', 1),
        ('LIMIT', 'constant', 'global', -3, 'main.asm', 8),
    ]
    assert all(s['annotations'] == {} and 'data' not in s for s in document['symbols'])


def test_predefined_symbols_come_first(tmp_path):
    document = _symbols(tmp_path, 'here = 1\n', _write_config(tmp_path, 'test_compiler_features.yaml'))
    assert [(s['name'], s['kind'], s['value'], s['file'], s['line']) for s in document['symbols']] == [
        ('CONST1', 'constant', 44, 'isa.json', None),
        ('CONST2', 'constant', 0xBEEF, 'isa.json', None),
        ('buffer', 'label', 0xF200, 'isa.json', None),
        ('here', 'constant', 1, 'main.asm', 1),
    ]


def test_predefined_symbols_name_the_config_file_not_its_path(tmp_path):
    """A config outside the source directory is named by its file name alone, for YAML as well as JSON."""
    with open(pkg_resources.files(config_files).joinpath('test_compiler_features.yaml')) as handle:
        config = YAML(typ='safe').load(handle)
    config_dir = tmp_path / 'isa' / 'configs'
    config_dir.mkdir(parents=True)
    config_path = config_dir / 'my-cpu.yaml'
    with open(config_path, 'w') as handle:
        YAML(typ='safe').dump(config, handle)
    source_dir = tmp_path / 'src'
    source_dir.mkdir()

    document = _symbols(source_dir, 'here = 1\n', str(config_path))
    files = {symbol['name']: symbol['file'] for symbol in document['symbols']}
    assert files == {'CONST1': 'my-cpu.yaml', 'CONST2': 'my-cpu.yaml', 'buffer': 'my-cpu.yaml', 'here': 'main.asm'}


def test_model_exposes_config_file_path(tmp_path):
    config_path = _write_config(tmp_path, 'test_compiler_features.yaml')
    with contextlib.redirect_stderr(io.StringIO()):
        model = AssemblerModel(config_path, 0, DiagnosticReporter())
    assert model.config_file_path == config_path


def test_annotations_and_data(tmp_path):
    source = '\n'.join([
        '.org $10',
        '#annotate listing heading="Vars"',
        '#annotate linked kind=var len=SIZE',
        'pair: .byte 1, 2',
        'SIZE = 2',
        '#annotate linked kind=addr',
        'SIZE2 = 4',
    ]) + '\n'
    config_path = _write_config(tmp_path, 'test_instruction_operands.yaml', {'linked': LINKED_ANNOTATION})
    pair, size, size2 = _symbols(tmp_path, source, config_path)['symbols']
    assert pair['annotations'] == {
        'listing': {'arguments': {'heading': 'Vars'}, 'resolved_symbols': {}},
        'linked': {'arguments': {'kind': 'var', 'len': 'SIZE'}, 'resolved_symbols': {'len': 2}},
    }
    assert pair['data'] == {'size': 2, 'words': [1, 2]}
    assert size['annotations'] == {}
    assert size2['annotations'] == {'linked': {'arguments': {'kind': 'addr'}, 'resolved_symbols': {}}}
    assert 'data' not in size2
