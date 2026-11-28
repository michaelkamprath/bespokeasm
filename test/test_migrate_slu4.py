"""`bespokeasm migrate` for element-syntax sources: the rule kinds that Carsten Herting's Minimal
assemblers need, and the slu4 dialect, checked against bytes his assembler produced."""
import contextlib
import importlib.resources as pkg_resources
import io
import json

import pytest
from bespokeasm.assembler.diagnostic_reporter import DiagnosticReporter
from bespokeasm.assembler.engine import Assembler
from bespokeasm.assembler.keywords import BYTECODE_DIRECTIVES_SET
from bespokeasm.assembler.keywords import COMPILER_DIRECTIVES_SET
from bespokeasm.assembler.keywords import PREPROCESSOR_DIRECTIVES_SET
from bespokeasm.assembler.line_object.instruction_line import InstructionLine
from bespokeasm.assembler.model import AssemblerModel
from bespokeasm.assembler.symbol_scope import SymbolScope
from bespokeasm.migrate.dialects import load_migrations
from bespokeasm.migrate.engine import migrate
from bespokeasm.migrate.isa import instruction_shapes
from bespokeasm.migrate.isa import InstructionShape
from bespokeasm.migrate.isa import migration_context
from bespokeasm.migrate.lexer import elements
from bespokeasm.migrate.rules import LoadEnvironment
from bespokeasm.migrate.rules import MigrationContext
from intelhex import IntelHex

from test import config_files
from test.isa_configs import json_config_copy

FIXTURES = pkg_resources.files(config_files).joinpath('slu4')
SUBSET = FIXTURES.joinpath('minimal-64x4-subset.yaml')
SAMPLE = json.loads(FIXTURES.joinpath('migrate-sample.json').read_text())

DIRECTIVES = frozenset(COMPILER_DIRECTIVES_SET | BYTECODE_DIRECTIVES_SET | PREPROCESSOR_DIRECTIVES_SET)
SHAPES = {
    'nop': InstructionShape(0, 0x00),
    'rts': InstructionShape(0, 0x69),
    'ldi': InstructionShape(1, 0x74),
    'jpa': InstructionShape(1, 0x64),
    'jps': InstructionShape(1, 0x67),
    'inw': InstructionShape(1, 0x98),
    'mib': InstructionShape(2, 0x87),
    'aiw': InstructionShape(2, 0xb4),
    'or.b': InstructionShape(1, 0x4b),
    'mac': InstructionShape(1, None),
}
CONTEXT = MigrationContext(mnemonics=frozenset(SHAPES), directive_names=DIRECTIVES, shapes=SHAPES)


class ConfigError(Exception):
    pass


def _raise(path, problem):
    raise ConfigError(f'{path} {problem}')


ENV = LoadEnvironment(
    error=_raise,
    directive_spellings=frozenset({f'.{name}' for name in COMPILER_DIRECTIVES_SET | BYTECODE_DIRECTIVES_SET}
                                  | {f'#{name}' for name in PREPROCESSOR_DIRECTIVES_SET}),
)


def _migrate(source: str, *rules):
    return migrate(source, load_migrations({'test': {'rules': list(rules)}}, ENV)['test'], CONTEXT)


@pytest.fixture(autouse=True)
def _reset_assembler_state():
    InstructionLine.reset_instruction_pattern_cache()
    SymbolScope._global_scope = None
    yield
    SymbolScope._global_scope = None


# ---- the slu4 dialect, end to end ----------------------------------------------------------


def test_sample_assembles_to_the_same_bytes_as_carstens_assembler(tmp_path):
    config = json_config_copy(SUBSET, tmp_path)
    model = AssemblerModel(config, 0, DiagnosticReporter())
    result = migrate(SAMPLE['source'], model.migrations['slu4'], migration_context(model))
    assert result.reported == []
    (tmp_path / 'main.min64x4').write_text(result.text)
    assembler = Assembler(
        str(tmp_path / 'main.min64x4'), config, False, None, 0, None, 0,
        True, 'intel_hex', str(tmp_path / 'out.hex'), 0, [], [],
    )
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        assembler.assemble_bytecode()
    expected = IntelHex(io.StringIO(SAMPLE['intel_hex']))
    actual = IntelHex(str(tmp_path / 'out.hex'))
    assert actual.todict() == expected.todict()


