"""Run the flow-counter M2 development acceptance harness."""
import json
import tempfile
from pathlib import Path

from bespokeasm.assembler.engine import Assembler
from bespokeasm.assembler.symbol_scope import SymbolScope
from bespokeasm.configgen.sublime import SublimeConfigGenerator
from bespokeasm.configgen.vim import VimConfigGenerator
from bespokeasm.configgen.vscode import VSCodeConfigGenerator


HARNESS_DIR = Path(__file__).resolve().parent
CONFIG_PATH = HARNESS_DIR / 'flow-counters-m2.yaml'


def _assemble(source_path: Path, output_path: Path, flow_checks: bool = True) -> bytes:
    """Assemble one fixture and return its emitted bytes."""
    SymbolScope._global_scope = None
    assembler = Assembler(
        source_file=str(source_path),
        config_file=str(CONFIG_PATH),
        generate_binary=True,
        output_file=str(output_path),
        binary_start=0,
        binary_end=None,
        binary_fill_value=0,
        enable_pretty_print=False,
        pretty_print_format=None,
        pretty_print_output=None,
        is_verbose=0,
        include_paths=[str(HARNESS_DIR)],
        predefined=[],
        flow_checks=flow_checks,
    )
    assembler.assemble_bytecode()
    return output_path.read_bytes()


def _assert_failure(
    tmp_dir: Path,
    name: str,
    source_path: Path,
    expected: str,
    flow_checks: bool = True,
) -> None:
    """Assert that one fixture fails with the expected diagnostic text."""
    try:
        _assemble(
            source_path,
            tmp_dir / f'{name}.bin',
            flow_checks=flow_checks,
        )
    except SystemExit as error:
        assert expected in str(error), str(error)
    else:
        raise AssertionError(f'{name} unexpectedly assembled successfully')


def _verify_editor_extensions(tmp_dir: Path) -> None:
    """Verify M2 grammar and hover collateral in all generated editors."""
    for generator_class in (
        VSCodeConfigGenerator,
        SublimeConfigGenerator,
        VimConfigGenerator,
    ):
        destination = tmp_dir / generator_class.__name__
        generator = generator_class(
            str(CONFIG_PATH),
            0,
            str(destination),
            'flow-analysis-m2',
            '0.2.0',
            'flowasm',
        )
        if generator_class is SublimeConfigGenerator:
            destination.mkdir(parents=True)
            generator._generate_files_in_dir(str(destination))
            generated_root = destination
        else:
            generator.generate()
            generated_root = (
                destination / 'extensions' / generator.language_name
                if generator_class is VSCodeConfigGenerator
                else destination
            )
        generated = '\n'.join(
            path.read_text(errors='ignore')
            for path in generated_root.rglob('*')
            if path.is_file()
        )
        assert all(
            token in generated
            for token in ('COORDINATE', 'COUNTER', 'OFFSET', ':=')
        )
        docs_path = next(generated_root.rglob('instruction-docs.json'), None)
        if docs_path is not None:
            hover_docs = json.loads(docs_path.read_text())
            assert {'COORDINATE', 'COUNTER', 'OFFSET'} <= set(
                hover_docs['expression_functions'],
            )
            assert ':=' in hover_docs['directives']['counter_coordinate']


def main() -> None:
    """Run the executable M2 acceptance demonstration."""
    with tempfile.TemporaryDirectory(prefix='bespokeasm-m2-') as tmp_dir_name:
        tmp_dir = Path(tmp_dir_name)
        parameters = _assemble(
            HARNESS_DIR / 'subroutine-parameters.asm',
            tmp_dir / 'parameters.bin',
        )
        parameters_stripped = _assemble(
            HARNESS_DIR / 'subroutine-parameters-stripped.asm',
            tmp_dir / 'parameters-stripped.bin',
        )
        parameters_with_local = _assemble(
            HARNESS_DIR / 'subroutine-parameters-with-local.asm',
            tmp_dir / 'parameters-with-local.bin',
        )
        parameters_with_local_stripped = _assemble(
            HARNESS_DIR / 'subroutine-parameters-with-local-stripped.asm',
            tmp_dir / 'parameters-with-local-stripped.bin',
        )
        parameters_with_rts = _assemble(
            HARNESS_DIR / 'subroutine-parameters-with-rts.asm',
            tmp_dir / 'parameters-with-rts.bin',
        )
        parameters_with_rts_stripped = _assemble(
            HARNESS_DIR / 'subroutine-parameters-with-rts-stripped.asm',
            tmp_dir / 'parameters-with-rts-stripped.bin',
        )
        cycles = _assemble(HARNESS_DIR / 'cycles.asm', tmp_dir / 'cycles.bin')
        disabled = _assemble(
            HARNESS_DIR / 'disabled-unused.asm',
            tmp_dir / 'disabled.bin',
            flow_checks=False,
        )

        assert parameters == parameters_stripped
        assert parameters_with_local == parameters_with_local_stripped
        assert parameters_with_rts == parameters_with_rts_stripped
        assert parameters == bytes([0x6C, 3, 0x6D, 7])
        assert parameters_with_local == bytes([0x14, 0x6C, 7, 0x6D, 11, 0x15])
        assert parameters_with_rts == bytes(
            [0x14, 0x6C, 7, 0x6D, 11, 0x15, 0x69]
        )
        assert cycles == bytes([0, 0, 2])
        assert disabled == bytes([0])

        _assert_failure(
            tmp_dir,
            'invalidated',
            HARNESS_DIR / 'invalidated.asm',
            'saved position was crossed and is no longer live',
        )
        _assert_failure(
            tmp_dir,
            'zero-offset-invalid',
            HARNESS_DIR / 'zero-offset-invalid.asm',
            'does not permit zero coordinate offsets',
        )
        resolved_without_checks = _assemble(
            HARNESS_DIR / 'disabled-dependent.asm',
            tmp_dir / 'resolved-without-checks.bin',
            flow_checks=False,
        )
        assert resolved_without_checks == bytes([0x10, 1, 0x11])
        _verify_editor_extensions(tmp_dir / 'editors')

        print('Caller parameter offsets at entry: candidate=3, return-value=7')
        print('After 4-byte local push: candidate=7, return-value=11')
        print('Called entry 0 -> balanced locals 0 -> #endtrack -> RTS: PASS')
        print('ISA-configured zero-offset rejection: PASS')
        print('Crossed-and-replaced coordinate invalidation: PASS')
        print('Elapsed cycle OFFSET: 2')
        print('Generated editor syntax and hover docs: PASS')
        print('M2 development acceptance: PASS')


if __name__ == '__main__':
    main()
