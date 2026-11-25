"""Tests for #annotate: config schema, argument validation, binding, constraints and the export model."""
import contextlib
import copy
import importlib.resources as pkg_resources
import io
import json
import os

import pytest
from bespokeasm.assembler.engine import Assembler
from bespokeasm.assembler.line_object.instruction_line import InstructionLine
from bespokeasm.assembler.symbol_scope import SymbolScope
from ruamel.yaml import YAML

from test import config_files

XMIN_ANNOTATION = {
    'documentation': {'description': 'Export a symbol to the xmin source file format.'},
    'applies_to': ['label', 'constant'],
    'scopes': ['global'],
    'arguments': {
        'kind': {'type': 'enum', 'values': ['addr', 'var', 'const'], 'required': True},
        'type': {
            'type': 'enum', 'values': ['char', 'int', 'long', 'str'], 'required_when': {'kind': ['var', 'const']},
        },
        'count': {'type': 'integer', 'min': 1, 'allowed_when': {'kind': ['var']}},
        'array': {'type': 'boolean', 'allowed_when': {'kind': ['var']}},
        'name': {'type': 'string', 'pattern': '^[A-Za-z][A-Za-z0-9]{0,12}$'},
    },
    'data_size': {
        'when': {'kind': ['var']},
        'words': {'type': {'char': 1, 'int': 2, 'long': 4, 'str': 1}, 'times': 'count', 'infer_times': 'array'},
        'terminated_when': {'type': ['str']},
    },
    'value_range': {
        'when': {'kind': ['const']},
        'range': {'type': {'char': [0, 255], 'int': [-32768, 32767], 'long': [-2147483648, 2147483647], 'str': None}},
    },
}

LINKED_ANNOTATION = {
    'arguments': {
        'len': {'type': 'symbol', 'required': True},
        'note': {'type': 'string', 'default': 'none'},
    },
}


@pytest.fixture(autouse=True)
def _reset_assembler_state():
    InstructionLine.reset_instruction_pattern_cache()
    SymbolScope._global_scope = None
    yield
    SymbolScope._global_scope = None


def _load_fixture(name: str) -> dict:
    path = pkg_resources.files(config_files).joinpath(name)
    with open(path) as handle:
        return YAML(typ='safe').load(handle)


def _write_config(tmp_path, annotations=None, fixture='test_instruction_operands.yaml') -> str:
    config = _load_fixture(fixture)
    if annotations is not None:
        config['annotations'] = copy.deepcopy(annotations)
    path = tmp_path / 'isa.json'
    path.write_text(json.dumps(config))
    return str(path)


def _assemble(tmp_path, source: str, config_path: str, files: dict[str, str] | None = None, binary: bool = False):
    source_path = tmp_path / 'main.asm'
    source_path.write_text(source)
    for name, text in (files or {}).items():
        (tmp_path / name).write_text(text)
    output_path = str(tmp_path / 'main.bin')
    stdout = io.StringIO()
    stderr = io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        assembler = _build_assembler(source_path, config_path, tmp_path, output_path, binary)
        assembler.assemble_bytecode()
    return assembler, stderr.getvalue(), output_path


def _build_assembler(source_path, config_path, tmp_path, output_path, binary) -> Assembler:
    return Assembler(
        source_file=str(source_path),
        config_file=config_path,
        generate_binary=binary,
        output_file=output_path,
        binary_start=0,
        binary_end=None,
        binary_fill_value=0,
        enable_pretty_print=False,
        pretty_print_format=None,
        pretty_print_output=None,
        is_verbose=0,
        include_paths=[str(tmp_path)],
        predefined=[],
    )


def _assemble_error(tmp_path, source: str, config_path: str, files: dict[str, str] | None = None) -> str:
    with pytest.raises(SystemExit) as exc_info:
        _assemble(tmp_path, source, config_path, files)
    return str(exc_info.value)


def _config_error(tmp_path, annotations) -> str:
    config_path = _write_config(tmp_path, annotations)
    with pytest.raises(SystemExit) as exc_info:
        _assemble(tmp_path, 'ld a, b, c\n', config_path)
    return str(exc_info.value)


def _xmin_config(tmp_path) -> str:
    return _write_config(tmp_path, {'xmin': XMIN_ANNOTATION, 'linked': LINKED_ANNOTATION})


# ---- export model -----------------------------------------------------------------

