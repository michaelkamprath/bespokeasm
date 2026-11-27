"""`bespokeasm migrate`: the rule engine, each rule kind, the dialect configuration, the command,
and the 6502 configurations' ca65 and vasm dialects, checked against bytes ca65 produced."""
import contextlib
import importlib.resources as pkg_resources
import io
import json

import pytest
from bespokeasm.__main__ import _HANDLERS
from bespokeasm.assembler.diagnostic_reporter import DiagnosticReporter
from bespokeasm.assembler.engine import Assembler
from bespokeasm.assembler.keywords import BYTECODE_DIRECTIVES_SET
from bespokeasm.assembler.keywords import COMPILER_DIRECTIVES_SET
from bespokeasm.assembler.keywords import PREPROCESSOR_DIRECTIVES_SET
from bespokeasm.assembler.line_object.instruction_line import InstructionLine
from bespokeasm.assembler.model import AssemblerModel
from bespokeasm.assembler.symbol_scope import SymbolScope
from bespokeasm.cli import build_cli
from bespokeasm.cli import config_migration_names
from bespokeasm.migrate.dialects import load_migrations
from bespokeasm.migrate.engine import migrate
from bespokeasm.migrate.isa import migration_context
from bespokeasm.migrate.lexer import mask_line
from bespokeasm.migrate.rules import LoadEnvironment
from bespokeasm.migrate.rules import MigrationContext
from click.testing import CliRunner

from test import config_files
from test.isa_configs import json_config_copy
from test.isa_configs import load_config
from test.isa_configs import write_json_config

FIXTURES = pkg_resources.files(config_files).joinpath('mos6502')
W65C02 = FIXTURES.joinpath('w65c02.yaml')
SAMPLES = json.loads(FIXTURES.joinpath('migrate-samples.json').read_text())
DIRECTIVES = frozenset(COMPILER_DIRECTIVES_SET | BYTECODE_DIRECTIVES_SET | PREPROCESSOR_DIRECTIVES_SET)
CONTEXT = MigrationContext(mnemonics=frozenset({'lda', 'sta', 'inc', 'dex', 'bne', 'beq', 'bra', 'jmp'}),
                           directive_names=DIRECTIVES | {'word', 'res'})


class ConfigError(Exception):
    pass


def _raise(path, problem):
    raise ConfigError(f'{path} {problem}')


ENV = LoadEnvironment(
    error=_raise,
    directive_spellings=frozenset({f'.{name}' for name in COMPILER_DIRECTIVES_SET | BYTECODE_DIRECTIVES_SET | {'word'}}
                                  | {f'#{name}' for name in PREPROCESSOR_DIRECTIVES_SET}),
)


def _dialect(*rules):
    return load_migrations({'test': {'rules': list(rules)}}, ENV)['test']


def _migrate(source: str, *rules):
    return migrate(source, _dialect(*rules), CONTEXT)


@pytest.fixture(autouse=True)
def _reset_assembler_state():
    InstructionLine.reset_instruction_pattern_cache()
    SymbolScope._global_scope = None
    yield
    SymbolScope._global_scope = None


def _assemble(tmp_path, source: str, start: int) -> bytes:
    (tmp_path / 'main.a65c').write_text(source)
    assembler = Assembler(
        str(tmp_path / 'main.a65c'), json_config_copy(W65C02, tmp_path), True, str(tmp_path / 'out.bin'),
        start, None, 0, False, None, None, 0, [], [],
    )
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        assembler.assemble_bytecode()
    return (tmp_path / 'out.bin').read_bytes()


def _model_context(model: AssemblerModel) -> MigrationContext:
    return migration_context(model)


# ---- the 6502 dialects ------------------------------------------------------------------


@pytest.mark.parametrize('dialect', ['ca65', 'vasm'])
def test_migrated_samples_assemble_to_the_same_bytes_as_ca65(tmp_path, dialect):
    model = AssemblerModel(json_config_copy(W65C02, tmp_path), 0, DiagnosticReporter())
    result = migrate(SAMPLES[dialect]['source'], model.migrations[dialect], _model_context(model))
    assert result.reported == []
    binary = _assemble(tmp_path, result.text, SAMPLES['origin'])
    assert binary.hex(' ').upper() == SAMPLES[dialect]['bytes']


