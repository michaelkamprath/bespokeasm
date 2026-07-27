"""Run the flow-counter M0 development acceptance harness."""
import copy
import tempfile
from pathlib import Path

from bespokeasm.assembler.engine import Assembler
from bespokeasm.assembler.symbol_scope import SymbolScope
from ruamel.yaml import YAML


DEV_HARNESS_DIR = Path(__file__).resolve().parent
FLOW_CONFIG_PATH = DEV_HARNESS_DIR / 'flow-counters-m0.yaml'
SOURCE_PATH = DEV_HARNESS_DIR / 'analysis-records.asm'


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


def _assemble(config_path: Path, output_path: Path, static_analysis: bool) -> Assembler:
    SymbolScope._global_scope = None
    assembler = Assembler(
        source_file=str(SOURCE_PATH),
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
        include_paths=[str(DEV_HARNESS_DIR)],
        predefined=[],
        static_analysis=static_analysis,
    )
    assembler.assemble_bytecode()
    return assembler


def main() -> None:
    yaml = YAML(typ='safe')
    with FLOW_CONFIG_PATH.open() as config_file:
        no_flow_config = _without_flow_metadata(yaml.load(config_file))

    with tempfile.TemporaryDirectory(prefix='bespokeasm-m0-') as tmp_dir_name:
        tmp_dir = Path(tmp_dir_name)
        no_flow_path = tmp_dir / 'no-flow.yaml'
        output_yaml = YAML()
        with no_flow_path.open('w') as config_file:
            output_yaml.dump(no_flow_config, config_file)

        enabled = _assemble(FLOW_CONFIG_PATH, tmp_dir / 'enabled.bin', True)
        disabled = _assemble(FLOW_CONFIG_PATH, tmp_dir / 'disabled.bin', False)
        no_feature = _assemble(no_flow_path, tmp_dir / 'no-feature.bin', True)

        index = enabled.analysis_source_index
        assert index is not None
        assert len(index.records) == 6
        immediate, register, branch, macro_load, macro_nop, target_nop = index.records
        assert immediate.source_mnemonic == 'move'
        assert immediate.canonical_mnemonic == 'load'
        assert immediate.variant_number == 1
        assert immediate.semantics['flow_effects']['stack'] == 1
        assert immediate.source_identity.line_object_ordinal == 1
        assert register.source_identity.line_object_ordinal == 2
        assert register.operands[0].semantic_kind.value == 'runtime_register'
        assert branch.parsed_operand_expressions[0] is not None
        assert macro_load.source_identity.macro_path == (('load_and_nop', 0),)
        assert macro_nop.source_identity.macro_path == (('load_and_nop', 1),)
        assert target_nop.source_identity.line_object_ordinal == 1
        assert disabled.analysis_source_index is None
        assert no_feature.analysis_source_index is None
        assert (tmp_dir / 'enabled.bin').read_bytes() == (
            tmp_dir / 'disabled.bin'
        ).read_bytes()
        assert (tmp_dir / 'enabled.bin').read_bytes() == (
            tmp_dir / 'no-feature.bin'
        ).read_bytes()

        print('Retained records:')
        for record in index.records:
            macro_path = record.source_identity.macro_path or '-'
            print(
                f'  {record.source_mnemonic} -> {record.canonical_mnemonic}; '
                f'variant={record.variant_number}; '
                f'ordinal={record.source_identity.line_object_ordinal}; '
                f'macro_path={macro_path}; '
                f'operands={tuple(operand.semantic_kind.value for operand in record.operands)}'
            )
        print('M0 development acceptance: PASS')


if __name__ == '__main__':
    main()
