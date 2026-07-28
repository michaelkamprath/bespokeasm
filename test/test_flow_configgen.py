import json
from pathlib import Path

import pytest
from bespokeasm.configgen.sublime import SublimeConfigGenerator
from bespokeasm.configgen.vim import VimConfigGenerator
from bespokeasm.configgen.vscode import VSCodeConfigGenerator
from ruamel.yaml import YAML


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FLOW_CONFIG = PROJECT_ROOT / 'dev' / 'flow-counters-m2' / 'flow-counters-m2.yaml'
PLAIN_CONFIG = PROJECT_ROOT / 'test' / 'config_files' / 'eater-sap1-isa.yaml'
FLOW_TOKENS = ('track', 'endtrack', 'COORDINATE', 'COUNTER', 'OFFSET', ':=')
M4_FLOW_DIRECTIVES = {'resume', 'set', 'suspend'}
FLOW_COORDINATE_SCOPE = 'variable.other.flow.coordinate'
FLOW_COORDINATE_DEFINITION_SCOPE = 'variable.other.flow.coordinate.definition'
FLOW_COORDINATE_USAGE_SCOPE = 'variable.other.flow.coordinate.usage'
FLOW_COUNTER_SCOPE = 'variable.other.flow.counter'
FLOW_COUNTER_USAGE_SCOPE = 'variable.other.flow.counter.usage'
FLOW_OPERATOR_SCOPE = 'keyword.operator.flow'
SYMBOL_PATTERN_TOKENS = (
    '##SYMBOL_PATTERN##',
    '##LABEL_PATTERN##',
    '##CONSTANT_PATTERN##',
    '##GLOBAL_SYMBOL_PATTERN##',
    '##FILE_SYMBOL_PATTERN##',
    '##LOCAL_SYMBOL_PATTERN##',
)


def _generated_text(generator_class, config_path: Path, destination: Path) -> tuple[str, dict]:
    generator = generator_class(
        str(config_path),
        0,
        str(destination),
        'flow-m1-test',
        '1.0.0',
        'flowasm',
    )
    if generator_class is SublimeConfigGenerator:
        destination.mkdir(parents=True)
        generator._generate_files_in_dir(str(destination))
        generated_root = destination
    else:
        generator.generate()
        if generator_class is VSCodeConfigGenerator:
            generated_root = destination / 'extensions' / generator.language_name
        else:
            generated_root = destination

    text = '\n'.join(
        path.read_text(errors='ignore')
        for path in generated_root.rglob('*')
        if path.is_file()
    )
    for token in SYMBOL_PATTERN_TOKENS:
        assert token not in text
    docs_path = next(generated_root.rglob('instruction-docs.json'), None)
    if docs_path is not None:
        hover_docs = json.loads(docs_path.read_text())
    else:
        hover_docs = {}
    return text, hover_docs