def test_programs_are_phased_and_the_filler_dephased():
    text = _migrate(
        '#org 0x0400\n'
        '"one", 0, OneStart\n'
        '  #mute\n  #org 0xfc00\n  #emit\n'
        '  OneStart: NOP\n'
        '0, 0x0500-*-2\n',
        'split_statements', {'bare_data': {'sizing': 'slu4'}}, 'muted_origin',
    ).text
    assert text.splitlines() == [
        '#org 0x0400',
        '.byte "one", 0',
        '.2byte OneStart',
        '  ; #mute',
        '  .phase 0xfc00',
        '  ; #emit',
        '  OneStart: NOP',
        '.dephase',
        '.byte 0',
        '.2byte 0x0500-*-2',
    ]


# ---- elements ---------------------------------------------------------------------------------


def test_elements_are_separated_by_whitespace_and_commas_and_quotes_have_no_escapes():
    assert [e.text for e in elements('MIW 0x1234,0xfffc  "a, b" "\\" \'"\'')] == [
        'MIW', '0x1234', '0xfffc', '"a, b"', '"\\"', '\'"\'',
    ]


# ---- split_statements ---------------------------------------------------------------------


def test_directives_labels_and_data_get_their_own_lines_while_instructions_stay_together():
    result = _migrate(
        '#org 0x0080     xa: steps: 0xffff   ; comment\n'
        'start:  NOP RTS 0x12 LDI 5\n',
        'split_statements',
    )
    assert result.text.splitlines() == [
        '#org 0x0080                         ; comment',
        '                xa:',
        '                    steps: 0xffff',
        'start:  NOP RTS',
        '        0x12',
        '        LDI 5',
    ]


def test_a_label_after_an_origin_stays_on_its_line():
    assert _migrate('#org 0x0080     PtrA:   ; pointer\n#org 0x0083 a: b:\n', 'split_statements').text.splitlines() == [
        '#org 0x0080     PtrA:   ; pointer', '#org 0x0083', '            a:', '               b:',
    ]


def test_a_label_before_a_directive_stands_alone():
    assert _migrate('Image: #mute #org 0xf000 #emit\n', 'split_statements').text.splitlines() == [
        'Image:', '       #mute', '             #org 0xf000', '                         #emit',
    ]


def test_operands_without_commas_get_them():
    assert _migrate('  MIB 0xfe 0xffff\n', 'split_statements').text == '  MIB 0xfe, 0xffff\n'


def test_operands_on_the_next_line_join_their_instruction():
    assert _migrate('  JPA\n  0x1234 NOP\n', 'split_statements').text.splitlines() == ['  JPA 0x1234', '  NOP']


def test_a_label_on_an_operand_becomes_an_operand_label():
    result = _migrate(
        '  loop:  LDI\n'
        '  value: 0xff MIB 0xfe,0xffff\n'
        '  MIB 0x12 target: 0xffff\n'
        '  JPA value JPA target\n',
        'split_statements',
    )
    assert result.text.splitlines() == [
        '  loop:  LDI @value: 0xff',
        '         MIB 0xfe,0xffff',
        '  MIB 0x12, @target: 0xffff',
        '  JPA value JPA target',
    ]
    assert result.reported == []


def test_an_operand_takes_one_operand_label():
    result = _migrate('  LDI\n  one: two: 5\n', 'split_statements')
    assert [line.reports for line in result.reported] == [[
        'one: names an operand of LDI, which can have one operand label',
        'two: names an operand of LDI, which can have one operand label',
    ]]


def test_a_mnemonic_in_an_expression_or_as_an_operand_is_its_opcode():
    result = _migrate('  MIB AIW+0,0x10 LDI INW\n', 'split_statements')
    assert result.text == '  MIB 0xb4+0,0x10 LDI 0x98\n'
    assert result.noted[0].notes == ['AIW is its opcode, 0xb4', 'INW is its opcode, 0x98']


def test_missing_operands_are_reported():
    assert _migrate('  JPA #org 0x10\n', 'split_statements').reported[0].reports == [
        'JPA has fewer operands here than the instruction set gives it',
    ]
    assert _migrate('  JPA\n', 'split_statements').reported[0].reports == ['JPA is missing operands at the end of the file']


# ---- bare_data ---------------------------------------------------------------------------------


