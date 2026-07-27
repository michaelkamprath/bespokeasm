import copy
import os
import subprocess
import sys
from pathlib import Path

import bespokeasm.assembler.analysis as analysis_module
import bespokeasm.assembler.bytecode.assembled as assembled_module
import bespokeasm.assembler.bytecode.generator.instruction as instruction_generator_module
import bespokeasm.assembler.flow_analysis as flow_analysis_module
import pytest
from bespokeasm.assembler.analysis import ExpressionUseContext
from bespokeasm.assembler.analysis import FrozenExpression
from bespokeasm.assembler.analysis import OperandSemanticKind
from bespokeasm.assembler.analysis import SourceIdentity
from bespokeasm.assembler.diagnostic_reporter import DiagnosticReporter
from bespokeasm.assembler.engine import Assembler
from bespokeasm.assembler.line_identifier import LineIdentifier
from bespokeasm.assembler.line_object.instruction_line import InstructionLine
from bespokeasm.assembler.model import AssemblerModel
from bespokeasm.assembler.symbol_scope import SymbolScope
from bespokeasm.cli import build_cli
from bespokeasm.cli import CommandHandlers
from bespokeasm.expression import parse_deferred_flow_expression
from bespokeasm.expression import parse_expression
from bespokeasm.expression import TokenType
from click.testing import CliRunner
from ruamel.yaml import YAML

PROJECT_ROOT = Path(__file__).resolve().parents[1]
M0_DEV_HARNESS_DIR = PROJECT_ROOT / 'dev' / 'flow-counters-m0'
FLOW_CONFIG_PATH = M0_DEV_HARNESS_DIR / 'flow-counters-m0.yaml'
FLOW_SOURCE_PATH = M0_DEV_HARNESS_DIR / 'analysis-records.asm'


@pytest.fixture(autouse=True)
def _reset_global_symbol_scope():
    SymbolScope._global_scope = None
    yield
    SymbolScope._global_scope = None


def _load_flow_config() -> dict:
    yaml = YAML(typ='safe')
    with FLOW_CONFIG_PATH.open() as config_file:
        return yaml.load(config_file)


def _write_config(tmp_path: Path, config: dict, filename: str = 'isa.yaml') -> Path:
    path = tmp_path / filename
    yaml = YAML()
    with path.open('w') as config_file:
        yaml.dump(config, config_file)
    return path