@pytest.mark.parametrize(
    'generator_class',
    [VSCodeConfigGenerator, SublimeConfigGenerator, VimConfigGenerator],
)
def test_flow_tokens_and_hover_docs_are_generated_for_enabled_isa(
    tmp_path,
    generator_class,
):
    generated, hover_docs = _generated_text(
        generator_class,
        FLOW_CONFIG,
        tmp_path / generator_class.__name__,
    )
    for token in FLOW_TOKENS:
        assert token in generated

    if generator_class is VimConfigGenerator:
        assert 'FlowCoordinateName' in generated
        assert 'FlowCoordinateDefinition' in generated
        assert 'FlowCoordinateUsage' in generated
        assert 'FlowCounterName' in generated
        assert 'FlowCounterUsage' in generated
        assert 'FlowOperator' in generated
    else:
        assert FLOW_COORDINATE_SCOPE in generated
        assert FLOW_COORDINATE_DEFINITION_SCOPE in generated
        assert FLOW_COORDINATE_USAGE_SCOPE in generated
        assert FLOW_COUNTER_SCOPE in generated
        assert FLOW_COUNTER_USAGE_SCOPE in generated
        assert FLOW_OPERATOR_SCOPE in generated

    generated_dir = tmp_path / generator_class.__name__
    if generator_class is VSCodeConfigGenerator:
        grammar_path = next(generated_dir.rglob('tmGrammar.json'))
        grammar = json.loads(grammar_path.read_text())
        usage = grammar['repository']['flow_coordinate_usages']
        assert usage['captures']['1']['name'] == FLOW_OPERATOR_SCOPE
        assert usage['captures']['5']['name'] == (
            f'{FLOW_COORDINATE_SCOPE} {FLOW_COORDINATE_USAGE_SCOPE}'
        )
        counter_usage = grammar['repository']['flow_counter_usages']
        assert counter_usage['captures']['1']['name'] == FLOW_OPERATOR_SCOPE
        assert counter_usage['captures']['5']['name'].endswith(
            FLOW_COUNTER_USAGE_SCOPE
        )
        assert all(
            token in counter_usage['match']
            for token in ('COORDINATE', 'COUNTER')
        )
        directive_patterns = grammar['repository']['flow_counter_directives'][
            'patterns'
        ]
        track = next(pattern for pattern in directive_patterns if '(track)' in pattern['match'])
        usages = next(
            pattern
            for pattern in directive_patterns
            if 'endtrack|resume|set|suspend' in pattern['match']
        )
        instance_name = next(
            pattern
            for pattern in directive_patterns
            if '(as)' in pattern['match']
        )
        assert track['captures']['3']['name'] == FLOW_COUNTER_SCOPE
        assert instance_name['captures']['3']['name'] == FLOW_COUNTER_SCOPE
        assert usages['captures']['3']['name'] == (
            f'{FLOW_COUNTER_SCOPE} {FLOW_COUNTER_USAGE_SCOPE}'
        )
        preprocessor = next(
            pattern
            for pattern in grammar['repository']['directives']['patterns']
            if pattern.get('name') == 'meta.preprocessor'
        )
        assert preprocessor['patterns'][0]['include'] == '#flow_counter_directives'
        assert all(
            token in grammar['repository']['flow_operators']['match']
            for token in ('COORDINATE', 'COUNTER', 'OFFSET')
        )
    elif generator_class is SublimeConfigGenerator:
        syntax_path = next(generated_dir.rglob('*.sublime-syntax'))
        syntax = YAML().load(syntax_path)
        usage = syntax['contexts']['flow_coordinate_usages'][0]
        assert usage['captures'][1] == FLOW_OPERATOR_SCOPE
        assert usage['captures'][5] == (
            f'{FLOW_COORDINATE_SCOPE} {FLOW_COORDINATE_USAGE_SCOPE}'
        )
        counter_usage = syntax['contexts']['flow_counter_usages'][0]
        assert counter_usage['captures'][1] == FLOW_OPERATOR_SCOPE
        assert counter_usage['captures'][5].endswith(FLOW_COUNTER_USAGE_SCOPE)
        assert all(
            token in counter_usage['match']
            for token in ('COORDINATE', 'COUNTER')
        )
        directive_patterns = syntax['contexts']['flow_counter_directives']
        track = next(pattern for pattern in directive_patterns if '(track)' in pattern['match'])
        usages = next(
            pattern
            for pattern in directive_patterns
            if 'endtrack|resume|set|suspend' in pattern['match']
        )
        instance_name = next(
            pattern
            for pattern in directive_patterns
            if '(as)' in pattern['match']
        )
        assert track['captures'][3] == FLOW_COUNTER_SCOPE
        assert instance_name['captures'][3] == FLOW_COUNTER_SCOPE
        assert usages['captures'][3] == (
            f'{FLOW_COUNTER_SCOPE} {FLOW_COUNTER_USAGE_SCOPE}'
        )
        assert (
            syntax['contexts']['preprocessor_directives'][0]['push'][1]['include']
            == 'flow_counter_directives'
        )
        assert all(
            token in syntax['contexts']['flow_operators'][0]['match']
            for token in ('COORDINATE', 'COUNTER', 'OFFSET')
        )
    else:
        assert 'syn match flowm1testassemblyFlowCoordinateUsage' in generated
        assert r'#\%(endtrack\|resume\|set\|suspend\)' in generated
        assert r'\<as\s*=\s*\zs' in generated
        assert (
            'syn keyword flowm1testassemblyFlowOperator '
            'COORDINATE COUNTER OFFSET'
        ) in generated

    if generator_class is not VimConfigGenerator:
        assert {'track', 'endtrack', 'assert', *M4_FLOW_DIRECTIVES} <= set(
            hover_docs['directives']['preprocessor'],
        )
        assert {'COORDINATE', 'COUNTER', 'OFFSET'} <= set(
            hover_docs['expression_functions'],
        )
        assert ':=' in hover_docs['directives']['counter_coordinate']
        # a flow-enabled ISA's #assert hover carries the flow-form suffix
        # (FLOW_ASSERT_DOC_SUFFIX) describing COUNTER()/OFFSET() operands
        assert (
            'never controls conditional compilation'
            in hover_docs['directives']['preprocessor']['assert']
        )
    else:
        assert '#track' in generated
        assert '#endtrack' in generated
        for directive in M4_FLOW_DIRECTIVES:
            assert f'`#{directive}`' in generated
        assert '`COUNTER()`' in generated
        assert '`COORDINATE()`' in generated
        assert '`OFFSET()`' in generated
        assert '`:=`' in generated