@pytest.mark.parametrize(('element', 'size'), [
    ('0xff', 1), ('0x0ff', 2), ('255', 1), ('256', 2), ('-128', 1), ('-129', 2), ('label', 2), ('*', 2),
    ('<label', 1), ('>label+1', 1), ('"a"', 1), ("'a'", 1), ('"text"', 1), ('NOP+1', 1), ('label-0x01', 2),
])
def test_bare_data_sizes_each_element_as_carstens_assembler_does(element, size):
    text = _migrate(f'{element}\n', {'bare_data': {'sizing': 'slu4'}}).text
    assert text == f'{".byte" if size == 1 else ".2byte"} {element}\n'


def test_bare_data_groups_elements_of_one_size_and_keeps_the_source_spacing():
    result = _migrate('table:  "ab", 0,    1, label,  2 3 ; comment\n', {'bare_data': {'sizing': 'slu4'}})
    assert result.text.splitlines() == [
        'table:  .byte "ab", 0,    1        ; comment',
        '        .2byte label',
        '        .byte 2, 3',
    ]


def test_bare_data_leaves_instructions_and_directives_alone():
    source = 'NOP 0x12\n#org 0x10\n.byte 1\n'
    assert _migrate(source, {'bare_data': {'sizing': 'slu4'}}).text == source


def test_bare_data_needs_a_known_sizing():
    with pytest.raises(ConfigError, match=r'bare_data.sizing must be one of slu4'):
        _migrate('', {'bare_data': {'sizing': 'other'}})


# ---- strings and characters ------------------------------------------------------------------


def test_backslashes_become_escapes_and_single_characters_become_character_literals():
    result = _migrate(
        '  LDI "\\" LDI "\'" LDI \'"\' LDI "a"+1\n  .byte "C:\\dir", \'\\\'\n',
        {'string_escapes': {'backslash': 'literal'}},
        {'char_literals': {'double_quoted': True}},
    )
    assert result.text.splitlines() == [
        "  LDI '\\\\' LDI '\\'' LDI '\"' LDI 'a'+1",
        "  .byte \"C:\\\\dir\", '\\\\'",
    ]


def test_an_escaped_character_keeps_its_escape_where_backslashes_are_escapes():
    # Without `backslash: literal`, `"\n"` is a line feed, and so is `'\n'`.
    result = _migrate(
        '  .byte "\\n", "\\t", "\\0", "\\\\", "\\"", "\\\'", "\\", "ab"\n',
        {'char_literals': {'double_quoted': True}},
    )
    assert result.text.splitlines() == [
        "  .byte '\\n', '\\t', '\\0', '\\\\', '\\\"', '\\'', \"\\\", \"ab\"",
    ]


def test_string_escapes_needs_a_setting():
    with pytest.raises(ConfigError, match='string_escapes must be a mapping with at least one entry'):
        _migrate('', {'string_escapes': {}})
    with pytest.raises(ConfigError, match='backslash must be "literal"'):
        _migrate('', {'string_escapes': {'backslash': 'escape'}})


# ---- terminated_strings ------------------------------------------------------------------


def _strings(source: str, embedded: bool = True):
    context = MigrationContext(
        mnemonics=CONTEXT.mnemonics, directive_names=DIRECTIVES, shapes=SHAPES, embedded_strings=embedded,
    )
    dialect = load_migrations({'t': {'rules': [
        'split_statements', {'bare_data': {'sizing': 'slu4'}}, {'string_escapes': {'backslash': 'literal'}},
        {'char_literals': {'double_quoted': True}}, 'terminated_strings',
    ]}}, ENV)['t']
    return migrate(source, dialect, CONTEXT if embedded is None else context)


def test_terminated_strings_become_cstr_or_embedded_strings():
    result = _strings(
        'name: "C:\\", 0  ; file\n'
        '  JPS print "Hi", 10, 13, 9, 0 NOP  ; greet\n'
        "  'say \"x\"', 0\n"
    )
    assert result.text.splitlines() == [
        'name: .cstr "C:\\\\"    ; file',
        '  JPS print "Hi\\n\\r\\t"              ; greet',
        '  NOP',
        '  .cstr "say \\"x\\""',
    ]


def test_string_data_without_a_backslash_still_becomes_cstr():
    # string_escapes clears a line's literal-backslash lexing even when it changes nothing;
    # terminated_strings skips lines still lexed that way, so this line must convert too.
    result = _strings('  "Ready", 0\n')
    assert result.text.splitlines() == ['  .cstr "Ready"']


