"""Tests for the directive_docs hover strings module."""
from bespokeasm.assembler.keywords import BYTECODE_DIRECTIVES_SET
from bespokeasm.assembler.keywords import COMPILER_DIRECTIVES_SET
from bespokeasm.assembler.keywords import PREPROCESSOR_DIRECTIVES_SET
from bespokeasm.docsgen.directive_docs import ALL_DIRECTIVE_DOCS
from bespokeasm.docsgen.directive_docs import BYTECODE_DIRECTIVE_DOCS
from bespokeasm.docsgen.directive_docs import COMPILER_DIRECTIVE_DOCS
from bespokeasm.docsgen.directive_docs import PREPROCESSOR_DIRECTIVE_DOCS


def test_all_compiler_directives_have_docs():
    for name in COMPILER_DIRECTIVES_SET:
        assert name in COMPILER_DIRECTIVE_DOCS, f'missing doc for compiler directive: {name}'


def test_all_bytecode_directives_have_docs():
    for name in BYTECODE_DIRECTIVES_SET:
        assert name in BYTECODE_DIRECTIVE_DOCS, f'missing doc for bytecode directive: {name}'


def test_all_preprocessor_directives_have_docs():
    for name in PREPROCESSOR_DIRECTIVES_SET:
        assert name in PREPROCESSOR_DIRECTIVE_DOCS, f'missing doc for preprocessor directive: {name}'


def test_all_directive_docs_is_union():
    expected = set(COMPILER_DIRECTIVE_DOCS) | set(BYTECODE_DIRECTIVE_DOCS) | set(PREPROCESSOR_DIRECTIVE_DOCS)
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