def test_both_6502_configs_declare_the_same_dialects():
    configs = [load_config(FIXTURES.joinpath(name))['migrations'] for name in ('mos6502.yaml', 'w65c02.yaml')]
    assert configs[0] == configs[1]
    assert list(configs[0]) == ['ca65', 'vasm']


# ---- the line lexer ---------------------------------------------------------------------


def test_strings_and_comments_are_masked():
    masked, comment = mask_line("lda #';' ; a ; comment", False)
    assert masked[:comment] == 'lda #\0\0\0 '
    assert mask_line("  .byte 'IT''S'", True)[0] == '  .byte ' + '\0' * 7
    # Without doubled quotes, 'IT' and 'S' are two strings with S between them.
    assert mask_line("'IT''S'", False)[0] == '\0' * 4 + '\0' * 3


def test_rules_never_change_strings_or_comments():
    source = '  .include "@x.s"  ; @y and :+\n  lda #\'@\'\n'
    result = _migrate(source, {'rename_directives': {'include': '#include'}}, {'local_labels': {'prefix': '@'}},
                      'anonymous_labels')
    assert result.text == '  #include "@x.s"  ; @y and :+\n  lda #\'@\'\n'


# ---- each rule kind -----------------------------------------------------------------------


def test_rename_directives():
    source = '  .INCLUDE "a.s"\n  include "b.s"\n  .org $10\nbyt = 3\n  lda byt\n  .byt 1\n'
    result = _migrate(source, {'rename_directives': {'include': '#include', 'org': '.org', 'byt': '.byte'}})
    assert result.text.splitlines() == [
        '  #include "a.s"', '  #include "b.s"', '  .org $10', 'byt = 3', '  lda byt', '  .byte 1',
    ]
    # `.org` was already `.org`; the assignment and the operand are not directives.
    assert [count.lines for count in result.rule_counts] == [3]


def test_a_rename_may_give_its_target_fixed_arguments():
    assert _migrate('  even\n', {'rename_directives': {'even': '.align 2'}}).text == '  .align 2\n'
    with pytest.raises(ConfigError, match='must name a BespokeASM directive'):
        _migrate('', {'rename_directives': {'even': 'align 2'}})


def test_an_origin_after_bytes_becomes_a_phase():
    source = '; top\n.org $8000\n#include "x.s"\n.org $8000\n  lda 1\n.org $0200\nram: .byte 1\n.dephase\n.org $9000\n'
    assert _migrate(source, 'origin_phases').text.splitlines() == [
        '; top', '.org $8000', '#include "x.s"', '.org $8000', '  lda 1', '.phase $0200', 'ram: .byte 1', '.dephase',
        '.phase $9000',
    ]


def test_a_bare_word_that_is_a_mnemonic_is_not_renamed():
    result = _migrate('  inc\n  .inc "x"\n', {'rename_directives': {'inc': '#include'}})
    assert result.text == '  inc\n  #include "x"\n'


def test_drop_directives_comment_the_line_out():
    result = _migrate('  .setcpu "65C02"\n  lda #1\n', {'drop_directives': ['setcpu']})
    assert result.text == '  ; .setcpu "65C02"\n  lda #1\n'
    assert result.reported == []


def test_unsupported_directives_and_blocks_are_reported():
    source = (
        '.segment "CODE"\n'
        '.macro twice value\n'
        '  lda value\n'
        '.endmacro\n'
        '  twice 3\n'
        '  lda #1\n'
    )
    result = _migrate(source, {'unsupported': ['segment', {'macro': ['endmacro', 'endmac']}]})
    lines = result.text.splitlines()
    assert lines[0] == '; MIGRATE: .segment is not supported: .segment "CODE"'
    assert lines[2] == '; MIGRATE: inside the .macro on line 2:   lda value'
    assert lines[4] == '; MIGRATE: uses twice, defined by the .macro on line 2:   twice 3'
    assert lines[5] == '  lda #1'
    # The block is summarized by its first line.
    assert [line.number for line in result.reported] == [1, 2, 5]
    assert result.reported_line_count == 5


def test_local_labels_with_a_prefix_or_suffix():
    assert _migrate('@loop: dex\n  bne @loop\n', {'local_labels': {'prefix': '@'}}).text == '.loop: dex\n  bne .loop\n'
    assert _migrate('1$ dex\n  bne 1$\n  lda #$10\n', {'local_labels': {'suffix': '$'}}).text == (
        '.1 dex\n  bne .1\n  lda #$10\n'
    )