def test_other_string_data_stays_byte_data():
    result = _strings('  27, "[H", 0\n  "ab", 0, "cd", 0\n  "ab", 1\n  JPS print "x", label, 0\n')
    assert result.text.splitlines() == [
        '  .byte 27, "[H", 0',
        '  .byte "ab", 0, "cd", 0',
        '  .byte "ab", 1',
        '  JPS print',
        "  .byte 'x'",
        '  .2byte label',
        '  .byte 0',
    ]


def test_without_embedded_strings_data_after_an_instruction_becomes_cstr():
    assert _strings('  JPS print "Hi", 0\n', embedded=False).text.splitlines() == ['  JPS print', '  .cstr "Hi"']


# ---- muted_origin ---------------------------------------------------------------------------------


def _muted(source: str, **params):
    return _migrate(source, 'split_statements', {'muted_origin': params or None})


def test_an_origin_set_while_muted_becomes_a_phase():
    assert _muted('Start: #mute #org 0xf000 #emit\n  NOP\n').text.splitlines() == [
        'Start:', '       .phase 0xf000', '  NOP',
    ]
    assert _muted('#mute\n#org 0xfc00 ; app\n#emit\nNOP\n').text.splitlines() == [
        '; #mute', '.phase 0xfc00 ; app', '; #emit', 'NOP',
    ]


def test_a_muted_region_followed_by_an_origin_or_nothing_is_left_alone():
    source = '#mute\n#org 0x80\nvar: 0xff\n#emit\n#org 0x1000\nNOP\n'
    assert _muted(source).text == source
    assert _muted('#mute\n#org 0x80\nvar:\n#emit\n').text == '#mute\n#org 0x80\nvar:\n#emit\n'


def test_bytes_after_a_muted_region_with_data_are_reported():
    result = _muted('#mute\n#org 0x80\nvar: 0xff\n#emit\nNOP\n')
    assert result.reported[0].reports[0].startswith('the bytes after this #emit go where they were going at the #mute')


def test_muting_does_not_nest():
    assert _muted('#mute\n#mute\n#emit\n#emit\n').text.splitlines() == ['#mute', '; #mute', '#emit', '; #emit']


def test_the_current_address_inside_a_phase_is_dephased_or_reported():
    dephased = _muted('#mute #org 0xfc00 #emit\nNOP\n0, *\n')
    assert dephased.text.splitlines()[-2:] == ['.dephase', '0, *']
    reported = _muted('#mute #org 0xfc00 #emit\nJPA *\nNOP\n')
    assert reported.reported[0].reports == ['"*" here is where the bytes go, which is not the address inside this .phase']


def test_image_start_places_bytes_before_the_first_origin():
    assert _muted('NOP\n', image_start=0x2000).text.splitlines() == ['.org 0x2000', '.phase 0x0000', 'NOP']
    assert _muted('0x12\n', image_start=0x2000).text.splitlines() == ['.org 0x2000', '0x12']
    assert _muted('NOP\n', image_start=0).text.splitlines() == ['.org 0x0000', 'NOP']
    assert _muted('#org 0x100\nNOP\n', image_start=0x2000).text == '#org 0x100\nNOP\n'


def test_image_start_must_be_an_address():
    with pytest.raises(ConfigError, match='image_start must be an address'):
        _muted('', image_start='high')


# ---- instruction shapes ---------------------------------------------------------------------------


def test_instruction_shapes_come_from_the_configuration():
    shapes = instruction_shapes({
        'instructions': {
            'mov': {'aliases': ['cpy'], 'bytecode': {'value': 0x12, 'size': 8}, 'operands': {'count': 2}},
            'sfx': {'bytecode': {'value': 1, 'size': 4, 'suffix': {'value': 2, 'size': 4}}},
            'two': {
                'bytecode': {'value': 2, 'size': 8},
                'variants': [{'bytecode': {'value': 3, 'size': 8}, 'operands': {'count': 1}}],
            },
            'alt': {
                'bytecode': {'value': 4, 'size': 8}, 'operands': {'count': 1},
                'variants': [{'bytecode': {'value': 5, 'size': 8}, 'operands': {'count': 1}}],
            },
        },
        'macros': {'push2': [{'operands': {'count': 2}, 'instructions': ['nop']}]},
    })
    assert shapes['mov'] == shapes['cpy'] == InstructionShape(2, 0x12)
    assert shapes['sfx'] == InstructionShape(0, None)
    assert 'two' not in shapes
    assert shapes['alt'] == InstructionShape(1, None)
    assert shapes['push2'].operand_count == 2