def test_export_model_records_annotated_symbols(tmp_path):
    source = '\n'.join([
        '.org $100',
        '#annotate xmin kind=addr name=AddW',
        'add_w:',
        '    ld a, b, c',
        '',
        '#annotate xmin kind=var type=int',
        'pa: .2byte 0',
        '#annotate listing heading="Parameter block"',
        '#annotate xmin kind=var type=char count=$4   ; hex literal',
        'buf:',
        '    ; a comment does not end the data run',
        '    .byte 1, 2',
        '    .byte 3, 4',
        'unannotated: .byte 9',
        '#annotate xmin kind=const type=int',
        'MAXARG = 1000',
    ]) + '\n'
    assembler, _, _ = _assemble(tmp_path, source, _xmin_config(tmp_path))
    symbols = {symbol.name: symbol for symbol in assembler.export_model.symbols}
    assert list(symbols) == ['add_w', 'pa', 'buf', 'MAXARG']

    add_w = symbols['add_w']
    assert (add_w.kind, add_w.scope, add_w.address, add_w.size) == ('label', 'global', 0x100, 0)
    assert add_w.annotations['xmin'].arguments == {'kind': 'addr', 'name': 'AddW'}

    pa = symbols['pa']
    assert pa.address == 0x103   # ld a, b, c is 3 bytes
    assert pa.size == 2
    assert [word.value for word in pa.words] == [0, 0]

    buf = symbols['buf']
    assert buf.size == 4
    assert [word.value for word in buf.words] == [1, 2, 3, 4]
    assert buf.annotations['listing'].arguments == {'heading': 'Parameter block'}
    assert buf.annotations['xmin'].arguments['count'] == 4

    maxarg = symbols['MAXARG']
    assert (maxarg.kind, maxarg.value, maxarg.address, maxarg.size) == ('constant', 1000, None, None)

    assert [symbol.name for symbol in assembler.export_model.for_namespace('listing')] == ['buf']


def test_annotations_do_not_change_assembled_bytes(tmp_path):
    body = [
        'start:',
        '    ld a, b, c',
        'value: .2byte $1234',
        'LIMIT = 7',
    ]
    annotated = [
        '#annotate xmin kind=addr',
        body[0],
        body[1],
        '#annotate xmin kind=var type=int',
        body[2],
        '#annotate xmin kind=const type=char',
        body[3],
    ]
    config_path = _xmin_config(tmp_path)
    plain_dir = tmp_path / 'plain'
    annotated_dir = tmp_path / 'annotated'
    plain_dir.mkdir()
    annotated_dir.mkdir()
    _, _, plain_bin = _assemble(plain_dir, '\n'.join(body) + '\n', config_path, binary=True)
    SymbolScope._global_scope = None
    _, _, annotated_bin = _assemble(annotated_dir, '\n'.join(annotated) + '\n', config_path, binary=True)
    with open(plain_bin, 'rb') as plain, open(annotated_bin, 'rb') as with_annotations:
        assert plain.read() == with_annotations.read()


def test_listing_namespace_exists_without_annotations_section(tmp_path):
    source = '#annotate listing heading="Start" page_break\nstart:\n    ld a, b, c\n'
    assembler, _, _ = _assemble(tmp_path, source, _write_config(tmp_path))
    (symbol,) = assembler.export_model.symbols
    assert symbol.annotations['listing'].arguments == {'heading': 'Start', 'page_break': True}


def test_symbol_argument_resolves_after_layout(tmp_path):
    source = '\n'.join([
        '.org $10',
        '#annotate linked len=buf_len',
        'buf: .byte 1, 2, 3',
        'buf_len = 3',
        'later: .byte 0',
        '#annotate linked len=later note="forward reference"',
        'ptr: .byte 0',
    ]) + '\n'
    assembler, _, _ = _assemble(tmp_path, source, _xmin_config(tmp_path))
    by_name = {symbol.name: symbol.annotations['linked'] for symbol in assembler.export_model.symbols}
    assert by_name['buf'].resolved_symbols == {'len': 3}
    assert by_name['buf'].arguments['note'] == 'none'
    assert by_name['ptr'].resolved_symbols == {'len': 0x13}
    assert by_name['ptr'].arguments['note'] == 'forward reference'


def test_symbol_argument_names_unknown_symbol(tmp_path):
    message = _assemble_error(tmp_path, '#annotate linked len=buf_len\nbuf: .byte 1\n', _xmin_config(tmp_path))
    assert "annotation 'linked': 'len' names unknown symbol 'buf_len'" in message


