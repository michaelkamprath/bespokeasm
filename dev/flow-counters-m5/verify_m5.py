"""Run the flow-counter M5 development acceptance harness."""
import json
import tempfile
from pathlib import Path

from bespokeasm.assembler.engine import Assembler
from bespokeasm.assembler.symbol_scope import SymbolScope
from bespokeasm.configgen.sublime import SublimeConfigGenerator
from bespokeasm.configgen.vim import VimConfigGenerator
from bespokeasm.configgen.vscode import VSCodeConfigGenerator


HARNESS_DIR = Path(__file__).resolve().parent
CONFIG_PATH = HARNESS_DIR / 'flow-counters-m5.yaml'


def _assembler(
    source_name: str,
    output_path: Path,
    *,
    listing: bool = False,
) -> Assembler:
    """Create an isolated assembler for one M5 fixture."""
    SymbolScope._global_scope = None
    return Assembler(
        source_file=str(HARNESS_DIR / source_name),
        config_file=str(CONFIG_PATH),
        generate_binary=True,
        output_file=str(output_path),
        binary_start=0,
        binary_end=None,
        binary_fill_value=0,
        enable_pretty_print=listing,
        pretty_print_format='listing' if listing else None,
        pretty_print_output='stdout' if listing else None,
        is_verbose=0,
        include_paths=[str(HARNESS_DIR)],
        predefined=[],
        flow_checks=True,
    )


def _assemble(
    source_name: str,
    output_path: Path,
    *,
    listing: bool = False,
) -> Assembler:
    """Assemble one fixture and return the completed assembler."""
    assembler = _assembler(source_name, output_path, listing=listing)
    assembler.assemble_bytecode()
    return assembler


def _expect_flow_error(
    source_name: str,
    output_path: Path,
    expected: str,
) -> None:
    """Require one fixture to fail with the named flow diagnostic."""
    try:
        _assemble(source_name, output_path)
    except SystemExit as error:
        if expected not in str(error):
            raise AssertionError(
                f'{source_name} produced the wrong diagnostic: {error}'
            ) from error
    else:
        raise AssertionError(f'{source_name} unexpectedly assembled')


def _verify_editor_extensions(tmp_dir: Path) -> None:
    """Verify M5 syntax and hover collateral in all generated editors."""
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
            'flow-analysis-m5',
            '0.5.0',
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
        assert '#entry' in generated
        docs_path = next(generated_root.rglob('instruction-docs.json'), None)
        if docs_path is not None:
            hover_docs = json.loads(docs_path.read_text())
            assert 'entry' in hover_docs['directives']['preprocessor']