def test_a_local_label_that_would_become_a_directive_is_reported():
    result = _migrate('@byte: dex\n', {'local_labels': {'prefix': '@'}})
    assert result.reported[0].reports == ['@byte would become the directive .byte; rename it']


def test_anonymous_labels_get_local_names():
    source = ':   lda $10\n    beq :+\n    bra :-\n:   bne :--\n    beq :>\n:   dex\n'
    result = _migrate(source, 'anonymous_labels')
    assert result.text.splitlines() == [
        '.anon_1:   lda $10', '    beq .anon_2', '    bra .anon_1', '.anon_2:   bne .anon_1', '    beq .anon_3',
        '.anon_3:   dex',
    ]


def test_an_anonymous_reference_across_a_label_is_reported():
    result = _migrate(':   dex\nnext: bne :-\n  beq :+\n', 'anonymous_labels')
    assert [(line.number, line.reports) for line in result.reported] == [
        (2, [':- crosses next; give its anonymous label a name']),
        (3, [':+ has no anonymous label to refer to']),
    ]


def test_anonymous_label_names_avoid_names_in_use():
    result = _migrate('anon_1 = 4\n:   bne :-\n', 'anonymous_labels')
    assert result.text == 'anon_1 = 4\n.anon__1:   bne .anon__1\n'


def test_colonless_labels():
    source = 'start lda #1\nCOUNT equ 3\nMAX = 4\n.loop\n  dex\n.org $10\n'
    assert _migrate(source, 'colonless_labels').text == 'start: lda #1\nCOUNT equ 3\nMAX = 4\n.loop:\n  dex\n.org $10\n'


def test_origin_assignment():
    assert _migrate('  *= $8000\n* = $9000\n', {'origin_assignment': {'symbol': '*'}}).text == (
        '  .org $8000\n.org $9000\n'
    )


def test_operand_prefixes():
    rule = {'operand_prefixes': {'drop': ['z:'], 'unsupported': ['a:']}}
    result = _migrate('  lda z:ptr\nz: lda a:ptr\n', rule)
    assert result.lines[0].text == '  lda ptr'
    assert result.reported[0].reports == ['the a: operand prefix is not supported']


def test_current_address_symbol():
    result = _migrate('  bne $\n  lda #$7C\n  .word $ + 2\n', {'current_address_symbol': {'symbol': '$'}})
    assert result.text == '  bne *\n  lda #$7C\n  .word * + 2\n'


def test_string_escapes():
    result = _migrate("  .byte 'IT''S', \"A\"\"B\" ; it''s\n", {'string_escapes': {'doubled_quotes': True}})
    assert result.text == "  .byte 'IT\\'S', \"A\\\"B\" ; it''s\n"


def test_assignment_operators():
    result = _migrate('COUNT := 3\nMAX set 4\n  lda #COUNT\n', {'assignment_operators': [':=', 'set']})
    assert result.text == 'COUNT = 3\nMAX = 4\n  lda #COUNT\n'


def test_includes_are_noted_not_reported():
    result = _migrate('  .include "lib.s"\n', {'rename_directives': {'include': '#include'}})
    assert result.reported == []
    assert result.noted[0].notes == ['includes lib.s; migrate it separately']


def test_line_endings_and_a_missing_final_newline_are_kept():
    rule = {'drop_directives': ['p02']}
    assert _migrate('  .p02\r\n  lda #1\r\n', rule).text == '  ; .p02\r\n  lda #1\r\n'
    assert _migrate('  lda #1', rule).text == '  lda #1'


# ---- configuration errors --------------------------------------------------------------------


@pytest.mark.parametrize(('section', 'message'), [
    ({'x': {'rules': ['no_such_rule']}}, 'migrations.x.rules[0] "no_such_rule" is not a migration rule'),
    ({'x': {'rules': [{'rename_directives': {'org': 'org'}}]}}, 'must name a BespokeASM directive'),
    ({'x': {'rules': [{'local_labels': {'prefix': '@', 'suffix': '$'}}]}}, 'takes either "prefix" or "suffix"'),
    ({'x': {'rules': [{'local_labels': {'start': '@'}}]}}, 'migrations.x.rules[0].local_labels.start is not a parameter'),
    ({'x': {'rules': [{'anonymous_labels': {'style': 'colon'}}]}}, 'takes no parameters'),
    ({'x': {'rules': []}}, 'migrations.x.rules must be a list with at least one rule'),
    ({'x': {'rules': ['colonless_labels'], 'notes': 'y'}}, 'migrations.x.notes is not a dialect setting'),
    ({'x': {'rules': [{'unsupported': [{'macro': 3}]}]}}, "must name a block's first and last directives"),
])
def test_bad_migrations_are_config_errors(section, message):
    with pytest.raises(ConfigError, match=message.replace('[', r'\[').replace(']', r'\]')):
        load_migrations(section, ENV)


