"""Tests for the directive_docs hover strings module."""
import importlib.resources as pkg_resources

from bespokeasm.assembler.diagnostic_reporter import DiagnosticReporter
from bespokeasm.assembler.keywords import BUILTIN_CONSTANTS_SET
from bespokeasm.assembler.keywords import BYTECODE_DIRECTIVES_SET
from bespokeasm.assembler.keywords import COMPILER_DIRECTIVES_SET
from bespokeasm.assembler.keywords import EXPRESSION_FUNCTIONS_SET
from bespokeasm.assembler.keywords import PREPROCESSOR_DIRECTIVES_SET
from bespokeasm.assembler.line_object.instruction_line import InstructionLine
from bespokeasm.assembler.model import AssemblerModel
from bespokeasm.assembler.symbol_scope import SymbolScope
from bespokeasm.configgen.hover_docs import build_hover_docs
from bespokeasm.docsgen.directive_docs import ALL_DIRECTIVE_DOCS
from bespokeasm.docsgen.directive_docs import BUILTIN_CONSTANT_DOCS
from bespokeasm.docsgen.directive_docs import BYTECODE_DIRECTIVE_DOCS
from bespokeasm.docsgen.directive_docs import COMPILER_DIRECTIVE_DOCS
from bespokeasm.docsgen.directive_docs import COUNTER_COORDINATE_DOCS
from bespokeasm.docsgen.directive_docs import directive_alias_docs
from bespokeasm.docsgen.directive_docs import EXPRESSION_FUNCTION_DOCS
from bespokeasm.docsgen.directive_docs import PREPROCESSOR_DIRECTIVE_DOCS

from test import config_files


def test_all_compiler_directives_have_docs():
    for name in COMPILER_DIRECTIVES_SET:
        assert name in COMPILER_DIRECTIVE_DOCS, f'missing doc for compiler directive: {name}'


def test_all_bytecode_directives_have_docs():
    for name in BYTECODE_DIRECTIVES_SET:
        assert name in BYTECODE_DIRECTIVE_DOCS, f'missing doc for bytecode directive: {name}'


def test_all_preprocessor_directives_have_docs():
    for name in PREPROCESSOR_DIRECTIVES_SET:
        assert name in PREPROCESSOR_DIRECTIVE_DOCS, f'missing doc for preprocessor directive: {name}'


def test_all_built_in_symbols_have_docs():
    assert set(BUILTIN_CONSTANT_DOCS) == BUILTIN_CONSTANTS_SET


def test_language_symbol_hovers_give_the_instruction_set_values():
    InstructionLine.reset_instruction_pattern_cache()
    SymbolScope._global_scope = None
    config = str(pkg_resources.files(config_files).joinpath('kenbak', 'kenbak-1-isa.yaml'))
    constants = build_hover_docs(AssemblerModel(config, 0, DiagnosticReporter()))['predefined']['constants']
    for name, value in {
        '__LANGUAGE_NAME__': 'kenbak-1',
        '__LANGUAGE_VERSION__': '1.1.0',
        '__LANGUAGE_VERSION_MAJOR__': '1',
        '__LANGUAGE_VERSION_MINOR__': '1',
        '__LANGUAGE_VERSION_PATCH__': '0',
    }.items():
        assert constants[name].endswith(f'\n\nFor this instruction set it is `{value}`.'), name
    # The assembling BespokeASM is not known when the extension is generated.
    assert 'For this instruction set' not in constants['__BESPOKEASM_VERSION__']


def test_directive_alias_docs_use_the_target_documentation():
    docs = directive_alias_docs({'word': '2byte', 'res': 'fill'})
    assert set(docs) == {'word', 'res'}
    assert docs['word'].startswith(
        '### `.word` : Same as `.2byte`\n\n---\n\n'
        'In this instruction set, `.word` is another name for `.2byte`.\n\n'
    )
    # The target's body follows, without its own heading.
    target_body = BYTECODE_DIRECTIVE_DOCS['fill'].split('---\n\n', 1)[1]
    assert docs['res'].endswith(target_body)
    assert '### `.fill`' not in docs['res']
    assert directive_alias_docs({}) == {}


def test_hovers_include_the_instruction_sets_directive_aliases(tmp_path):
    from ruamel.yaml import YAML
    InstructionLine.reset_instruction_pattern_cache()
    SymbolScope._global_scope = None
    source = pkg_resources.files(config_files).joinpath('test_default_numeric_base.yaml')
    with open(source) as handle:
        config = YAML(typ='safe').load(handle)
    config['general']['directive_aliases'] = {'word': '2byte'}
    config_path = tmp_path / 'isa.yaml'
    with open(config_path, 'w') as handle:
        YAML().dump(config, handle)
    data_types = build_hover_docs(AssemblerModel(str(config_path), 0, DiagnosticReporter()))['directives']['data_type']
    assert set(data_types) == set(BYTECODE_DIRECTIVE_DOCS) | {'word'}
    assert data_types['word'] == directive_alias_docs({'word': '2byte'})['word']


def test_all_expression_functions_have_docs():
    for name in EXPRESSION_FUNCTIONS_SET:
        assert name in EXPRESSION_FUNCTION_DOCS, f'missing doc for expression function: {name}'


def test_counter_coordinate_declaration_has_docs():
    """The `:=` declaration ships with M2 and must carry hover documentation.

    Unlike directives and expression functions, `:=` has no keyword-set entry
    to iterate, so its docs coverage is asserted directly here — previously
    nothing in docsgen enforced it.
    """
    assert ':=' in COUNTER_COORDINATE_DOCS, 'missing doc for the := coordinate declaration'


def test_all_directive_docs_is_union():
    # COUNTER_COORDINATE_DOCS is part of the aggregate: a consumer of
    # ALL_DIRECTIVE_DOCS must not silently miss the `:=` declaration.
    expected = (
        set(COMPILER_DIRECTIVE_DOCS)
        | set(BYTECODE_DIRECTIVE_DOCS)
        | set(PREPROCESSOR_DIRECTIVE_DOCS)
        | set(COUNTER_COORDINATE_DOCS)
    )
    assert set(ALL_DIRECTIVE_DOCS) == expected


def test_directive_docs_are_nonempty_strings():
    for name, doc in ALL_DIRECTIVE_DOCS.items():
        assert isinstance(doc, str), f'{name} doc is not a string'
        assert len(doc) > 10, f'{name} doc is too short'


def test_directive_docs_contain_heading():
    for name, doc in ALL_DIRECTIVE_DOCS.items():
        assert doc.startswith('### '), f'{name} doc should start with markdown heading'


def test_no_duplicate_keys_across_categories():
    compiler_keys = set(COMPILER_DIRECTIVE_DOCS)
    bytecode_keys = set(BYTECODE_DIRECTIVE_DOCS)
    preprocessor_keys = set(PREPROCESSOR_DIRECTIVE_DOCS)
    assert compiler_keys.isdisjoint(bytecode_keys), 'compiler and bytecode overlap'
    assert compiler_keys.isdisjoint(preprocessor_keys), 'compiler and preprocessor overlap'
    assert bytecode_keys.isdisjoint(preprocessor_keys), 'bytecode and preprocessor overlap'
