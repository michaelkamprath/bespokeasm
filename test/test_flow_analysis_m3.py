import copy
import subprocess
import sys
from pathlib import Path

import pytest
from bespokeasm.assembler.engine import Assembler
from bespokeasm.assembler.symbol_scope import SymbolScope
from ruamel.yaml import YAML


PROJECT_ROOT = Path(__file__).resolve().parents[1]
M3_HARNESS_DIR = PROJECT_ROOT / 'test' / 'flow_harnesses' / 'm3'
M3_CONFIG_PATH = M3_HARNESS_DIR / 'flow-counters-m3.yaml'


@pytest.fixture(autouse=True)
def _reset_global_symbol_scope():
    SymbolScope._global_scope = None
    yield
    SymbolScope._global_scope = None


def _load_config() -> dict:
    yaml = YAML(typ='safe')
    with M3_CONFIG_PATH.open() as config_file:
        return yaml.load(config_file)


def _write_config(tmp_path: Path, config: dict, name: str = 'isa.yaml') -> Path:
    config_path = tmp_path / name
    yaml = YAML()
    with config_path.open('w') as config_file:
        yaml.dump(config, config_file)
    return config_path


def _assembler(
    tmp_path: Path,
    source: str,
    *,
    config_path: Path = M3_CONFIG_PATH,
    flow_checks: bool = True,
    output_name: str = 'out.bin',
) -> Assembler:
    source_path = tmp_path / f'{output_name}.asm'
    output_path = tmp_path / output_name
    source_path.write_text(source)
    return Assembler(
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
        flow_checks=flow_checks,
    )


def _assemble(*args, **kwargs) -> tuple[Assembler, bytes]:
    assembler = _assembler(*args, **kwargs)
    assembler.assemble_bytecode()
    return assembler, Path(assembler._output_file).read_bytes()


def _assert_flow_error(
    tmp_path: Path,
    source: str,
    expected: str,
    *,
    config_path: Path = M3_CONFIG_PATH,
    expected_line: int | None = None,
) -> Assembler:
    assembler = _assembler(tmp_path, source, config_path=config_path)
    with pytest.raises(SystemExit, match=expected):
        assembler.assemble_bytecode()
    diagnostic = assembler.model.diagnostic_reporter.diagnostics[-1]
    assert diagnostic.category == 'flow'
    if expected_line is not None:
        assert diagnostic.line_id.line_num == expected_line
    return assembler