def test_the_model_reports_a_bad_migration_by_config_path(tmp_path):
    config = load_config(W65C02)
    rules = config['migrations']['ca65']['rules']
    rules.append({'rename_directives': {'org': '.origin'}})
    with pytest.raises(SystemExit) as info:
        AssemblerModel(write_json_config(config, tmp_path), 0, DiagnosticReporter())
    path = f'migrations.ca65.rules[{len(rules) - 1}].rename_directives.org'
    assert f'{path} must name a BespokeASM directive' in str(info.value)


def test_a_rename_may_target_a_directive_alias(tmp_path):
    config = load_config(W65C02)
    config['migrations'] = {'x': {'rules': [{'rename_directives': {'dw': '.word'}}]}}
    model = AssemblerModel(write_json_config(config, tmp_path), 0, DiagnosticReporter())
    assert list(model.migrations) == ['x']


# ---- the command --------------------------------------------------------------------------------


def _run(args):
    return CliRunner().invoke(build_cli(_HANDLERS), ['migrate', *args])


def test_migrate_without_from_lists_the_dialects(tmp_path):
    (tmp_path / 'a.s').write_text('  lda #1\n')
    result = _run(['-c', str(W65C02), str(tmp_path / 'a.s')])
    assert result.exit_code == 2
    assert 'can migrate source from these assemblers' in result.output
    assert '  ca65: ' in result.output and '  vasm: ' in result.output
    result = _run(['-c', str(W65C02), '--from', 'ca66', str(tmp_path / 'a.s')])
    assert '"ca66" is not one of them' in result.output


def test_migrate_writes_the_output_and_reports_to_stderr(tmp_path):
    source = tmp_path / 'a.s'
    source.write_text('.segment "CODE"\n@x: dex\n  bne @x\n')
    result = _run(['-c', str(W65C02), '--from', 'ca65', str(source), '-o', str(tmp_path / 'a.a65c')])
    assert result.exit_code == 1
    assert (tmp_path / 'a.a65c').read_text() == (
        '; MIGRATE: .segment is not supported: .segment "CODE"\n.x: dex\n  bne .x\n'
    )
    assert 'a.s:1: .segment is not supported' in result.stderr
    assert '  local_labels: 2 lines' in result.stderr


def test_migrate_writes_to_stdout_and_exits_0_when_nothing_is_reported(tmp_path):
    source = tmp_path / 'a.s'
    source.write_text('@x: dex\n')
    result = _run(['-c', str(W65C02), '--from', 'ca65', str(source)])
    assert result.exit_code == 0
    assert result.stdout == '.x: dex\n'


def test_migrate_never_overwrites_its_input(tmp_path):
    source = tmp_path / 'a.s'
    source.write_text('@x: dex\n')
    result = _run(['-c', str(W65C02), '--from', 'ca65', str(source), '-o', str(source)])
    assert result.exit_code == 2
    assert 'never overwrites its input' in result.output
    assert source.read_text() == '@x: dex\n'


def test_dialect_names_for_shell_completion(tmp_path):
    assert config_migration_names(str(W65C02)) == ['ca65', 'vasm']
    path = tmp_path / 'isa.json'
    path.write_text(json.dumps({'migrations': {'a-b': {}, 'c': {}}}))
    assert config_migration_names(str(path)) == ['a-b', 'c']


def test_generated_docs_list_the_dialects(tmp_path):
    from bespokeasm.docsgen import DocumentationGenerator
    output = tmp_path / 'isa.md'
    DocumentationGenerator(json_config_copy(W65C02, tmp_path), 0).generate_markdown_documentation(str(output))
    text = output.read_text()
    assert '# Source Migration' in text
    assert '| `ca65` | cc65\'s ca65 assembler.' in text