@pytest.mark.parametrize(
    'generator_class',
    [VSCodeConfigGenerator, SublimeConfigGenerator, VimConfigGenerator],
)
def test_flow_tokens_are_absent_from_non_enabled_isa(
    tmp_path,
    generator_class,
):
    generated, hover_docs = _generated_text(
        generator_class,
        PLAIN_CONFIG,
        tmp_path / generator_class.__name__,
    )
    for token in FLOW_TOKENS[:-1]:
        assert token not in generated, f'flow token {token!r} leaked into non-flow extension'
    # ':=' cannot be asserted as a bare substring — ordinary regex syntax such
    # as the non-capturing group in `(?:=|\bEQU\b)` contains it. The only
    # legitimate carrier of the spelling is the hover-detection code, which
    # templates it via ##DECLARATION_OPERATOR##; assert the quoted operator
    # literal never ships in a non-flow extension.
    assert "':='" not in generated, "':=' hover spelling leaked into non-flow extension"
    assert 'Declare Counter Coordinate' not in generated
    assert FLOW_COORDINATE_SCOPE not in generated
    assert FLOW_COORDINATE_DEFINITION_SCOPE not in generated
    assert FLOW_COORDINATE_USAGE_SCOPE not in generated
    assert 'FlowCoordinateName' not in generated
    assert 'FlowCoordinateDefinition' not in generated
    assert 'FlowCoordinateUsage' not in generated
    assert 'FlowCounterName' not in generated
    assert 'FlowCounterUsage' not in generated
    assert 'FlowOperator' not in generated
    assert FLOW_COUNTER_USAGE_SCOPE not in generated
    assert FLOW_OPERATOR_SCOPE not in generated

    if generator_class is not VimConfigGenerator:
        assert 'track' not in hover_docs['directives']['preprocessor']
        assert 'endtrack' not in hover_docs['directives']['preprocessor']
        assert 'assert' in hover_docs['directives']['preprocessor']
        # the non-flow #assert hover must not carry the flow-form suffix
        assert (
            'never controls conditional compilation'
            not in hover_docs['directives']['preprocessor']['assert']
        )
        assert not M4_FLOW_DIRECTIVES & set(
            hover_docs['directives']['preprocessor'],
        )
        assert 'COUNTER' not in hover_docs['expression_functions']
        assert 'COORDINATE' not in hover_docs['expression_functions']
        assert 'OFFSET' not in hover_docs['expression_functions']
        assert not hover_docs['directives']['counter_coordinate']