def test_m3_development_acceptance_harness():
    result = subprocess.run(
        [sys.executable, str(M3_HARNESS_DIR / 'verify_m3.py')],
        cwd=PROJECT_ROOT,
        env={'PYTHONPATH': str(PROJECT_ROOT / 'src')},
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'M3 development acceptance: PASS' in result.stdout


def test_m3_called_parameter_demo_matches_hand_resolved_source(tmp_path):
    tracked = (M3_HARNESS_DIR / 'subroutine-parameters.asm').read_text()
    stripped = (M3_HARNESS_DIR / 'subroutine-parameters-stripped.asm').read_text()

    _, tracked_bytes = _assemble(tmp_path, tracked, output_name='tracked.bin')
    SymbolScope._global_scope = None
    _, stripped_bytes = _assemble(tmp_path, stripped, output_name='stripped.bin')

    assert tracked_bytes == stripped_bytes
    assert tracked_bytes == bytes(
        [0x14, 0x6C, 7, 0x6D, 11, 0x16, 4, 0x69]
    )


@pytest.mark.parametrize(
    'delimiter',
    ['', '#endtrack stack\n', '#endtrack stack exit=99\n'],
)
def test_m3_before_effect_terminal_closes_path_without_applying_physical_delta(
    tmp_path,
    delimiter,
):
    _, bytecode = _assemble(
        tmp_path,
        '#track stack mode=called\n'
        'rts\n'
        f'{delimiter}',
    )
    assert bytecode == bytes([0x69])


def test_m3_before_effect_terminal_reports_routine_owned_leak(tmp_path):
    _assert_flow_error(
        tmp_path,
        '#track stack mode=called\n'
        'push\n'
        'rts\n'
        '#endtrack stack\n',
        'exit mismatch: expected 0, actual 1',
        expected_line=3,
    )


def test_m3_after_effect_terminal_applies_delta_before_exit_check(tmp_path):
    _, bytecode = _assemble(
        tmp_path,
        '#track stack mode=called\n'
        'push\n'
        'leave\n'
        '#endtrack stack\n',
    )
    assert bytecode == bytes([0x10, 0x6A])


def test_m3_entry_mode_values_and_explicit_overrides(tmp_path):
    config = _load_config()
    config['flow_counters']['stack']['entry_modes']['called'] = {
        'init': 2,
        'exit': 1,
    }
    config_path = _write_config(tmp_path, config)

    _, mode_bytes = _assemble(
        tmp_path,
        '#track stack mode=called\n'
        'pop\n'
        'rts\n',
        config_path=config_path,
        output_name='mode.bin',
    )
    SymbolScope._global_scope = None
    _, override_bytes = _assemble(
        tmp_path,
        '#track stack mode=called init=0 exit=0\n'
        'rts\n',
        config_path=config_path,
        output_name='override.bin',
    )
    SymbolScope._global_scope = None
    _, default_bytes = _assemble(
        tmp_path,
        '#track stack\n'
        'rts\n',
        config_path=config_path,
        output_name='default.bin',
    )

    assert mode_bytes == bytes([0x11, 0x69])
    assert override_bytes == default_bytes == bytes([0x69])


def test_m3_unknown_or_non_identifier_entry_mode_fails(tmp_path):
    _assert_flow_error(
        tmp_path,
        '#track stack mode=interrupt\nrts\n',
        'has no entry mode "interrupt"',
        expected_line=1,
    )
    SymbolScope._global_scope = None
    _assert_flow_error(
        tmp_path,
        '#track stack mode=called+1\nrts\n',
        'requires one identifier',
        expected_line=1,
    )


@pytest.mark.parametrize(
    ('entry_modes', 'expected'),
    [
        ([], 'entry_modes must be a dictionary'),
        ({'called': {'exit': 0}}, 'containing integer init'),
        ({'called': {'init': False}}, 'init must be an integer'),
        ({'called': {'init': 0, 'extra': 1}}, 'unsupported option "extra"'),
    ],
)
def test_m3_malformed_entry_modes_fail_at_config_load(
    tmp_path,
    entry_modes,
    expected,
):
    config = _load_config()
    config['flow_counters']['stack']['entry_modes'] = entry_modes
    config_path = _write_config(tmp_path, config)

    with pytest.raises(SystemExit, match=expected):
        _assembler(
            tmp_path,
            '#track stack\nrts\n',
            config_path=config_path,
        )


def test_m3_terminal_does_not_end_lexical_extent(tmp_path):
    _assert_flow_error(
        tmp_path,
        '#track stack mode=called\n'
        'rts\n'
        '#track stack mode=called\n'
        'rts\n',
        'still lexically open after its terminal.*#endtrack stack',
        expected_line=3,
    )


def test_m5_cfg_supersedes_m3_unconditional_transfer_limitation(tmp_path):
    source = (
        '#track stack mode=jumped\n'
        '#endtrack stack\n'
        'jmp target\n'
        'target: nop\n'
    )
    _, bytecode = _assemble(tmp_path, source)
    assert bytecode == bytes([0x70, 2, 0])

    SymbolScope._global_scope = None
    _, bytecode = _assemble(
        tmp_path,
        '#track stack mode=jumped\n'
        'jmp target\n'
        'target: nop\n'
        '#endtrack stack\n',
    )
    assert bytecode == bytes([0x70, 2, 0])


def test_m3_arg_delta_uses_immediate_constant_and_updates_offset(tmp_path):
    source = (
        'FRAME_SIZE = 2\n'
        'routine:\n'
        '#track stack init=4 exit=0\n'
        '.arg := COORDINATE(stack, 3)\n'
        'addsp 2\n'
        'lds .arg\n'
        'addsp FRAME_SIZE\n'
        'rts\n'
        '#endtrack stack\n'
    )
    _, bytecode = _assemble(tmp_path, source)
    assert bytecode == bytes([0x16, 2, 0x6C, 1, 0x16, 2, 0x69])


def test_m3_macro_constituent_resolves_arg_against_expanded_operands(tmp_path):
    _, bytecode = _assemble(
        tmp_path,
        '#track stack init=4 exit=0\n'
        'free4\n'
        'rts\n'
        '#endtrack stack\n',
    )
    assert bytecode == bytes([0x16, 4, 0x69])


def test_m3_arg_delta_rejects_runtime_register_semantics(tmp_path):
    _assert_flow_error(
        tmp_path,
        '#track stack mode=called\n'
        'addsp sp\n'
        'rts\n'
        '#endtrack stack\n',
        'operand "sp" is runtime-valued',
        expected_line=2,
    )


def test_m3_arg_reads_source_value_from_numeric_bytecode_operand(tmp_path):
    config = _load_config()
    config['operand_sets']['encoded_adjustment'] = {
        'operand_values': {
            'immediate': {
                'type': 'numeric_bytecode',
                'bytecode': {
                    'min': 0,
                    'max': 15,
                    'size': 4,
                },
            },
        },
    }
    config['instructions']['encoded_addsp'] = {
        'flow_effects': {'stack': '-ARG(0)'},
        'flow_transfer': 'none',
        'bytecode': {'value': 0xA, 'size': 4},
        'operands': {
            'count': 1,
            'operand_sets': {'list': ['encoded_adjustment']},
        },
    }
    config_path = _write_config(tmp_path, config)

    _, bytecode = _assemble(
        tmp_path,
        '#track stack init=4 exit=0\n'
        'encoded_addsp 4\n'
        'rts\n',
        config_path=config_path,
    )
    assert bytecode == bytes([0xA4, 0x69])


def test_m3_arg_index_is_validated_against_each_effective_variant(tmp_path):
    config = _load_config()
    config['instructions']['addsp']['flow_effects']['stack'] = '-ARG(1)'
    config_path = _write_config(tmp_path, config)

    with pytest.raises(
        SystemExit,
        match=r'ARG\(1\).*outside the configured source-written operand count',
    ):
        _assembler(
            tmp_path,
            '#track stack\naddsp 1\n#endtrack stack\n',
            config_path=config_path,
        )


def test_m3_frozen_operand_preserves_non_decimal_default_base(tmp_path):
    config = copy.deepcopy(_load_config())
    config['general']['default_numeric_base'] = 'hex'
    config_path = _write_config(tmp_path, config)

    _, bytecode = _assemble(
        tmp_path,
        '#track stack init=10 exit=0\n'
        'addsp a\n'
        'rts\n',
        config_path=config_path,
    )
    assert bytecode == bytes([0x16, 0x0A, 0x69])


@pytest.mark.parametrize(
    ('unreachable_line', 'expected'),
    [
        (
            'lds COUNTER(stack)',
            'is unreachable after flow counter "stack" terminated',
        ),
        (
            'lds .slot',
            'is unreachable after the flow counter path terminated',
        ),
    ],
)
def test_m3_unreachable_lines_have_no_counter_state(
    tmp_path,
    unreachable_line,
    expected,
):
    """Requirements: unreachable code after all paths terminated has no state.

    "Unreachable instructions receive no counter state and are not subjected
    to effect/transfer completeness checks until declared as an entry ...
    ``COUNTER()``/coordinate use on any unreachable line remains an error."
    The error half was probe-verified during the M3 review but had no test.
    """
    _assert_flow_error(
        tmp_path,
        'function:\n'
        '#track stack mode=called\n'
        'push\n'
        '.slot := COORDINATE(stack, 1)\n'
        'pop\n'
        'rts\n'
        f'{unreachable_line}\n'
        '#endtrack stack\n',
        expected,
        expected_line=7,
    )


def test_m3_unreachable_instructions_are_exempt_from_completeness_checks(tmp_path):
    """Requirements: transfer/effect completeness checks stop at termination.

    An instruction with *missing* ``flow_transfer`` metadata after every path
    has terminated must be accepted (it is unreachable); the same instruction
    while the path is live must error. Probe-verified during review; untested.
    """
    config = _load_config()
    config['instructions']['nop'] = {
        'bytecode': {'value': 0x77, 'size': 8},
    }
    config_path = _write_config(tmp_path, config)

    _, bytecode = _assemble(
        tmp_path,
        '#track stack mode=called\nrts\nnop\n',
        config_path=config_path,
    )
    assert bytecode == bytes([0x69, 0x77])

    SymbolScope._global_scope = None
    _assert_flow_error(
        tmp_path,
        '#track stack mode=called\nnop\nrts\n',
        'missing required flow_transfer',
        config_path=config_path,
        expected_line=2,
    )


def test_m3_error_paths_survive_a_nonfatal_diagnostic_reporter(tmp_path, monkeypatch):
    """Extends the M1/M2 nonfatal-reporter regression tests with M3 error sites.

    Every ``_error()`` call site must guard-and-return; with a non-exiting
    reporter each scenario must degrade to a recorded flow diagnostic rather
    than crash on invalid state (see the M1 test of the same name for the full
    rationale).
    """
    from bespokeasm.assembler.diagnostic_reporter import DiagnosticReporter

    original_error = DiagnosticReporter.error

    def nonfatal_error(self, line_id, message, category='user', color=None):
        try:
            original_error(self, line_id, message, category=category, color=color)
        except SystemExit:
            pass

    monkeypatch.setattr(DiagnosticReporter, 'error', nonfatal_error)

    scenarios = [
        # terminal exit mismatch (before_effect check against incoming value)
        ('terminal-mismatch', '#track stack mode=called\npush\nrts\n#endtrack stack\n'),
        # unknown entry mode
        ('unknown-mode', '#track stack mode=interrupt\nrts\n'),
        # runtime-valued ARG operand
        ('runtime-arg', '#track stack mode=called\naddsp sp\nrts\n#endtrack stack\n'),
    ]
    for name, source in scenarios:
        SymbolScope._global_scope = None
        assembler = _assembler(tmp_path, source, output_name=f'{name}.bin')
        assembler.assemble_bytecode()
        assert any(
            diagnostic.category == 'flow' and diagnostic.level == 'error'
            for diagnostic in assembler.model.diagnostic_reporter.diagnostics
        ), f'scenario {name} recorded no flow error'