def test_annotation_in_included_file(tmp_path):
    included = '#annotate xmin kind=var type=int\ncounter: .2byte 0\n'
    source = '#include "lib.asm"\nstart:\n    ld a, b, c\n'
    assembler, _, _ = _assemble(tmp_path, source, _xmin_config(tmp_path), files={'lib.asm': included})
    assert [symbol.name for symbol in assembler.export_model.symbols] == ['counter']


def test_data_run_ends_at_end_of_file(tmp_path):
    included = '#annotate xmin kind=var type=int\ncounter:\n'
    source = '#include "lib.asm"\n.2byte 0\n'
    message = _assemble_error(tmp_path, source, _xmin_config(tmp_path), files={'lib.asm': included})
    assert "'counter' is annotated as type=int, which needs 2 words, but no data follows it" in message


def test_annotation_obeys_conditional_compilation(tmp_path):
    source = '\n'.join([
        '#ifdef NOT_DEFINED',
        '#annotate xmin kind=var type=int',
        '#endif',
        'flag: .byte 0',
    ]) + '\n'
    assembler, _, _ = _assemble(tmp_path, source, _xmin_config(tmp_path))
    assert assembler.export_model.symbols == []


def test_words_are_counted_in_isa_words(tmp_path):
    annotations = {'sized': {'arguments': {}, 'data_size': {'words': 2}}}
    config_path = _write_config(tmp_path, annotations, fixture='test_16bit_data_words.yaml')
    assembler, _, _ = _assemble(tmp_path, '#annotate sized\npair: .2byte 1, 2\n', config_path)
    (symbol,) = assembler.export_model.symbols
    assert symbol.size == 2


# ---- source errors --------------------------------------------------------------------

@pytest.mark.parametrize(('source', 'expected'), [
    ('#annotate xmn kind=addr\nstart:\n', "this instruction set does not define annotation 'xmn'"),
    ('#annotate\nstart:\n', '#annotate requires an annotation namespace'),
    ('#annotate xmin kind=func\nstart:\n', "annotation 'xmin': argument 'kind' must be one of addr, var, const"),
    ('#annotate xmin knd=addr\nstart:\n', "annotation 'xmin': unknown argument 'knd'; did you mean 'kind'?"),
    ('#annotate xmin kind=addr kind=var\nstart:\n', "argument 'kind' is given more than once"),
    ('#annotate xmin type=int\nx: .2byte 0\n', "annotation 'xmin': argument 'kind' is required"),
    ('#annotate xmin kind=var\nx: .2byte 0\n', "argument 'type' is required when kind is one of var, const"),
    ('#annotate xmin kind=addr count=2\nx:\n', "annotation 'xmin': 'count' is only allowed when kind is var"),
    ('#annotate xmin kind=var type=char count=0\nx:\n', "argument 'count' must be at least 1, not 0"),
    ('#annotate xmin kind=var type=char count=many\nx:\n', 'argument \'count\' must be an integer, not "many"'),
    ('#annotate xmin kind=addr name=add_w\nadd_w:\n', 'argument \'name\' value "add_w" does not match the pattern'),
    ('#annotate xmin kind\nx:\n', "argument 'kind' needs a value"),
    ('#annotate listing hide=maybe\nx:\n', 'argument \'hide\' must be true or false, not "maybe"'),
    ('#annotate xmin kind=addr name="unterminated\nx:\n', "annotation 'xmin': cannot parse argument"),
])
def test_argument_errors(tmp_path, source, expected):
    assert expected in _assemble_error(tmp_path, source, _xmin_config(tmp_path))


@pytest.mark.parametrize(('written', 'value'), [
    ('"a\\nb"', 'a\nb'),            # \n is a line break
    ('"a\\tb"', 'a\tb'),            # \t is a tab
    ('"say \\"hi\\""', 'say "hi"'),  # an escaped quote
    ('"back\\\\slash"', 'back\\slash'),  # an escaped backslash
    ('"\\x"', 'x'),                 # any other escaped character stands for itself
])
def test_quoted_value_escapes(written, value):
    from bespokeasm.assembler.annotations.parser import parse_annotation_directive
    from bespokeasm.assembler.line_identifier import LineIdentifier
    _, arguments = parse_annotation_directive(LineIdentifier(1, 'x.asm'), f'#annotate listing heading={written}')
    assert arguments[0].value == value


def test_quoted_string_with_escapes(tmp_path):
    source = '#annotate listing heading="Say \\"hi\\"; then go"\nx:\n    ld a, b, c\n'
    assembler, _, _ = _assemble(tmp_path, source, _xmin_config(tmp_path))
    assert assembler.export_model.symbols[0].annotations['listing'].arguments['heading'] == 'Say "hi"; then go'