def _assembler(
    tmp_path: Path,
    config_path: Path,
    source: str,
    *,
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
    assembler.assemble_bytecode()
    return assembler


def _without_flow_metadata(config: dict) -> dict:
    config = copy.deepcopy(config)
    config.pop('flow_counters')
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


def test_m0_records_variants_operands_expressions_ordinals_and_macro_constituents(tmp_path):
    source = FLOW_SOURCE_PATH.read_text()
    assembler = _assembler(tmp_path, FLOW_CONFIG_PATH, source)

    index = assembler.analysis_source_index
    assert index is not None
    assert len(index.nodes) == 6
    assert len(index.records) == 6

    immediate, register, branch, macro_load, macro_nop, target_nop = index.records
    assert immediate.source_mnemonic == 'move'
    assert immediate.canonical_mnemonic == 'load'
    assert immediate.source_identity.line_object_ordinal == 1
    assert register.source_identity.line_object_ordinal == 2
    assert immediate.selected_variant is register.selected_variant
    assert immediate.variant_number == 1
    assert immediate.semantics['flow_transfer'] == 'none'
    assert immediate.semantics['flow_effects']['stack'] == 1
    assert immediate.semantics['documentation']['cycles'] == 2
    with pytest.raises(TypeError):
        immediate.semantics['flow_transfer'] = 'return'
    with pytest.raises(TypeError):
        immediate.semantics['flow_effects']['stack'] = 2

    assert immediate.operands[0].semantic_kind is OperandSemanticKind.COMPILE_TIME_EXPRESSION
    assert immediate.operands[0].expression is not None
    assert immediate.operands[0].expression_context is ExpressionUseContext.OPERAND_VALUE
    assert register.operands[0].semantic_kind is OperandSemanticKind.RUNTIME_REGISTER
    assert register.operands[0].expression is None
    # the retained expression tree must be a faithful snapshot, not merely
    # non-None: `jmp target + 0` freezes as (+ (label target) (num 0))
    branch_expression = branch.parsed_operand_expressions[0]
    assert branch_expression is not None
    assert branch_expression.token_type is TokenType.T_PLUS
    assert branch_expression.left.token_type is TokenType.T_LABEL
    assert branch_expression.left.value == 'target'
    assert branch_expression.right.token_type is TokenType.T_NUM
    assert branch_expression.right.value == 0

    assert macro_load.source_identity.macro_path == (('load_and_nop', 0),)
    assert macro_nop.source_identity.macro_path == (('load_and_nop', 1),)
    assert target_nop.source_identity.line_object_ordinal == 1


def test_m0_records_are_gated_and_bytecode_is_invariant(tmp_path):
    source = FLOW_SOURCE_PATH.read_text()
    enabled = _assembler(
        tmp_path,
        FLOW_CONFIG_PATH,
        source,
        output_name='enabled.bin',
    )
    SymbolScope._global_scope = None
    disabled = _assembler(
        tmp_path,
        FLOW_CONFIG_PATH,
        source,
        static_analysis=False,
        output_name='disabled.bin',
    )
    SymbolScope._global_scope = None
    no_flow_config = _write_config(
        tmp_path,
        _without_flow_metadata(_load_flow_config()),
        'no-flow.yaml',
    )
    no_feature = _assembler(
        tmp_path,
        no_flow_config,
        source,
        output_name='no-feature.bin',
    )

    assert enabled.analysis_source_index is not None
    assert disabled.analysis_source_index is None
    assert no_feature.analysis_source_index is None
    assert enabled.model.instructions.get('load').variants[0].analysis_semantics_retained
    assert not disabled.model.instructions.get('load').variants[0].analysis_semantics_retained
    assert not no_feature.model.instructions.get('load').variants[0].analysis_semantics_retained
    assert (tmp_path / 'enabled.bin').read_bytes() == (tmp_path / 'disabled.bin').read_bytes()
    assert (tmp_path / 'enabled.bin').read_bytes() == (tmp_path / 'no-feature.bin').read_bytes()


@pytest.mark.parametrize('context', list(ExpressionUseContext))
def test_m0_deferred_flow_expressions_are_recognized_and_context_tagged(context):
    line_id = LineIdentifier(7, 'deferred-flow.asm')
    expression = 'COUNTER(stack) + OFFSET(.slot)'

    parsed = parse_deferred_flow_expression(line_id, expression, context)
    deferred_nodes = parsed.deferred_flow_nodes()

    assert tuple(node.token_type for node in deferred_nodes) == (
        TokenType.T_COUNTER,
        TokenType.T_OFFSET,
    )
    assert tuple(node.left_child.value for node in deferred_nodes) == ('stack', '.slot')
    assert all(node.expression_context is context for node in deferred_nodes)
    frozen = FrozenExpression.from_node(parsed)
    assert frozen is not None
    assert frozen.left.expression_context is context
    assert frozen.right.expression_context is context

    with pytest.raises(SyntaxError, match='flow expression has no tagged use context'):
        parse_expression(line_id, expression)


@pytest.mark.parametrize(
    ('static_analysis', 'remove_flow_metadata'),
    [
        (False, False),
        (True, True),
    ],
    ids=['analysis-disabled', 'isa-has-no-analysis-feature'],
)
def test_m0_large_dormant_compile_has_no_analysis_allocations_or_traversal(
    tmp_path,
    monkeypatch,
    static_analysis,
    remove_flow_metadata,
):
    config = _load_flow_config()
    if remove_flow_metadata:
        config = _without_flow_metadata(config)
    config['general']['address_size'] = 16
    config_path = _write_config(tmp_path, config, 'large-dormant.yaml')

    def unexpected_analysis_work(*_args, **_kwargs):
        raise AssertionError('dormant compilation performed analysis-only work')

    monkeypatch.setattr(
        analysis_module.AnalysisSourceIndex,
        'from_line_objects',
        classmethod(unexpected_analysis_work),
    )
    monkeypatch.setattr(
        SourceIdentity,
        'from_line_id',
        classmethod(unexpected_analysis_work),
    )
    monkeypatch.setattr(
        instruction_generator_module,
        'InstructionAnalysisRecord',
        unexpected_analysis_work,
    )
    # Dormant compilation must not perform the flow-usage source scan either:
    # `source_uses_flow` walks every line object, and the M0 dormant-overhead
    # acceptance criterion (case 70) is structural — no additional whole-source
    # traversal — so the scan must stay behind the analysis-enabled gate in the
    # engine rather than merely returning False.
    monkeypatch.setattr(
        flow_analysis_module.FlowLinearAnalyzer,
        'source_uses_flow',
        staticmethod(unexpected_analysis_work),
    )

    original_assembled_init = assembled_module.AssembledInstruction.__init__

    def audited_assembled_init(self, *args, **kwargs):
        original_assembled_init(self, *args, **kwargs)
        assert not hasattr(self, '_analysis_record')

    monkeypatch.setattr(
        assembled_module.AssembledInstruction,
        '__init__',
        audited_assembled_init,
    )

    original_line_init = InstructionLine.__init__

    def audited_line_init(self, *args, **kwargs):
        original_line_init(self, *args, **kwargs)
        assert not hasattr(self, '_source_identity')

    monkeypatch.setattr(InstructionLine, '__init__', audited_line_init)

    source = '\n'.join('nop' for _ in range(1024))
    assembler = _assembler(
        tmp_path,
        config_path,
        source,
        static_analysis=static_analysis,
        output_name='large-dormant.bin',
    )

    assert assembler.analysis_source_index is None
    variant = assembler.model.instructions.get('nop').variants[0]
    assert not hasattr(variant, '_semantic_config')
    assert not hasattr(variant, '_variant_num')
    assert (tmp_path / 'large-dormant.bin').stat().st_size == 1024


def test_m0_development_acceptance_harness_is_runnable():
    environment = os.environ.copy()
    environment['PYTHONPATH'] = str(PROJECT_ROOT / 'src')
    result = subprocess.run(
        [sys.executable, str(M0_DEV_HARNESS_DIR / 'verify_m0.py')],
        cwd=PROJECT_ROOT,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert 'M0 development acceptance: PASS' in result.stdout


@pytest.mark.parametrize(
    ('flag', 'expected'),
    [
        (None, True),
        ('--static-analysis', True),
        ('--no-static-analysis', False),
        ('-a', True),
        ('-A', False),
    ],
)
def test_m0_static_analysis_cli_flag_defaults_on_and_forwards_value(flag, expected):
    compile_calls = []

    def compile_handler(*args):
        compile_calls.append(args)

    def noop(*_args):
        return None

    cli = build_cli(CommandHandlers(compile_handler, noop, noop, noop, noop))
    args = ['compile', 'program.asm', '--config-file', str(FLOW_CONFIG_PATH), '--no-binary']
    if flag is not None:
        args.append(flag)
    result = CliRunner().invoke(cli, args)

    assert result.exit_code == 0, result.output
    assert compile_calls[0][-1] is expected


def test_m0_flow_warning_category_is_elevated_by_warnings_as_errors():
    reporter = DiagnosticReporter(warnings_as_errors=True)
    with pytest.raises(SystemExit, match='flow warning'):
        reporter.warn(None, 'flow warning', category='flow')
    assert reporter.diagnostics[-1].level == 'error'
    assert reporter.diagnostics[-1].category == 'flow'


@pytest.mark.parametrize(
    ('mutate', 'message'),
    [
        (
            lambda config: config['instructions']['nop']['flow_effects'].update({'missing': 1}),
            'undeclared counter "missing"',
        ),
        (
            lambda config: config.pop('flow_counters'),
            'undeclared counter "stack"',
        ),
        (
            lambda config: config['instructions']['nop'].update(
                {'flow_terminal': {'missing': 'before_effect'}}
            ),
            'undeclared counter "missing"',
        ),
        (
            lambda config: config['instructions']['nop'].update(
                {'flow_terminal': {'stack': 'during_effect'}}
            ),
            'before_effect',
        ),
        (
            lambda config: config['instructions']['nop'].update(
                {'flow_call_effects': {'missing': 0}}
            ),
            'undeclared counter "missing"',
        ),
        (
            lambda config: config['instructions']['nop'].update({'flow_transfer': 'sideways'}),
            'invalid value "sideways"',
        ),
        (
            lambda config: config['instructions']['jmp'].pop('flow_target_operand'),
            'flow_target_operand is required',
        ),
        (
            lambda config: config['instructions']['nop'].update({'flow_target_operand': 0}),
            'flow_target_operand is incompatible',
        ),
        (
            lambda config: config['instructions']['jmp']['operands']['operand_sets'].update(
                {'list': ['source']}
            ),
            'incompatible operand type',
        ),
        (
            lambda config: config['instructions']['nop'].update(
                {'flow_call_effects': {'stack': 0}}
            ),
            'only valid with flow_transfer "call"',
        ),
        (
            lambda config: config['flow_counters']['stack'].update(
                {'unknown_instructions': 'maybe'}
            ),
            'unknown_instructions',
        ),
        (
            lambda config: config['flow_counters']['stack'].update(
                {'exit_policy': 'sometimes'}
            ),
            'exit_policy',
        ),
        (
            lambda config: config['flow_counters']['stack'].update(
                {'coordinate_offsets': 'sideways'}
            ),
            'coordinate_offsets',
        ),
        (
            lambda config: config['flow_counters']['stack'].update(
                {'allow_zero_offset': 'sometimes'}
            ),
            'allow_zero_offset',
        ),
        (
            lambda config: config['instructions']['nop']['flow_effects'].update(
                {'stack': 1.5}
            ),
            'must be an integer',
        ),
    ],
)
def test_m0_flow_config_validation_is_analysis_gated(tmp_path, mutate, message):
    config = _load_flow_config()
    mutate(config)
    config_path = _write_config(tmp_path, config)

    reporter = DiagnosticReporter()
    with pytest.raises(SystemExit, match=message):
        AssemblerModel(str(config_path), 0, reporter, static_analysis=True)
    assert reporter.diagnostics[-1].category == 'flow'

    disabled_reporter = DiagnosticReporter()
    model = AssemblerModel(
        str(config_path),
        0,
        disabled_reporter,
        static_analysis=False,
    )
    assert not model.analysis_records_enabled
    assert disabled_reporter.diagnostics == ()


def test_m0_variant_semantics_merge_is_deep_for_metadata(tmp_path):
    """Bug: the variant semantics merge was shallow, dropping root nested keys.

    ``InstructionVariant`` and ``AssemblerModel._effective_instruction_configs``
    both computed ``{**root, **variant}``, so a variant overriding one key of a
    nested metadata dictionary silently discarded the root's sibling keys:
    root ``documentation: {family: load}`` plus variant ``documentation:
    {cycles: 2}`` produced merged semantics with ``family`` gone. With counter
    ``source:`` binding (e.g. ``source: documentation.cycles``, shipped in M1)
    and per-class ``flow_effects`` maps, that silently loses deltas — the
    "silently tracking nothing" failure mode the Fail Loud requirement exists
    to prevent.

    Pinned merge semantics:
    * nested metadata dictionaries (``documentation``, ``flow_effects``,
      custom fields) merge recursively key-by-key; the variant wins per key;
    * a variant can never remove a root key: an explicit ``null`` override is
      ignored (decided 2026-07: no removal escape hatch);
    * ``bytecode`` and ``operands`` replace wholesale, mirroring the emission
      machinery, which reads them only from the selected variant's config;
    * the raw ``variants`` list never appears in merged semantics (previously
      it leaked into variant 0 of a root-bytecode-plus-variants instruction);
    * the retained ``semantic_config`` and the validation-side
      ``_effective_instruction_configs`` agree exactly — validation must check
      the same data the analyzer consumes.
    """
    config = _load_flow_config()
    config['flow_counters']['aux'] = {
        'unknown_instructions': 'ignore',
        'exit_policy': 'balanced',
    }
    load_config = config['instructions']['load']
    load_config['flow_effects'] = {'stack': 0, 'aux': 2}
    load_config['variants'][0]['flow_effects'] = {'stack': 1}
    load_config['variants'][0]['documentation'] = {'cycles': 2, 'family': None}
    config['instructions']['wide'] = {
        'flow_effects': {'stack': 0},
        'flow_transfer': 'none',
        'documentation': {'family': 'wide'},
        'bytecode': {'value': 0x50, 'size': 8, 'suffix': {'value': 1, 'size': 8}},
        'variants': [{
            'flow_effects': {'stack': 0},
            'flow_transfer': 'none',
            'bytecode': {'value': 0x60, 'size': 7},
            'operands': {'count': 1, 'operand_sets': {'list': ['source']}},
        }],
    }
    config_path = _write_config(tmp_path, config, 'deep-merge.yaml')
    model = AssemblerModel(str(config_path), 0, DiagnosticReporter(), static_analysis=True)

    load_semantics = model.instructions.get('load').variants[0].semantic_config
    # variant overrides merge into root nested metadata instead of replacing it
    assert load_semantics['documentation'] == {'family': 'load', 'cycles': 2}
    # per-class effect maps retain root classes the variant does not mention
    assert load_semantics['flow_effects'] == {'stack': 1, 'aux': 2}

    wide_variants = model.instructions.get('wide').variants
    # the raw variants list is not semantic data
    assert 'variants' not in wide_variants[0].semantic_config
    assert 'variants' not in wide_variants[1].semantic_config
    # bytecode/operands mirror emission: the variant's values replace wholesale
    assert wide_variants[1].semantic_config['bytecode'] == {'value': 0x60, 'size': 7}
    # but semantic metadata still inherits
    assert wide_variants[1].semantic_config['documentation'] == {'family': 'wide'}

    # the validation-side merge must agree with the retained semantics
    assert AssemblerModel._effective_instruction_configs(load_config) == [
        load_semantics,
    ]
    assert AssemblerModel._effective_instruction_configs(
        config['instructions']['wide']
    ) == [
        wide_variants[0].semantic_config,
        wide_variants[1].semantic_config,
    ]


def test_m0_flow_metadata_is_validated_even_without_flow_counters_section(tmp_path):
    """Pins a deliberate design decision about flow validation and enablement.

    With static analysis enabled, per-instruction flow metadata is validated
    at config load for *every* ISA, whether or not it declares a
    ``flow_counters`` section: an instruction set must either carry a proper
    section or carry only valid (or no) flow keys. An invalid
    ``flow_transfer`` value, or ``flow_effects`` naming a counter class that
    no section declares, fails at load even though the ISA never enabled the
    feature. This is deliberately stricter than "a no-section ISA assembles
    exactly as today" for a configuration that coincidentally carries a
    malformed flow key: silently ignoring malformed flow metadata would let a
    typo'd configuration masquerade as valid. (Under ``--no-static-analysis``
    all of these checks are skipped — covered by the analysis-gating test
    above.)
    """
    config = _without_flow_metadata(_load_flow_config())
    config['instructions']['nop']['flow_transfer'] = 'garbage'
    config_path = _write_config(tmp_path, config, 'no-section-bad-transfer.yaml')
    reporter = DiagnosticReporter()
    with pytest.raises(SystemExit, match='flow_transfer has invalid value "garbage"'):
        AssemblerModel(str(config_path), 0, reporter, static_analysis=True)
    assert reporter.diagnostics[-1].category == 'flow'

    config = _without_flow_metadata(_load_flow_config())
    config['instructions']['nop']['flow_effects'] = {'stack': 1}
    config_path = _write_config(tmp_path, config, 'no-section-effects.yaml')
    reporter = DiagnosticReporter()
    with pytest.raises(SystemExit, match='names undeclared counter "stack"'):
        AssemblerModel(str(config_path), 0, reporter, static_analysis=True)
    assert reporter.diagnostics[-1].category == 'flow'

    # a *valid* flow_transfer classification on a no-section ISA is acceptable
    # (it is inert metadata; the feature remains disabled)
    config = _without_flow_metadata(_load_flow_config())
    config['instructions']['nop']['flow_transfer'] = 'none'
    config_path = _write_config(tmp_path, config, 'no-section-valid.yaml')
    model = AssemblerModel(
        str(config_path),
        0,
        DiagnosticReporter(),
        static_analysis=True,
    )
    assert not model.flow_counters_enabled
