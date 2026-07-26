import copy
import os
import subprocess
import sys
from pathlib import Path

import pytest
from bespokeasm.assembler.engine import Assembler
from bespokeasm.assembler.label_scope import LabelScope
from bespokeasm.assembler.line_identifier import LineIdentifier
from bespokeasm.expression import ExpressionUseContext
from bespokeasm.expression import parse_expression
from ruamel.yaml import YAML


PROJECT_ROOT = Path(__file__).resolve().parents[1]
M1_HARNESS_DIR = PROJECT_ROOT / 'dev' / 'flow-counters-m1'
M1_CONFIG_PATH = M1_HARNESS_DIR / 'flow-counters-m1.yaml'


@pytest.fixture(autouse=True)
def _reset_global_label_scope():
    LabelScope._global_scope = None
    yield
    LabelScope._global_scope = None


def _load_config() -> dict:
    yaml = YAML(typ='safe')
    with M1_CONFIG_PATH.open() as config_file:
        return yaml.load(config_file)


def _write_config(tmp_path: Path, config: dict, name: str = 'isa.yaml') -> Path:
    config_path = tmp_path / name
    yaml = YAML()
    with config_path.open('w') as config_file:
        yaml.dump(config, config_file)
    return config_path


def _without_flow_metadata(config: dict) -> dict:
    config = copy.deepcopy(config)
    config.pop('flow_counters', None)
    for instruction in config['instructions'].values():
        for key in (
            'flow_effects',
            'flow_terminal',
            'flow_transfer',
            'flow_target_operand',
            'flow_call_effects',
        ):
            instruction.pop(key, None)
        for variant in instruction.get('variants', []):
            for key in (
                'flow_effects',
                'flow_terminal',
                'flow_transfer',
                'flow_target_operand',
                'flow_call_effects',
            ):
                variant.pop(key, None)
    return config


def _assembler(
    tmp_path: Path,
    source: str,
    *,
    config_path: Path = M1_CONFIG_PATH,
    static_analysis: bool = True,
    output_name: str = 'out.bin',
) -> Assembler:
    source_path = tmp_path / f'{output_name}.asm'
    output_path = tmp_path / output_name
    source_path.write_text(source)
    assembler = Assembler(
        source_file=str(source_path),
        config_file=str(config_path),
        generate_binary=True,
        output_file=str(output_path),
        binary_start=0,
        binary_end=None,
        binary_fill_value=0,
        enable_pretty_print=False,
        pretty_print_format=None,
        pretty_print_output=None,
        is_verbose=0,
        include_paths=[str(tmp_path)],
        predefined=[],
        static_analysis=static_analysis,
    )
    return assembler


def _assemble(*args, **kwargs) -> tuple[Assembler, bytes]:
    assembler = _assembler(*args, **kwargs)
    assembler.assemble_bytecode()
    return assembler, Path(assembler._output_file).read_bytes()


def _assert_flow_error(
    tmp_path: Path,
    source: str,
    expected: str,
    *,
    config_path: Path = M1_CONFIG_PATH,
    static_analysis: bool = True,
    expected_line: int | None = None,
) -> Assembler:
    assembler = _assembler(
        tmp_path,
        source,
        config_path=config_path,
        static_analysis=static_analysis,
    )
    with pytest.raises(SystemExit, match=expected):
        assembler.assemble_bytecode()
    diagnostic = assembler.model.diagnostic_reporter.diagnostics[-1]
    assert diagnostic.category == 'flow'
    assert diagnostic.line_id is not None
    if expected_line is not None:
        assert diagnostic.line_id.line_num == expected_line
    return assembler