@pytest.mark.parametrize(('between', 'description'), [
    ('', 'a blank line'),
    ('; just a comment', 'a comment line'),
    ('ld a, b, c', 'not a label or constant definition'),
    ('#define FOO 1', 'not a label or constant definition'),
])
def test_annotation_must_be_directly_above_definition(tmp_path, between, description):
    source = f'#annotate xmin kind=addr\n{between}\nstart:\n    ld a, b, c\n'
    message = _assemble_error(tmp_path, source, _xmin_config(tmp_path))
    assert 'line 1' in message
    assert f'#annotate must be directly above a label or constant definition, but line 2 is {description}' in message


def test_annotation_at_end_of_file(tmp_path):
    message = _assemble_error(tmp_path, 'start:\n    ld a, b, c\n#annotate xmin kind=addr\n', _xmin_config(tmp_path))
    assert '#annotate at the end of the file has no label or constant definition after it' in message


def test_same_namespace_twice_on_one_symbol(tmp_path):
    source = '#annotate xmin kind=addr\n#annotate xmin kind=addr\nstart:\n    ld a, b, c\n'
    message = _assemble_error(tmp_path, source, _xmin_config(tmp_path))
    assert "symbol 'start' already has an annotation in the 'xmin' namespace" in message


@pytest.mark.parametrize(('source', 'expected'), [
    (
        'start:\n#annotate xmin kind=addr\n.loop:\n    ld a, b, c\n',
        "annotation 'xmin' is not allowed on local label '.loop'; it applies only to global symbols",
    ),
    (
        '#annotate xmin kind=const type=int\n_LIMIT = 3\n',
        "annotation 'xmin' is not allowed on file constant '_LIMIT'",
    ),
    (
        '#annotate linked len=x\nx = 3\n',
        None,
    ),
])
def test_scope_and_kind_restrictions(tmp_path, source, expected):
    annotations = {'xmin': XMIN_ANNOTATION, 'linked': dict(LINKED_ANNOTATION, applies_to=['label'])}
    config_path = _write_config(tmp_path, annotations)
    message = _assemble_error(tmp_path, source, config_path)
    assert (expected or "annotation 'linked' is not allowed on constant 'x'; it applies only to labels") in message


@pytest.mark.parametrize(('data', 'found'), [
    ('x: .byte 0', '1 word of data follows it'),
    ('x: .8byte 0', '8 words of data follow it'),
    ('x: .2byte 0\n    .byte 0', '3 words of data follow it'),
    ('x:\ny: .2byte 0', 'no data follows it'),
    ('x:\n    ld a, b, c', 'no data follows it'),
])
def test_data_size_mismatch(tmp_path, data, found):
    source = f'#annotate xmin kind=var type=int\n{data}\n'
    message = _assemble_error(tmp_path, source, _xmin_config(tmp_path))
    assert f"'x' is annotated as type=int, which needs 2 words, but {found}" in message


def test_data_size_mismatch_names_the_count(tmp_path):
    source = '#annotate xmin kind=var type=int count=3\nx: .2byte 0\n'
    message = _assemble_error(tmp_path, source, _xmin_config(tmp_path))
    assert "'x' is annotated as type=int count=3, which needs 6 words, but 2 words of data follow it" in message


@pytest.mark.parametrize(('rule', 'expected'), [
    # A fixed size names the arguments its `when` tests.
    (
        {'when': {'kind': ['var']}, 'words': 2},
        "'x' is annotated as kind=var, which needs 2 words, but 1 word of data follows it (annotation 'fixed')",
    ),
    # With no argument choosing the size, the message gives the size alone.
    ({'words': 2}, "'x' is annotated as 2 words but 1 word of data follows it (annotation 'fixed')"),
])
def test_data_size_mismatch_with_a_fixed_size(tmp_path, rule, expected):
    annotations = {'fixed': {'arguments': {'kind': {'type': 'enum', 'values': ['var']}}, 'data_size': rule}}
    message = _assemble_error(tmp_path, '#annotate fixed kind=var\nx: .byte 0\n', _write_config(tmp_path, annotations))
    assert expected in message


@pytest.mark.parametrize(('data', 'count'), [
    ('x: .cstr "hello"', 6),
    ('x: .byte 1\n    .byte 2, 3', 3),
    ('x: .byte 9', 1),
])
def test_array_takes_its_count_from_the_data(tmp_path, data, count):
    source = f'#annotate xmin kind=var type=char array\n{data}\n'
    assembler, _, _ = _assemble(tmp_path, source, _xmin_config(tmp_path))
    arguments = assembler.export_model.symbols[0].annotations['xmin'].arguments
    assert arguments['count'] == count
    assert arguments['array'] is True


