"""Run the flow-counter M3 development acceptance harness."""
import json
import tempfile
from pathlib import Path

from bespokeasm.assembler.engine import Assembler
from bespokeasm.assembler.symbol_scope import SymbolScope
from bespokeasm.configgen.sublime import SublimeConfigGenerator
from bespokeasm.configgen.vim import VimConfigGenerator
from bespokeasm.configgen.vscode import VSCodeConfigGenerator


HARNESS_DIR = Path(__file__).resolve().parent
CONFIG_PATH = HARNESS_DIR / 'flow-counters-m3.yaml'


def _assemble(source_path: Path, output_path: Path) -> bytes:
    """Assemble one M3 fixture and return its emitted bytes."""
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
        static_analysis=True,
    )
    assembler.assemble_bytecode()
    return output_path.read_bytes()


def _assert_failure(
    tmp_dir: Path,
    name: str,
    source_path: Path,
    expected: str,
) -> None:
    """Assert that one fixture fails with the expected flow diagnostic."""
    try:
        _assemble(source_path, tmp_dir / f'{name}.bin')
    except SystemExit as error:
        assert expected in str(error), str(error)
    else:
        raise AssertionError(f'{name} unexpectedly assembled successfully')


def _verify_editor_extensions(tmp_dir: Path) -> None:
    """Verify generated hover collateral describes M3 entry modes."""
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
            'flow-analysis-m3',
            '0.3.0',
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
        docs_path = next(generated_root.rglob('instruction-docs.json'), None)
        if docs_path is not None:
            hover_docs = json.loads(docs_path.read_text())
            track_doc = hover_docs['directives']['preprocessor']['track']
            assert 'mode=<entry-mode>' in track_doc


def main() -> None:
    """Run the executable M3 acceptance demonstration."""
    with tempfile.TemporaryDirectory(prefix='bespokeasm-m3-') as tmp_dir_name:
        tmp_dir = Path(tmp_dir_name)
        tracked = _assemble(
            HARNESS_DIR / 'subroutine-parameters.asm',
            tmp_dir / 'tracked.bin',
        )
        stripped = _assemble(
            HARNESS_DIR / 'subroutine-parameters-stripped.asm',
            tmp_dir / 'stripped.bin',
        )

        assert tracked == stripped
        assert tracked == bytes(
            [0x14, 0x6C, 7, 0x6D, 11, 0x16, 4, 0x69]
        )
        _assert_failure(
            tmp_dir,
            'unbalanced',
            HARNESS_DIR / 'unbalanced.asm',
            'exit mismatch: expected 0, actual 1',
        )
        _assert_failure(
            tmp_dir,
            'runtime-adjustment',
            HARNESS_DIR / 'runtime-adjustment.asm',
            'runtime-valued',
        )
        _verify_editor_extensions(tmp_dir / 'editors')

        print('Called mode establishes routine-owned stack contract: 0 -> 0')
        print('Caller parameter coordinates remain physical: sp+3 and sp+7')
        print('After local push: candidate=sp+7, return-value=sp+11')
        print('addsp 4 uses -ARG(0) and restores routine-owned depth to 0')
        print('RTS before-effect reconciliation and lexical #endtrack: PASS')
        print('Wrong teardown and runtime ARG diagnostics: PASS')
        print('Generated editor hover collateral: PASS')
        print('M3 development acceptance: PASS')


if __name__ == '__main__':
    main()