def test_m1_counter_operand_data_and_strip_equivalence(tmp_path):
    tracked = (M1_HARNESS_DIR / 'tracked.asm').read_text()
    stripped = (M1_HARNESS_DIR / 'stripped.asm').read_text()
    annotation_only = (M1_HARNESS_DIR / 'annotation-only.asm').read_text()

    _, tracked_bytes = _assemble(tmp_path, tracked, output_name='tracked.bin')
    LabelScope._global_scope = None
    _, stripped_bytes = _assemble(tmp_path, stripped, output_name='stripped.bin')
    LabelScope._global_scope = None
    disabled, disabled_bytes = _assemble(
        tmp_path,
        annotation_only,
        static_analysis=False,
        output_name='disabled.bin',
    )

    assert tracked_bytes == stripped_bytes == disabled_bytes
    assert tracked_bytes == bytes([0x10, 0x80, 0x01, 0x01, 0x11])
    assert disabled.analysis_source_index is None
    assert not any(
        diagnostic.category == 'flow'
        for diagnostic in disabled.model.diagnostic_reporter.diagnostics
    )


def test_m1_counter_resolves_in_fill_value_and_repeated_expression(tmp_path):
    source = (
        '#track stack\n'
        'push\n'
        '.fill 2, COUNTER(stack)\n'
        '.byte COUNTER(stack) + COUNTER(stack)\n'
        'pop\n'
        '#endtrack stack\n'
    )
    _, bytecode = _assemble(tmp_path, source)
    assert bytecode == bytes([0x10, 1, 1, 2, 0x11])


def test_m1_custom_source_path_supplies_constant_delta(tmp_path):
    config = _load_config()
    config['flow_counters']['stack']['source'] = 'documentation.cycles'
    for instruction in config['instructions'].values():
        instruction.pop('flow_effects', None)
        instruction['documentation'] = {'cycles': 1}
    config_path = _write_config(tmp_path, config)
    source = '#track stack exit=2\nnop\ndepth COUNTER(stack)\n#endtrack stack\n'
    _, bytecode = _assemble(tmp_path, source, config_path=config_path)
    assert bytecode == bytes([0, 0x80, 1])


def test_m1_directives_have_zero_address_footprint(tmp_path):
    tracked = (
        '.org 4\n'
        'before:\n'
        '#track stack\n'
        'nop\n'
        '#endtrack stack\n'
        'after:\n'
        '.byte after - before\n'
    )
    stripped = '.org 4\nbefore:\nnop\nafter:\n.byte after - before\n'
    _, tracked_bytes = _assemble(tmp_path, tracked, output_name='tracked-layout.bin')
    LabelScope._global_scope = None
    _, stripped_bytes = _assemble(tmp_path, stripped, output_name='stripped-layout.bin')
    assert tracked_bytes == stripped_bytes
    assert tracked_bytes[-2:] == bytes([0, 1])


def test_m1_multiple_same_line_instructions_apply_effects_in_order(tmp_path):
    source = '#track stack\npush depth COUNTER(stack)\npop\n#endtrack stack\n'
    _, bytecode = _assemble(tmp_path, source)
    assert bytecode == bytes([0x10, 0x80, 0x01, 0x11])


def test_m1_mute_does_not_stop_tracking(tmp_path):
    source = '\n'.join([
        '#track stack',
        '#mute',
        'push',
        '#unmute',
        'depth COUNTER(stack)',
        'pop',
        '#endtrack stack',
    ])
    _, bytecode = _assemble(tmp_path, source)
    assert bytecode[-3:] == bytes([0x80, 0x01, 0x11])


@pytest.mark.parametrize(
    ('source', 'message', 'line_number'),
    [
        ('#track stack\npop\n#endtrack stack\n', 'underflow', 2),
        ('#track stack\npush\npush\npush\n#endtrack stack exit=3\n', 'overflow', 4),
        ('#track stack\npush\n#endtrack stack\n', 'exit mismatch', 3),
        ('#track stack\nnop\n', 'reaches EOF', 2),
        ('depth COUNTER(stack)\n', 'inactive flow counter', 1),
    ],
)
def test_m1_bounds_exit_eof_and_inactive_errors(
    tmp_path,
    source,
    message,
    line_number,
):
    _assert_flow_error(
        tmp_path,
        source,
        message,
        expected_line=line_number,
    )