def test_array_count_is_in_whole_elements(tmp_path):
    source = '#annotate xmin kind=var type=int array\nx: .2byte 1, 2, 3\n'
    assembler, _, _ = _assemble(tmp_path, source, _xmin_config(tmp_path))
    assert assembler.export_model.symbols[0].annotations['xmin'].arguments['count'] == 3


@pytest.mark.parametrize(('annotation', 'data', 'expected'), [
    (
        'type=int array', 'x: .byte 1, 2, 3',
        "'x' is annotated as type=int array, which needs a whole number of 2-word elements, "
        "but 3 words of data follow it (annotation 'xmin')",
    ),
    (
        'type=char array', 'x:\n    ld a, b, c',
        "'x' is annotated as type=char array, which needs at least one 1-word element, but no data follows it",
    ),
    (
        'type=char array count=3', 'x: .byte 1, 2, 3',
        "annotation 'xmin': 'count' cannot be given with 'array', which takes count from the data",
    ),
    # array=false is the same as leaving it out: the size is type times count (1).
    (
        'type=char array=false', 'x: .byte 1, 2, 3',
        "'x' is annotated as type=char array=false, which needs 1 word, but 3 words of data follow it",
    ),
])
def test_array_errors(tmp_path, annotation, data, expected):
    message = _assemble_error(tmp_path, f'#annotate xmin kind=var {annotation}\n{data}\n', _xmin_config(tmp_path))
    assert expected in message


@pytest.mark.parametrize(('data', 'count'), [
    ('x: .cstr "hello"', 5),
    ('x: .byte "ab"\n    .cstr "cd"', 4),
    ('x: .byte 65, 0', 1),
])
def test_terminated_count_leaves_out_the_terminator(tmp_path, data, count):
    source = f'#annotate xmin kind=var type=str\n{data}\n'
    assembler, _, _ = _assemble(tmp_path, source, _xmin_config(tmp_path))
    assert assembler.export_model.symbols[0].annotations['xmin'].arguments['count'] == count


@pytest.mark.parametrize(('annotation', 'data', 'expected'), [
    (
        'type=str', 'x: .byte 65, 66',
        "'x' is annotated as type=str, which needs its data to end with a 0 terminator, but it ends with 0x42 "
        "(annotation 'xmin')",
    ),
    (
        'type=str', 'x: .cstr ""',
        "'x' is annotated as type=str, which needs at least one 1-word element and a terminator, "
        'but 1 word of data follows it',
    ),
    (
        'type=str', 'x:\n    ld a, b, c',
        "'x' is annotated as type=str, which needs at least one 1-word element and a terminator, "
        'but no data follows it',
    ),
    (
        'type=str count=5', 'x: .cstr "hello"',
        "annotation 'xmin': 'count' cannot be given with type=str, which takes count from the data",
    ),
])
def test_terminated_errors(tmp_path, annotation, data, expected):
    message = _assemble_error(tmp_path, f'#annotate xmin kind=var {annotation}\n{data}\n', _xmin_config(tmp_path))
    assert expected in message


def test_terminator_is_the_isa_cstr_terminator(tmp_path):
    config = _load_fixture('test_instruction_operands.yaml')
    config['general']['cstr_terminator'] = 3
    config['annotations'] = {'xmin': XMIN_ANNOTATION}
    path = tmp_path / 'isa.json'
    path.write_text(json.dumps(config))
    assembler, _, _ = _assemble(tmp_path, '#annotate xmin kind=var type=str\nx: .cstr "hi"\n', str(path))
    assert assembler.export_model.symbols[0].annotations['xmin'].arguments['count'] == 2
    SymbolScope._global_scope = None
    message = _assemble_error(tmp_path, '#annotate xmin kind=var type=str\nx: .byte 1, 0\n', str(path))
    assert 'which needs its data to end with a 3 terminator, but it ends with 0x00' in message


def test_null_table_entry_is_not_allowed(tmp_path):
    message = _assemble_error(tmp_path, '#annotate xmin kind=const type=str\nX = 5\n', _xmin_config(tmp_path))
    assert "annotation 'xmin': type=str is not allowed when kind is const" in message


def test_value_range_with_a_fixed_range(tmp_path):
    annotations = {'small': {'arguments': {}, 'value_range': {'range': [0, 9]}}}
    message = _assemble_error(tmp_path, '#annotate small\nLIMIT = 10\n', _write_config(tmp_path, annotations))
    assert "'LIMIT' value 10 is outside 0 to 9 (annotation 'small')" in message


