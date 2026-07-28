from pathlib import Path

import pytest
from bespokeasm.assembler.engine import Assembler
from bespokeasm.assembler.symbol_scope import SymbolScope


PROJECT_ROOT = Path(__file__).resolve().parents[1]
NO_FLOW_CONFIG = PROJECT_ROOT / 'test' / 'config_files' / 'test_compilation_control.yaml'
FLOW_CONFIG = PROJECT_ROOT / 'dev' / 'flow-counters-m4' / 'flow-counters-m4.yaml'


@pytest.fixture(autouse=True)
def _reset_global_symbol_scope():
    SymbolScope._global_scope = None
    yield
    SymbolScope._global_scope = None


def _assembler(
    tmp_path: Path,
    source: str,
    *,
    config: Path = NO_FLOW_CONFIG,
    static_analysis: bool = True,
) -> Assembler:
    source_path = tmp_path / 'assert.asm'
    output_path = tmp_path / 'assert.bin'
    source_path.write_text(source)
    return Assembler(
        source_file=str(source_path),
        config_file=str(config),
        generate_binary=True,
        output_file=str(output_path),
        binary_start=0x100 if config == NO_FLOW_CONFIG else 0,
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


def _assemble(tmp_path: Path, source: str, **kwargs) -> Assembler:
    assembler = _assembler(tmp_path, source, **kwargs)
    assembler.assemble_bytecode()
    return assembler


@pytest.mark.parametrize(
    'condition',
    [
        'VALUE',
        'VALUE == 4',
        'VALUE != 5',
        'VALUE < 5',
        'VALUE <= 4',
        'VALUE > 3',
        'VALUE >= 4',
    ],
)
def test_assert_accepts_every_if_comparison_without_flow_counters(
    tmp_path,
    condition,
):
    _assemble(
        tmp_path,
        f'#define VALUE 4\n#assert {condition}\npush a\n',
    )


def test_assert_uses_if_string_and_builtin_symbol_semantics(tmp_path):
    _assemble(
        tmp_path,
        '#define FLAVOR alpha\n'
        '#assert FLAVOR == "alpha"\n'
        '#assert __LANGUAGE_NAME__ == "compilation-control-test"\n'
        '#assert __LANGUAGE_VERSION_MAJOR__ == 0\n'
        'push a\n',
    )


def test_assert_accepts_user_macros_that_require_rejects(tmp_path):
    _assemble(
        tmp_path,
        '#define MINIMUM 0\n'
        '#assert __LANGUAGE_VERSION_MAJOR__ >= MINIMUM\n'
        'push a\n',
    )


def test_assert_supports_plain_and_colored_failure_messages(tmp_path):
    plain = _assembler(tmp_path, '#assert 1 == 2 "plain failure"\npush a\n')
    with pytest.raises(SystemExit, match='plain failure'):
        plain.assemble_bytecode()
    assert plain.model.diagnostic_reporter.diagnostics[-1].message == 'plain failure'

    SymbolScope._global_scope = None
    colored = _assembler(
        tmp_path,
        '#assert 1 == 2 red "colored failure"\npush a\n',
    )
    with pytest.raises(SystemExit) as error:
        colored.assemble_bytecode()
    assert 'colored failure' in str(error.value)
    assert '\x1b[31m' in str(error.value)
    assert (
        colored.model.diagnostic_reporter.diagnostics[-1].message
        == 'colored failure'
    )


def test_assert_distinguishes_a_string_rhs_from_an_optional_message(tmp_path):
    _assemble(
        tmp_path,
        '#define FLAVOR alpha\n'
        '#define COLOR red\n'
        '#assert FLAVOR == "alpha" "wrong flavor"\n'
        '#assert FLAVOR == "alpha" red "wrong flavor"\n'
        '#assert COLOR == red "wrong color"\n'
        'push a\n',
    )


def test_general_assert_remains_active_when_static_analysis_is_disabled(
    tmp_path,
):
    assembler = _assembler(
        tmp_path,
        '#define VALUE 1\n'
        '#assert VALUE == 2 "general assertion still runs"\n'
        'push a\n',
        static_analysis=False,
    )
    with pytest.raises(SystemExit, match='general assertion still runs'):
        assembler.assemble_bytecode()


def test_assert_is_ignored_inside_an_inactive_conditional(tmp_path):
    _assemble(
        tmp_path,
        '#ifdef NEVER\n'
        '#assert malformed assertion red "must not run"\n'
        '#endif\n'
        'push a\n',
    )


def test_flow_assert_supports_a_colored_user_message(tmp_path):
    assembler = _assembler(
        tmp_path,
        '#track stack\n'
        'push\n'
        '#assert stack == 0 yellow "stack is unbalanced"\n',
        config=FLOW_CONFIG,
    )
    with pytest.raises(SystemExit) as error:
        assembler.assemble_bytecode()
    assert 'stack is unbalanced' in str(error.value)
    assert '\x1b[33m' in str(error.value)
    diagnostic = assembler.model.diagnostic_reporter.diagnostics[-1]
    assert diagnostic.category == 'flow'
    assert diagnostic.message == 'stack is unbalanced'


def test_flow_assert_resolves_preprocessor_values(tmp_path):
    _assemble(
        tmp_path,
        '#define EXPECTED 1\n'
        '#track stack\n'
        'push\n'
        '#assert stack == EXPECTED\n'
        '#assert COUNTER(stack) == EXPECTED\n'
        '#endtrack stack exit=1\n',
        config=FLOW_CONFIG,
    )


def test_explicit_flow_assert_does_not_macro_replace_its_counter_name(tmp_path):
    _assemble(
        tmp_path,
        '#define stack 99\n'
        '#track stack\n'
        'push\n'
        '#assert COUNTER(stack) == 1\n'
        '#endtrack stack exit=1\n',
        config=FLOW_CONFIG,
    )


def test_explicit_flow_assert_requires_a_flow_enabled_isa(tmp_path):
    assembler = _assembler(
        tmp_path,
        '#assert COUNTER(stack) == 0\npush a\n',
    )
    with pytest.raises(
        SystemExit,
        match='instruction set does not enable flow counters',
    ):
        assembler.assemble_bytecode()


def test_flow_dependent_assert_skips_general_evaluation(tmp_path, monkeypatch):
    """A flow-dependent assert must never invoke general condition evaluation.

    Bug (robustness): the bare-name flow shorthand (``#assert stack == 1``)
    still computed a throwaway general result at parse time because the gate
    checked ``_uses_explicit_flow`` rather than ``_is_flow_dependent``.
    Harmless while the fallback string comparison cannot fail, but fragile:
    any future change to general-evaluation semantics would silently apply to
    flow asserts too. General evaluation belongs to general asserts only.
    """
    from bespokeasm.assembler.preprocessor.condition import IfPreprocessorCondition

    original = IfPreprocessorCondition.evaluate
    calls = []

    def counting_evaluate(self, preprocessor):
        calls.append(self)
        return original(self, preprocessor)

    monkeypatch.setattr(IfPreprocessorCondition, 'evaluate', counting_evaluate)
    _assemble(
        tmp_path,
        '#track stack\npush\n#assert stack == 1\npop\n#endtrack stack\n',
        config=FLOW_CONFIG,
    )
    assert not calls, 'flow-dependent assert performed general evaluation'


def test_general_assert_failure_reports_exactly_once(tmp_path, monkeypatch):
    """A failing general assert must produce exactly one diagnostic.

    Bug (robustness): general asserts were enforced twice — once in the
    ``AssertLine`` constructor at parse time and again by the flow analyzer's
    redundant ``enforce_general()`` call. Benign under the fail-fast reporter
    (the first report exits), but a future accumulate-and-continue reporter
    would emit the same diagnostic twice. The analyzer must not re-enforce
    general asserts; the parse-time evaluation is the single enforcement
    point (which is also what keeps general asserts active under
    ``--no-static-analysis``).
    """
    from bespokeasm.assembler.diagnostic_reporter import DiagnosticReporter

    original_error = DiagnosticReporter.error

    def nonfatal_error(self, line_id, message, category='user', color=None):
        try:
            original_error(self, line_id, message, category=category, color=color)
        except SystemExit:
            pass

    monkeypatch.setattr(DiagnosticReporter, 'error', nonfatal_error)
    assembler = _assemble(
        tmp_path,
        '#define VALUE 1\n'
        '#track stack\n'
        '#assert VALUE == 2\n'
        'nop\n'
        '#endtrack stack\n',
        config=FLOW_CONFIG,
    )
    failures = [
        diagnostic
        for diagnostic in assembler.model.diagnostic_reporter.diagnostics
        if 'assertion failed' in diagnostic.message
    ]
    assert len(failures) == 1, f'expected one report, got {len(failures)}'