def test_m1_exit_policy_none_and_explicit_exit(tmp_path):
    config = _load_config()
    config['flow_counters']['stack']['exit_policy'] = 'none'
    config_path = _write_config(tmp_path, config)
    source = '#track stack\npush\n#endtrack stack\n'
    _assemble(tmp_path, source, config_path=config_path)

    LabelScope._global_scope = None
    source = '#track stack\npush\n#endtrack stack exit=1\n'
    _assemble(tmp_path, source, config_path=config_path)

    LabelScope._global_scope = None
    _assert_flow_error(
        tmp_path,
        '#track stack\npush\n#endtrack stack exit=0\n',
        'exit mismatch',
        config_path=config_path,
    )


def test_m1_track_init_and_exit_parameters(tmp_path):
    source = '#track stack init=1 exit=0\npop\n#endtrack stack\n'
    _, bytecode = _assemble(tmp_path, source)
    assert bytecode == bytes([0x11])


@pytest.mark.parametrize('directive', ['#track', '#endtrack'])
def test_m1_malformed_flow_directive_reports_flow_syntax_error(tmp_path, directive):
    _assert_flow_error(tmp_path, f'{directive}\n', 'directive syntax')


@pytest.mark.parametrize(
    ('policy', 'outcome'),
    [
        ('ignore', 'ok'),
        ('warn', 'warning'),
        ('error', 'error'),
    ],
)
def test_m1_unknown_instruction_policy(tmp_path, policy, outcome):
    config = _load_config()
    config['flow_counters']['stack']['unknown_instructions'] = policy
    config['instructions']['mystery'] = {
        'flow_transfer': 'none',
        'bytecode': {'value': 0x33, 'size': 8},
    }
    config_path = _write_config(tmp_path, config)
    source = '#track stack\nmystery\n#endtrack stack\n'

    if outcome == 'error':
        _assert_flow_error(tmp_path, source, 'no effect metadata', config_path=config_path)
        return
    assembler, _ = _assemble(tmp_path, source, config_path=config_path)
    flow_warnings = [
        diagnostic
        for diagnostic in assembler.model.diagnostic_reporter.diagnostics
        if diagnostic.category == 'flow' and diagnostic.level == 'warning'
    ]
    assert bool(flow_warnings) is (outcome == 'warning')


def test_m1_missing_and_non_linear_transfer_metadata_fail_on_use(tmp_path):
    config = _load_config()
    config['instructions']['nop'].pop('flow_transfer')
    missing_path = _write_config(tmp_path, config, 'missing.yaml')
    _assert_flow_error(
        tmp_path,
        '#track stack\nnop\n#endtrack stack\n',
        'missing required flow_transfer',
        config_path=missing_path,
    )

    LabelScope._global_scope = None
    config = _load_config()
    config['instructions']['nop']['flow_transfer'] = 'unconditional'
    config['instructions']['nop']['flow_target_operand'] = 0
    config['instructions']['nop']['operands'] = {
        'count': 1,
        'operand_sets': {'list': ['depth']},
    }
    transfer_path = _write_config(tmp_path, config, 'transfer.yaml')
    _assert_flow_error(
        tmp_path,
        '#track stack\nnop 0\n#endtrack stack\n',
        'path analysis is not yet available in M1',
        config_path=transfer_path,
    )


def test_m1_inert_and_unused_counter_classes_are_usage_gated(tmp_path):
    config = _load_config()
    config['flow_counters']['unused'] = {
        'unknown_instructions': 'error',
        'exit_policy': 'balanced',
    }
    config_path = _write_config(tmp_path, config)
    _assemble(
        tmp_path,
        '#track stack\nnop\n#endtrack stack\n',
        config_path=config_path,
    )

    LabelScope._global_scope = None
    _assert_flow_error(
        tmp_path,
        '#track unused\nnop\n#endtrack unused\n',
        'is inert',
        config_path=config_path,
    )