@pytest.mark.parametrize('data', [
    'x: .2byte 0',
    'x: .byte 0, 0',
    'x: .byte 0\n    .byte 0',
    'x: .zero 2',
    'x:\n    ; comment\n\n    .2byte 0',
])
def test_data_size_matches(tmp_path, data):
    source = f'#annotate xmin kind=var type=int\n{data}\n'
    assembler, _, _ = _assemble(tmp_path, source, _xmin_config(tmp_path))
    assert assembler.export_model.symbols[0].size == 2


def test_value_range(tmp_path):
    message = _assemble_error(tmp_path, '#annotate xmin kind=const type=char\nLIMIT = 1000\n', _xmin_config(tmp_path))
    assert "'LIMIT' value 1000 is outside 0 to 255, the range of type=char (annotation 'xmin')" in message
    SymbolScope._global_scope = None
    assembler, _, _ = _assemble(tmp_path, '#annotate xmin kind=const type=int\nLIMIT = -5\n', _xmin_config(tmp_path))
    assert assembler.export_model.symbols[0].value == -5


def _ranged_config(tmp_path) -> str:
    """xmin with a list of value_range rules: consts by type, then addresses as 16-bit values."""
    annotation = copy.deepcopy(XMIN_ANNOTATION)
    annotation['value_range'] = [annotation['value_range'], {'when': {'kind': ['addr']}, 'range': [0, 0xffff]}]
    return _write_config(tmp_path, {'xmin': annotation})


@pytest.mark.parametrize(('source', 'expected'), [
    ('#annotate xmin kind=addr\nREG = $FEC0\n', 0xFEC0),
    ('#annotate xmin kind=const type=int\nLIMIT = -5\n', -5),
])
def test_value_range_rules_in_order(tmp_path, source, expected):
    """The first rule whose `when` holds applies: an addr constant may use all 16 bits."""
    assembler, _, _ = _assemble(tmp_path, source, _ranged_config(tmp_path))
    assert assembler.export_model.symbols[0].value == expected


@pytest.mark.parametrize(('source', 'expected'), [
    ('#annotate xmin kind=addr\nREG = $10000\n', "'REG' value 65536 is outside 0 to 65535, the range of kind=addr"),
    (
        '#annotate xmin kind=const type=int\nREG = $FEC0\n',
        "'REG' value 65216 is outside -32768 to 32767, the range of type=int",
    ),
])
def test_value_range_rules_check_their_own_range(tmp_path, source, expected):
    assert expected in _assemble_error(tmp_path, source, _ranged_config(tmp_path))


def test_value_range_rules_without_a_match_check_nothing(tmp_path):
    """A label never has a value range, and no rule applies to kind=var."""
    assembler, _, _ = _assemble(tmp_path, '#annotate xmin kind=var type=char\nx: .byte 0\n', _ranged_config(tmp_path))
    assert assembler.export_model.symbols[0].size == 1


def test_annotate_is_a_reserved_word(tmp_path):
    message = _assemble_error(tmp_path, 'annotate:\n    ld a, b, c\n', _write_config(tmp_path))
    assert '"annotate" is an assembler keyword' in message


# ---- configuration errors -------------------------------------------------------