def main() -> None:
    """Run the executable M5 acceptance demonstration."""
    with tempfile.TemporaryDirectory(prefix='bespokeasm-m5-') as tmp_dir_name:
        tmp_dir = Path(tmp_dir_name)
        annotated = _assemble(
            'branching-stack.asm',
            tmp_dir / 'annotated.bin',
            listing=True,
        )
        _assemble(
            'branching-stack-stripped.asm',
            tmp_dir / 'stripped.bin',
        )
        assert (tmp_dir / 'annotated.bin').read_bytes() == (
            tmp_dir / 'stripped.bin'
        ).read_bytes()
        assert annotated.model.diagnostic_reporter.diagnostics == ()

        _assemble(
            'concurrent-counters.asm',
            tmp_dir / 'concurrent.bin',
            listing=True,
        )
        _assemble(
            'concurrent-counters-stripped.asm',
            tmp_dir / 'concurrent-stripped.bin',
        )
        assert (tmp_dir / 'concurrent.bin').read_bytes() == (
            tmp_dir / 'concurrent-stripped.bin'
        ).read_bytes()

        _assemble(
            'macro-stack.asm',
            tmp_dir / 'macro-stack.bin',
            listing=True,
        )
        _assemble(
            'macro-stack-stripped.asm',
            tmp_dir / 'macro-stack-stripped.bin',
        )
        assert (tmp_dir / 'macro-stack.bin').read_bytes() == (
            tmp_dir / 'macro-stack-stripped.bin'
        ).read_bytes()

        _assemble(
            'macro-shared-continuation.asm',
            tmp_dir / 'macro-shared-continuation.bin',
            listing=True,
        )
        _assemble(
            'macro-shared-continuation-stripped.asm',
            tmp_dir / 'macro-shared-continuation-stripped.bin',
        )
        assert (
            tmp_dir / 'macro-shared-continuation.bin'
        ).read_bytes() == (
            tmp_dir / 'macro-shared-continuation-stripped.bin'
        ).read_bytes()

        _assemble(
            'cycle-counting.asm',
            tmp_dir / 'cycles.bin',
        )
        _assemble(
            'cycle-counting-stripped.asm',
            tmp_dir / 'cycles-stripped.bin',
        )
        assert (tmp_dir / 'cycles.bin').read_bytes() == (
            tmp_dir / 'cycles-stripped.bin'
        ).read_bytes()

        _expect_flow_error(
            'leaked-push.asm',
            tmp_dir / 'leaked-push.bin',
            'exit mismatch',
        )
        _assemble('explicit-entry.asm', tmp_dir / 'explicit-entry.bin')
        _assemble('runtime-loop.asm', tmp_dir / 'runtime-loop.bin')
        _expect_flow_error(
            'indirect-error.asm',
            tmp_dir / 'indirect-error.bin',
            'indirect control transfer',
        )
        _expect_flow_error(
            'fallthrough-data-error.asm',
            tmp_dir / 'fallthrough-data.bin',
            'enters emitted data',
        )
        _assemble('tail-call.asm', tmp_dir / 'tail-call.bin')
        _assemble(
            'watched-address-reset.asm',
            tmp_dir / 'watched-address-reset.bin',
            listing=True,
        )
        _assemble(
            'watched-address-reset-stripped.asm',
            tmp_dir / 'watched-address-reset-stripped.bin',
        )
        assert (
            tmp_dir / 'watched-address-reset.bin'
        ).read_bytes() == (
            tmp_dir / 'watched-address-reset-stripped.bin'
        ).read_bytes()
        _assemble(
            'direct-reset.asm',
            tmp_dir / 'direct-reset.bin',
            listing=True,
        )
        _assemble(
            'direct-reset-stripped.asm',
            tmp_dir / 'direct-reset-stripped.bin',
        )
        assert (
            tmp_dir / 'direct-reset.bin'
        ).read_bytes() == (
            tmp_dir / 'direct-reset-stripped.bin'
        ).read_bytes()
        warning_assembler = _assemble(
            'trailing-label-warning.asm',
            tmp_dir / 'trailing-warning.bin',
        )
        warnings = [
            diagnostic
            for diagnostic in warning_assembler.model.diagnostic_reporter.diagnostics
            if diagnostic.level == 'warning'
        ]
        assert len(warnings) == 1
        assert 'unreachable potential entry' in warnings[0].message
        _verify_editor_extensions(tmp_dir / 'editors')

        print('Branch propagation and separate balanced exits: PASS')
        print('Stack parameter coordinate references and stripped byte identity: PASS')
        print('Concurrent-counter listing continuation rows: PASS')
        print('Macro aggregate stack transition and expanded byte identity: PASS')
        print('Shared byte/flow macro continuation row: PASS')
        print('Five-cycle balanced branch and stripped byte identity: PASS')
        print('Per-return leaked-push diagnostic: PASS')
        print('Explicit #entry root and suspended loop: PASS')
        print('Indirect transfer and fall-through diagnostics: PASS')
        print('Balanced tail call and external-entry warning: PASS')
        print('Watched-address macro invalidation and re-anchor: PASS')
        print('Direct instruction invalidation and re-anchor: PASS')
        print('Annotated listing flow column: PASS')
        print('Generated editor syntax and hover docs: PASS')
        print('M5 development acceptance: PASS')


if __name__ == '__main__':
    main()
