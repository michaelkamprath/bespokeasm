import subprocess
import sys
from pathlib import Path

import pytest
from bespokeasm.assembler.engine import Assembler
from bespokeasm.assembler.symbol_scope import SymbolScope


PROJECT_ROOT = Path(__file__).resolve().parents[1]
M4_HARNESS_DIR = PROJECT_ROOT / 'dev' / 'flow-counters-m4'
M4_CONFIG_PATH = M4_HARNESS_DIR / 'flow-counters-m4.yaml'


@pytest.fixture(autouse=True)
def _reset_global_symbol_scope():
    SymbolScope._global_scope = None
    yield
    SymbolScope._global_scope = None


def _assembler(
    tmp_path: Path,
    source: str,
    *,
    static_analysis: bool = True,
    output_name: str = 'out.bin',
) -> Assembler:
    source_path = tmp_path / f'{output_name}.asm'
    output_path = tmp_path / output_name
    source_path.write_text(source)
    return Assembler(
        source_file=str(source_path),
        config_file=str(M4_CONFIG_PATH),
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


def _assemble(*args, **kwargs) -> tuple[Assembler, bytes]:
    assembler = _assembler(*args, **kwargs)
    assembler.assemble_bytecode()
    return assembler, Path(assembler._output_file).read_bytes()


def _assert_flow_error(
    tmp_path: Path,
    source: str,
    expected: str,
    *,
    static_analysis: bool = True,
    expected_line: int | None = None,
) -> Assembler:
    assembler = _assembler(
        tmp_path,
        source,
        static_analysis=static_analysis,
    )
    with pytest.raises(SystemExit, match=expected):
        assembler.assemble_bytecode()
    diagnostic = assembler.model.diagnostic_reporter.diagnostics[-1]
    assert diagnostic.category == 'flow'
    if expected_line is not None:
        assert diagnostic.line_id.line_num == expected_line
    return assembler


def test_m4_development_acceptance_harness():
    result = subprocess.run(
        [sys.executable, str(M4_HARNESS_DIR / 'verify_m4.py')],
        cwd=PROJECT_ROOT,
        env={'PYTHONPATH': str(PROJECT_ROOT / 'src')},
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'M4 development acceptance: PASS' in result.stdout


def test_m4_default_names_advance_independent_classes(tmp_path):
    _, bytecode = _assemble(
        tmp_path,
        '#track stack\n'
        '#track cycles\n'
        'push\n'
        '#assert stack == 1\n'
        '#assert cycles == 2\n'
        'pop\n'
        '#endtrack stack\n'
        '#endtrack cycles exit=4\n',
    )
    assert bytecode == bytes([0x10, 0x11])


def test_m4_overlapping_instances_of_one_class_advance_independently(tmp_path):
    _, bytecode = _assemble(
        tmp_path,
        '#track cycles as=outer\n'
        'nop\n'
        '#track cycles as=inner\n'
        'nop\n'
        '#endtrack inner exit=1\n'
        'nop\n'
        '#endtrack outer exit=3\n',
    )
    assert bytecode == bytes([0, 0, 0])


def test_m4_duplicate_active_name_fails_but_distinct_names_succeed(tmp_path):
    _assert_flow_error(
        tmp_path,
        '#track cycles as=window\n'
        '#track stack as=window\n',
        'flow counter "window" is still active',
        expected_line=2,
    )

    SymbolScope._global_scope = None
    _, bytecode = _assemble(
        tmp_path,
        '#track cycles as=first\n'
        '#track cycles as=second\n'
        'nop\n'
        '#endtrack first exit=1\n'
        '#endtrack second exit=1\n',
    )
    assert bytecode == bytes([0])


@pytest.mark.parametrize(
    ('comparison', 'expected'),
    [
        ('==', 2),
        ('!=', 3),
        ('<', 3),
        ('<=', 2),
        ('>', 1),
        ('>=', 2),
    ],
)
def test_m4_assert_supports_scalar_comparisons(
    tmp_path,
    comparison,
    expected,
):
    _, bytecode = _assemble(
        tmp_path,
        '#track cycles\n'
        'push\n'
        f'#assert COUNTER(cycles) {comparison} {expected}\n'
        '#endtrack cycles exit=2\n',
    )
    assert bytecode == bytes([0x10])


def test_m4_failed_assert_reports_expected_and_actual(tmp_path):
    _assert_flow_error(
        tmp_path,
        '#track cycles\n'
        'nop\n'
        '#assert cycles == 2\n',
        'assertion failed: expected == 2, actual 1',
        expected_line=3,
    )


def test_m4_set_reanchors_only_the_named_counter(tmp_path):
    _, bytecode = _assemble(
        tmp_path,
        '#track cycles as=left\n'
        '#track cycles as=right\n'
        'nop\n'
        '#set left = COUNTER(right) + 4\n'
        'nop\n'
        '#assert left == 6\n'
        '#assert right == 2\n'
        '#endtrack left exit=6\n'
        '#endtrack right exit=2\n',
    )
    assert bytecode == bytes([0, 0])


def test_m4_suspend_pauses_only_the_named_counter(tmp_path):
    _, bytecode = _assemble(
        tmp_path,
        '#track cycles as=paused\n'
        '#track cycles as=running\n'
        'nop\n'
        '#suspend paused\n'
        'nop\n'
        '#resume paused = 1\n'
        'nop\n'
        '#assert paused == 2\n'
        '#assert running == 3\n'
        '#endtrack paused exit=2\n'
        '#endtrack running exit=3\n',
    )
    assert bytecode == bytes([0, 0, 0])


@pytest.mark.parametrize(
    ('source', 'expected', 'expected_line'),
    [
        (
            '#track cycles\n'
            '#suspend cycles\n'
            'depth COUNTER(cycles)\n',
            'cannot be resolved while flow counter "cycles" is suspended',
            3,
        ),
        (
            'routine:\n'
            '#track stack\n'
            '.slot := COORDINATE(stack, 0)\n'
            '#suspend stack\n'
            'depth OFFSET(.slot)\n',
            'cannot be resolved while flow counter "stack" is suspended',
            5,
        ),
        (
            '#track stack\n'
            '#suspend stack\n'
            '.slot := COORDINATE(stack, 0)\n',
            'cannot declare a coordinate while the counter is suspended',
            3,
        ),
        (
            '#track stack\n'
            '#suspend stack\n'
            'rts\n',
            'cannot reconcile suspended flow counter "stack"',
            3,
        ),
    ],
)
def test_m4_suspended_state_rejects_value_dependent_operations(
    tmp_path,
    source,
    expected,
    expected_line,
):
    _assert_flow_error(
        tmp_path,
        source,
        expected,
        expected_line=expected_line,
    )


def test_m4_resume_from_coordinate_invalidates_presuspension_slots(tmp_path):
    _assert_flow_error(
        tmp_path,
        'routine:\n'
        '#track stack\n'
        '.saved := COORDINATE(stack, 0)\n'
        '#suspend stack\n'
        'push\n'
        '#resume stack = .saved\n'
        'depth OFFSET(.saved)\n',
        'counter coordinate ".saved" is invalid',
        expected_line=7,
    )


def test_m4_plain_endtrack_may_abandon_a_suspended_region(tmp_path):
    _, bytecode = _assemble(
        tmp_path,
        '#track cycles\n'
        '#suspend cycles\n'
        'nop\n'
        '#endtrack cycles\n',
    )
    assert bytecode == bytes([0])


def test_m4_terminal_reconciles_all_instances_of_mapped_class_only(tmp_path):
    _, bytecode = _assemble(
        tmp_path,
        '#track stack as=frame_a mode=called\n'
        '#track stack as=frame_b mode=called\n'
        '#track cycles\n'
        'rts\n'
        '#assert cycles == 3\n'
        '#endtrack cycles exit=3\n'
        '#endtrack frame_a\n'
        '#endtrack frame_b\n',
    )
    assert bytecode == bytes([0x69])


def test_m4_inactive_or_undeclared_instance_errors(tmp_path):
    _assert_flow_error(
        tmp_path,
        '#assert absent == 0\n',
        '#assert references inactive flow counter "absent"',
        expected_line=1,
    )
    SymbolScope._global_scope = None
    _assert_flow_error(
        tmp_path,
        '#track missing\n',
        'flow counter class "missing" is not declared',
        expected_line=1,
    )


def test_m4_flow_directive_expressions_are_context_aware(tmp_path):
    _, bytecode = _assemble(
        tmp_path,
        '#track cycles as=source\n'
        '#track cycles as=target\n'
        'nop\n'
        '#set target = COUNTER(source) + 2\n'
        '#assert target == COUNTER(source) + 2\n'
        '#endtrack source exit=1\n'
        '#endtrack target exit=3\n',
    )
    assert bytecode == bytes([0])

    SymbolScope._global_scope = None
    _assert_flow_error(
        tmp_path,
        '#if COUNTER(source)\n'
        '#endif\n'
        'nop\n',
        'flow expressions are not allowed in conditional-compilation directives',
        expected_line=1,
    )


def test_m4_inactive_conditional_ignores_all_flow_directives(tmp_path):
    _, bytecode = _assemble(
        tmp_path,
        '#ifdef NEVER\n'
        '#track malformed as===\n'
        '#assert not valid syntax\n'
        '#set cycles\n'
        '#suspend\n'
        '#resume cycles\n'
        '#endif\n'
        'nop\n',
    )
    assert bytecode == bytes([0])


def test_m4_disabled_analysis_ignores_valid_manual_control_but_not_bad_syntax(
    tmp_path,
):
    _, annotated = _assemble(
        tmp_path,
        '#track cycles as=window\n'
        '#assert window == 99\n'
        '#set window = COUNTER(window) + 1\n'
        '#suspend window\n'
        '#resume window = 0\n'
        '#endtrack window exit=99\n'
        'nop\n',
        static_analysis=False,
        output_name='annotated.bin',
    )
    SymbolScope._global_scope = None
    _, stripped = _assemble(
        tmp_path,
        'nop\n',
        static_analysis=False,
        output_name='stripped.bin',
    )
    assert annotated == stripped == bytes([0])

    SymbolScope._global_scope = None
    _assert_flow_error(
        tmp_path,
        '#resume cycles\nnop\n',
        'invalid #resume directive syntax',
        static_analysis=False,
        expected_line=1,
    )