@pytest.mark.parametrize(('annotations', 'expected'), [
    ({'listing': {}}, 'annotations.listing "listing" is a framework annotation namespace'),
    ({'9bad': {}}, 'annotations.9bad is not a valid annotation namespace name'),
    ({'ns': {'arguments': {'a': {'type': 'float'}}}}, 'annotations.ns.arguments.a.type must be one of enum'),
    ({'ns': {'arguments': {'a': {'type': 'enum'}}}}, 'annotations.ns.arguments.a.values is required'),
    ({'ns': {'arguments': {'a': {'type': 'string', 'min': 1}}}}, 'annotations.ns.arguments.a.min only applies'),
    ({'ns': {'arguments': {'a': {'type': 'string', 'pattern': '('}}}}, 'is not a valid regular expression'),
    (
        {'ns': {'arguments': {'a': {'type': 'integer'}, 'b': {'type': 'string', 'required_when': {'a': [1]}}}}},
        'annotations.ns.arguments.b.required_when.a must name another enum argument',
    ),
    (
        {'ns': {'arguments': {'a': {'type': 'enum', 'values': ['x', 'y'], 'default': 'z'}}}},
        'annotations.ns.arguments.a.default must be one of x, y',
    ),
    (
        {'ns': {'arguments': {'a': {'type': 'enum', 'values': ['x', 'y']}}, 'data_size': {'words': {'a': {'x': 1}}}}},
        'annotations.ns.data_size.words.a has no entry for "y"',
    ),
    (
        {'ns': {'arguments': {'a': {'type': 'enum', 'values': ['x']}}, 'data_size': {'words': {'a': {'x': 1}, 'times': 'a'}}}},
        'annotations.ns.data_size.words.times must name an integer argument',
    ),
    (
        {'ns': {
            'arguments': {'a': {'type': 'enum', 'values': ['x']}, 'flag': {'type': 'boolean'}},
            'data_size': {'words': {'a': {'x': 1}, 'infer_times': 'flag'}},
        }},
        'annotations.ns.data_size.words.infer_times needs times, the argument it computes',
    ),
    (
        {'ns': {
            'arguments': {'a': {'type': 'enum', 'values': ['x']}, 'n': {'type': 'integer'}},
            'data_size': {'words': {'a': {'x': 1}, 'times': 'n', 'infer_times': 'n'}},
        }},
        'annotations.ns.data_size.words.infer_times must name a boolean argument',
    ),
    (
        {'ns': {
            'arguments': {'a': {'type': 'enum', 'values': ['x']}},
            'data_size': {'words': {'a': {'x': 1}}, 'terminated_when': {'a': ['x']}},
        }},
        'annotations.ns.data_size.terminated_when needs annotations.ns.data_size.words.times, the argument it computes',
    ),
    (
        {'ns': {
            'arguments': {'a': {'type': 'enum', 'values': ['x']}},
            'value_range': {'range': {'a': {'x': [0, 1]}}, 'terminated_when': {'a': ['x']}},
        }},
        'annotations.ns.value_range.terminated_when is only allowed in data_size',
    ),
    (
        {'ns': {
            'arguments': {'a': {'type': 'enum', 'values': ['x']}, 'n': {'type': 'integer'}},
            'data_size': {'words': {'a': {'x': 1}, 'times': 'n'}, 'terminated_when': {'n': [1]}},
        }},
        'annotations.ns.data_size.terminated_when.n must name another enum argument',
    ),
    (
        {'ns': {'applies_to': ['label'], 'value_range': {'range': [0, 1]}}},
        'annotations.ns.value_range only applies to constants',
    ),
    ({'ns': {'scopes': ['global', 'named']}}, 'annotations.ns.scopes must contain only global, file, local'),
    ({'ns': {'value_range': []}}, 'annotations.ns.value_range must be a rule or a non-empty list of rules'),
    (
        {'ns': {'value_range': [{'range': [0, 1]}, {'range': [2, 1]}]}},
        'annotations.ns.value_range[1].range must be a [min, max] pair',
    ),
    (
        {'ns': {'applies_to': ['label'], 'value_range': [{'range': [0, 1]}]}},
        'annotations.ns.value_range only applies to constants',
    ),
])
def test_config_errors(tmp_path, annotations, expected):
    assert expected in _config_error(tmp_path, annotations)


def test_unknown_config_key_is_a_warning(tmp_path):
    annotations = {'ns': {'arguments': {'a': {'type': 'string', 'requried': True}}}}
    _, warnings, _ = _assemble(tmp_path, 'ld a, b, c\n', _write_config(tmp_path, annotations))
    assert 'annotations.ns.arguments.a.requried is not a recognized setting' in warnings
    assert 'did you mean "required"?' in warnings


def test_xmin_spec_example_config_loads(tmp_path):
    config_path = _xmin_config(tmp_path)
    assert os.path.exists(config_path)
    _, warnings, _ = _assemble(tmp_path, 'ld a, b, c\n', config_path)
    assert warnings == ''


# ---- continuing an #annotate line ----------------------------------------------------------

NOTE_ANNOTATION = {'arguments': {'note': {'type': 'string'}, 'n': {'type': 'integer'}}}


def _note_config(tmp_path) -> str:
    return _write_config(tmp_path, {'ns': NOTE_ANNOTATION})


def _note(tmp_path, source: str) -> dict:
    assembler, _, _ = _assemble(tmp_path, source, _note_config(tmp_path))
    return assembler.export_model.symbols[0].annotations['ns'].arguments