def test_m1_effect_metadata_lookup_is_memoized(tmp_path, monkeypatch):
    assembler = _assembler(tmp_path, 'nop\n')
    model = assembler.model
    original = model._effective_instruction_configs
    scans = 0

    def counted_effective_configs(instruction_config):
        nonlocal scans
        scans += 1
        return original(instruction_config)

    monkeypatch.setattr(
        model,
        '_effective_instruction_configs',
        counted_effective_configs,
    )

    assert model.flow_counter_has_effect_metadata('stack')
    first_scan_count = scans
    assert first_scan_count > 0
    assert model.flow_counter_has_effect_metadata('stack')
    assert scans == first_scan_count


def test_m1_feature_enablement_and_inactive_condition_are_usage_gated(tmp_path):
    no_flow_path = _write_config(tmp_path, _without_flow_metadata(_load_config()))
    _, ordinary = _assemble(tmp_path, 'push\npop\n', config_path=no_flow_path)
    assert ordinary == bytes([0x10, 0x11])

    LabelScope._global_scope = None
    _assert_flow_error(
        tmp_path,
        '#track stack\n#endtrack stack\n',
        'does not enable flow counters',
        config_path=no_flow_path,
    )

    LabelScope._global_scope = None
    _, inactive = _assemble(
        tmp_path,
        '#ifdef NEVER\n#track stack\n#endtrack stack\n#endif\nnop\n',
        config_path=no_flow_path,
    )
    assert inactive == bytes([0])


def test_m1_disabled_analysis_ignores_annotations_but_rejects_dependency(tmp_path):
    no_flow_path = _write_config(tmp_path, _without_flow_metadata(_load_config()))
    annotated = '#track stack\npush\npop\n#endtrack stack\n'
    _, annotated_bytes = _assemble(
        tmp_path,
        annotated,
        config_path=no_flow_path,
        static_analysis=False,
    )
    LabelScope._global_scope = None
    _, stripped_bytes = _assemble(
        tmp_path,
        'push\npop\n',
        config_path=no_flow_path,
        static_analysis=False,
        output_name='stripped.bin',
    )
    assert annotated_bytes == stripped_bytes

    LabelScope._global_scope = None
    _assert_flow_error(
        tmp_path,
        'depth COUNTER(stack)\n',
        'static analysis is disabled',
        static_analysis=False,
    )
    LabelScope._global_scope = None
    _assert_flow_error(
        tmp_path,
        '.byte COUNTER(stack)\n',
        'static analysis is disabled',
        static_analysis=False,
    )


@pytest.mark.parametrize(
    ('line', 'context'),
    [
        ('.org COUNTER(stack)', 'layout expressions'),
        ('.align COUNTER(stack)', 'layout expressions'),
        ('.fill COUNTER(stack), 0', 'fill-count expressions'),
        ('.zero COUNTER(stack)', 'layout expressions'),
        ('.zerountil COUNTER(stack)', 'layout expressions'),
        ('#if COUNTER(stack)', 'preprocessor directives'),
        ('VALUE = COUNTER(stack)', 'ordinary constant assignments'),
    ],
)
def test_m1_counter_is_rejected_from_layout_and_selection_contexts(tmp_path, line, context):
    _assert_flow_error(
        tmp_path,
        f'#track stack\n{line}\n#endtrack stack\n',
        context,
        expected_line=2,
    )


@pytest.mark.parametrize(
    'context',
    [
        ExpressionUseContext.LAYOUT,
        ExpressionUseContext.PREPROCESSOR_CONDITION,
        ExpressionUseContext.INSTRUCTION_SELECTION,
    ],
)
def test_m1_expression_parser_rejects_counter_from_non_value_contexts(context):
    with pytest.raises(SyntaxError, match='flow expressions are not allowed'):
        parse_expression(
            LineIdentifier(1, 'selection.asm'),
            'COUNTER(stack)',
            context=context,
        )


def test_m1_harness_is_runnable():
    environment = os.environ.copy()
    environment['PYTHONPATH'] = str(PROJECT_ROOT / 'src')
    result = subprocess.run(
        [sys.executable, str(M1_HARNESS_DIR / 'verify_m1.py')],
        cwd=PROJECT_ROOT,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert 'M1 development acceptance: PASS' in result.stdout
