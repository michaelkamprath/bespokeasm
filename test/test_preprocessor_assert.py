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
    flow_checks: bool = True,
    predefined: list[str] | None = None,
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
        predefined=predefined or [],
        flow_checks=flow_checks,
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


def test_general_assert_remains_active_when_flow_checks_is_disabled(
    tmp_path,
):
    assembler = _assembler(
        tmp_path,
        '#define VALUE 1\n'
        '#assert VALUE == 2 "general assertion still runs"\n'
        'push a\n',
        flow_checks=False,
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
    ``--no-flow-checks``).
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


def test_macro_introduced_flow_assert_is_flow_dependent(tmp_path):
    """Flow dependence must be determined from resolved operands too.

    Bug: classification ran on the raw operand text only, so with a
    command-line predefined ``FLOW_VALUE=COUNTER(stack)``, the assertion
    ``#assert FLOW_VALUE == 0`` was treated as a *general* assertion and
    rejected as an illegal preprocessor condition. A general-looking
    assertion must resolve its operands (general evaluation resolves them
    anyway) and reclassify as flow-dependent when the expansion introduces a
    flow operator.
    """
    assembler = _assemble(
        tmp_path,
        '#track stack\n'
        '#assert FLOW_VALUE == 0\n'
        'nop\n'
        '#endtrack stack\n',
        config=FLOW_CONFIG,
        predefined=['FLOW_VALUE=COUNTER(stack)'],
    )
    assert not any(
        diagnostic.level == 'error'
        for diagnostic in assembler.model.diagnostic_reporter.diagnostics
    )


def test_macro_introduced_flow_assert_is_ignored_when_analysis_disabled(tmp_path):
    """The reclassified flow assertion is analysis-only under -A.

    Bug companion: the same macro-introduced flow assertion failed under
    ``--no-flow-checks`` instead of being ignored like a directly written
    flow assertion.
    """
    assembler = _assemble(
        tmp_path,
        '#assert FLOW_VALUE == 0\n'
        'nop\n',
        config=FLOW_CONFIG,
        flow_checks=False,
        predefined=['FLOW_VALUE=COUNTER(stack)'],
    )
    assert not any(
        diagnostic.level == 'error'
        for diagnostic in assembler.model.diagnostic_reporter.diagnostics
    )


def test_macro_introduced_flow_assert_requires_flow_enabled_isa(tmp_path):
    """A macro-introduced flow assertion is gated like a directly written one."""
    assembler = _assembler(
        tmp_path,
        '#assert FLOW_VALUE == 0\nnop\n',
        config=NO_FLOW_CONFIG,
        predefined=['FLOW_VALUE=COUNTER(stack)'],
    )
    with pytest.raises(SystemExit, match='does not enable flow counters'):
        assembler.assemble_bytecode()


def test_macro_introduced_flow_assert_tolerates_cyclic_sibling_operand(tmp_path):
    """Classification must not resolve operand values at all.

    Bug: flow dependence was determined by *resolving* both operands, so a
    macro cycle in the sibling operand of a macro-introduced flow reference
    (``#assert FLOW_VALUE == LOOP_A`` with cyclic ``LOOP_A``/``LOOP_B``)
    failed under ``--no-flow-checks`` even though the assertion is
    flow-dependent and must be ignored. Classification now uses a
    cycle-tolerant dependency scan over macro values — no expansion — so an
    ignored assertion never evaluates its operands, whichever side carries
    the cycle. With analysis enabled the assertion is genuinely used, so the
    cyclic operand still errors with the canonical diagnostic.
    """
    sources = {
        'rhs-cycle': (
            '#define LOOP_A LOOP_B\n'
            '#define LOOP_B LOOP_A\n'
            '#assert FLOW_VALUE == LOOP_A\n'
            'nop\n'
        ),
        'lhs-cycle': (
            '#define LOOP_A LOOP_B\n'
            '#define LOOP_B LOOP_A\n'
            '#assert LOOP_A == FLOW_VALUE\n'
            'nop\n'
        ),
    }
    for name, source in sources.items():
        SymbolScope._global_scope = None
        assembler = _assemble(
            tmp_path,
            source,
            config=FLOW_CONFIG,
            flow_checks=False,
            predefined=['FLOW_VALUE=COUNTER(stack)'],
        )
        assert not any(
            diagnostic.level == 'error'
            for diagnostic in assembler.model.diagnostic_reporter.diagnostics
        ), f'{name} was not ignored under --no-flow-checks'

    SymbolScope._global_scope = None
    enabled = _assembler(
        tmp_path,
        '#define LOOP_A LOOP_B\n'
        '#define LOOP_B LOOP_A\n'
        '#track stack\n'
        '#assert FLOW_VALUE == LOOP_A\n'
        'nop\n'
        '#endtrack stack\n',
        config=FLOW_CONFIG,
        predefined=['FLOW_VALUE=COUNTER(stack)'],
    )
    with pytest.raises(SystemExit, match='indirectly referring to itself'):
        enabled.assemble_bytecode()


def test_macro_expanding_to_bare_flow_operator_name(tmp_path):
    """A macro may expand to a complete flow expression, never a bare operator.

    Bug: with ``#define FLOW_FN COUNTER``, the assertion
    ``#assert FLOW_FN(stack) == 0`` assembled the operator from two fragments
    (the name from the macro value, the parenthesis from the expansion
    context). The dependency scan saw neither fragment as a flow operator, so
    the assertion was classified general and failed with the misleading
    "flow expressions are not allowed in preprocessor condition expressions"
    — even under ``--no-flow-checks``.

    Rule (2026-07): flow operator names must be written literally as complete
    calls; a macro value may *be* a complete flow expression, but a macro
    that expands to a bare operator name is rejected at its point of use with
    a dedicated diagnostic. For classification the bare name counts as flow
    dependence, so under ``--no-flow-checks`` the assertion is ignored
    like any other flow assertion.
    """
    assembler = _assemble(
        tmp_path,
        '#define FLOW_FN COUNTER\n'
        '#assert FLOW_FN(stack) == 0\n'
        'nop\n',
        config=FLOW_CONFIG,
        flow_checks=False,
    )
    assert not any(
        diagnostic.level == 'error'
        for diagnostic in assembler.model.diagnostic_reporter.diagnostics
    )

    SymbolScope._global_scope = None
    enabled = _assembler(
        tmp_path,
        '#define FLOW_FN COUNTER\n'
        '#track stack\n'
        '#assert FLOW_FN(stack) == 0\n'
        'nop\n'
        '#endtrack stack\n',
        config=FLOW_CONFIG,
    )
    with pytest.raises(
        SystemExit,
        match='forms a flow operator call from separate fragments',
    ):
        enabled.assemble_bytecode()


def test_bare_flow_keyword_outside_call_position_is_ordinary(tmp_path):
    """Bare-operator detection applies only to call position.

    Bug: any macro value containing a flow operator keyword classified the
    assertion as flow-dependent, so this valid general assertion on a
    *non-flow* ISA — where these words are ordinary identifiers — failed with
    "this instruction set does not enable flow counters". The split-call
    hazard exists only when expansion supplies the operator name immediately
    before a parenthesis (``FLOW_FN(stack)``); a keyword used as a plain
    value, on either side of the comparison, stays a general assertion.
    """
    assembler = _assemble(
        tmp_path,
        '#define FLAVOR COUNTER\n'
        '#assert FLAVOR == COUNTER\n'
        'push a\n',
        config=NO_FLOW_CONFIG,
    )
    assert not any(
        diagnostic.level == 'error'
        for diagnostic in assembler.model.diagnostic_reporter.diagnostics
    )
