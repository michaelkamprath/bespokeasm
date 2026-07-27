import json
from pathlib import Path

import pytest
from bespokeasm.configgen.sublime import SublimeConfigGenerator
from bespokeasm.configgen.vim import VimConfigGenerator
from bespokeasm.configgen.vscode import VSCodeConfigGenerator


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FLOW_CONFIG = PROJECT_ROOT / 'dev' / 'flow-counters-m2' / 'flow-counters-m2.yaml'
PLAIN_CONFIG = PROJECT_ROOT / 'test' / 'config_files' / 'eater-sap1-isa.yaml'
FLOW_TOKENS = ('track', 'endtrack', 'COORDINATE', 'COUNTER', 'OFFSET', ':=')
FLOW_COORDINATE_SCOPE = 'variable.other.flow.coordinate'
FLOW_COORDINATE_DEFINITION_SCOPE = 'variable.other.flow.coordinate.definition'
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
def test_m2_flow_tokens_and_hover_docs_are_generated_for_enabled_isa(
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
        assert 'FlowCoordinateDefinition' in generated
    else:
        assert FLOW_COORDINATE_SCOPE in generated
        assert FLOW_COORDINATE_DEFINITION_SCOPE in generated

    if generator_class is not VimConfigGenerator:
        assert {'track', 'endtrack'} <= set(
            hover_docs['directives']['preprocessor'],
        )
        assert {'COORDINATE', 'COUNTER', 'OFFSET'} <= set(
            hover_docs['expression_functions'],
        )
        assert ':=' in hover_docs['directives']['counter_coordinate']
    else:
        assert '#track' in generated
        assert '#endtrack' in generated
        assert '`COUNTER()`' in generated
        assert '`COORDINATE()`' in generated
        assert '`OFFSET()`' in generated
        assert '`:=`' in generated


@pytest.mark.parametrize(
    'generator_class',
    [VSCodeConfigGenerator, SublimeConfigGenerator, VimConfigGenerator],
)
def test_m2_flow_tokens_are_absent_from_non_enabled_isa(
    tmp_path,
    generator_class,
):
    generated, hover_docs = _generated_text(
        generator_class,
        PLAIN_CONFIG,
        tmp_path / generator_class.__name__,
    )
    for token in FLOW_TOKENS[:-1]:
        assert token not in generated
    assert 'Declare Counter Coordinate' not in generated
    assert FLOW_COORDINATE_SCOPE not in generated
    assert FLOW_COORDINATE_DEFINITION_SCOPE not in generated
    assert 'FlowCoordinateDefinition' not in generated

    if generator_class is not VimConfigGenerator:
        assert 'track' not in hover_docs['directives']['preprocessor']
        assert 'endtrack' not in hover_docs['directives']['preprocessor']
        assert 'COUNTER' not in hover_docs['expression_functions']
        assert 'COORDINATE' not in hover_docs['expression_functions']
        assert 'OFFSET' not in hover_docs['expression_functions']
        assert not hover_docs['directives']['counter_coordinate']