def test_value_split_across_continued_lines(tmp_path):
    source = '#annotate ns n=3 note= \\\n    "one\\n" \\\n  "two" \\\n    n=4\nx: .byte 0\n'
    with pytest.raises(SystemExit) as exc_info:
        _assemble(tmp_path, source, _note_config(tmp_path))
    # The joined directive is one line, so n given twice is an error, reported on line 1.
    assert 'line 1' in str(exc_info.value) and "argument 'n' is given more than once" in str(exc_info.value)
    SymbolScope._global_scope = None
    source = '#annotate ns n=3 note= \\\n    "one\\n" \\\n  "two"\nx: .byte 0\n'
    assert _note(tmp_path, source) == {'n': 3, 'note': 'one\ntwo'}


@pytest.mark.parametrize(('written', 'expected'), [
    ('"ab" "cd"', 'abcd'),
    ('"a\\"b"   "\\tc"', 'a"b\tc'),
    ('"a;b" "c"', 'a;bc'),
])
def test_adjacent_strings_are_one_value(tmp_path, written, expected):
    assert _note(tmp_path, f'#annotate ns note={written} n=1\nx: .byte 0\n') == {'note': expected, 'n': 1}


def test_comment_on_the_last_line_only(tmp_path):
    # A comment on the last line is allowed; on an earlier line it hides the \, ending the directive.
    assert _note(tmp_path, '#annotate ns \\\n    note="x" ; a comment \\\nx: .byte 0\n') == {'note': 'x'}
    SymbolScope._global_scope = None
    # Line 2 is not part of the directive, so it is parsed as code of its own.
    message = _assemble_error(tmp_path, '#annotate ns ; see C:\\dir\\\n    note="x"\nx: .byte 0\n', _note_config(tmp_path))
    assert 'line 2 - constant "note" is missing a value' in message


def test_backslash_inside_quotes_does_not_continue(tmp_path):
    message = _assemble_error(tmp_path, '#annotate ns note="abc \\\n    def"\nx: .byte 0\n', _note_config(tmp_path))
    assert "annotation 'ns': cannot parse argument" in message and 'line 1' in message


@pytest.mark.parametrize(('source', 'expected'), [
    ('#annotate ns \\\n\nx: .byte 0\n', '#annotate ends with \\ but line 2 is blank'),
    ('.byte 0\n#annotate ns note="a" \\\n', '#annotate ends with \\ but the file ends at line 2'),
    ('#annotate ns \\\n  note="a" \\\n   \nx: .byte 0\n', '#annotate ends with \\ but line 3 is blank'),
])
def test_continuation_needs_a_next_line(tmp_path, source, expected):
    message = _assemble_error(tmp_path, source, _note_config(tmp_path))
    assert expected in message
    first = source.split('\n').index(next(line for line in source.split('\n') if line.startswith('#annotate')))
    assert f'line {first + 1}' in message


def test_continued_annotation_binds_after_its_last_line(tmp_path):
    source = '#annotate ns \\\n    note="a"\n#annotate listing \\\n    heading="H"\nx: .byte 0\n'
    assembler, _, _ = _assemble(tmp_path, source, _note_config(tmp_path))
    symbol = assembler.export_model.symbols[0]
    assert symbol.name == 'x' and set(symbol.annotations) == {'ns', 'listing'}


@pytest.mark.parametrize(('condition', 'annotated'), [('1', True), ('0', False)])
def test_continued_annotation_in_a_conditional_block(tmp_path, condition, annotated):
    # The continuation line `#endif \` is text of the directive, never a preprocessor line.
    source = f'#if {condition}\n#annotate ns note= \\\n    "#endif"\nx: .byte 0\n#endif\ny: .byte 0\n'
    assembler, _, _ = _assemble(tmp_path, source, _note_config(tmp_path))
    names = [symbol.name for symbol in assembler.export_model.symbols]
    assert names == (['x'] if annotated else [])


def test_listing_shows_each_physical_line(tmp_path):
    source = '#annotate ns note= \\\n    "a" \\\n    "b" ; done\nx: .byte 7\n'
    source_path = tmp_path / 'main.asm'
    source_path.write_text(source)
    output_path = tmp_path / 'main.lst'
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        Assembler(
            str(source_path), _note_config(tmp_path), False, None, 0, None, 0,
            True, 'listing', str(output_path), 0, [], [],
        ).assemble_bytecode()
    rows = [line for line in output_path.read_text().split('\n') if line.strip()[:1].isdigit()]
    assert [row.split('|')[0].strip() for row in rows] == ['1', '2', '3', '4', '4']
    assert '#annotate ns note= \\' in rows[0]
    assert '"b"' in rows[2] and 'done' in rows[2]
    assert rows[1].split('|')[2].strip() == '' and rows[2].split('|')[2].strip() == ''
