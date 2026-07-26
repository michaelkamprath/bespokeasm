"""Run the flow-counter M1 development acceptance harness."""
import json
import tempfile
from pathlib import Path

from bespokeasm.assembler.engine import Assembler
from bespokeasm.assembler.label_scope import LabelScope
from bespokeasm.configgen.vscode import VSCodeConfigGenerator


HARNESS_DIR = Path(__file__).resolve().parent
CONFIG_PATH = HARNESS_DIR / 'flow-counters-m1.yaml'


def _assemble(source_path: Path, output_path: Path, static_analysis: bool = True) -> bytes:
    """Assemble one fixture and return its emitted bytes."""
    LabelScope._global_scope = None
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
        static_analysis=static_analysis,
    )
    assembler.assemble_bytecode()
    return output_path.read_bytes()


def _assert_failure(tmp_dir: Path, name: str, source: str, expected: str, static_analysis=True):
    """Assert that generated source fails with the expected diagnostic text."""
    source_path = tmp_dir / f'{name}.asm'
    source_path.write_text(source)
    try:
        _assemble(source_path, tmp_dir / f'{name}.bin', static_analysis)
    except SystemExit as error:
        assert expected in str(error), str(error)
    else:
        raise AssertionError(f'{name} unexpectedly assembled successfully')


def _verify_editor_extension(tmp_dir: Path) -> None:
    """Generate an extension and verify M1 syntax plus hover collateral."""
    generator = VSCodeConfigGenerator(
        str(CONFIG_PATH),
        0,
        str(tmp_dir),
        'flow-analysis-m1',
        '0.1.0',
        'flowasm',
    )
    generator.generate()
    extension_dir = tmp_dir / 'extensions' / generator.language_name
    grammar = (extension_dir / 'syntaxes' / 'tmGrammar.json').read_text()
    hover_docs = json.loads(
        (extension_dir / 'instruction-docs.json').read_text(),
    )
    assert all(token in grammar for token in ('track', 'endtrack', 'COUNTER'))
    assert {'track', 'endtrack'} <= set(
        hover_docs['directives']['preprocessor'],
    )
    assert 'COUNTER' in hover_docs['expression_functions']


def main() -> None:
    """Run the executable M1 acceptance demonstration."""
    with tempfile.TemporaryDirectory(prefix='bespokeasm-m1-') as tmp_dir_name:
        tmp_dir = Path(tmp_dir_name)
        tracked = _assemble(HARNESS_DIR / 'tracked.asm', tmp_dir / 'tracked.bin')
        stripped = _assemble(HARNESS_DIR / 'stripped.asm', tmp_dir / 'stripped.bin')
        annotation_only = _assemble(
            HARNESS_DIR / 'annotation-only.asm',
            tmp_dir / 'annotation-only.bin',
            static_analysis=False,
        )
        assert tracked == stripped == annotation_only
        assert tracked == bytes([0x10, 0x80, 0x01, 0x01, 0x11])

        _assert_failure(
            tmp_dir,
            'exit-mismatch',
            '#track stack\npush\n#endtrack stack\n',
            'exit mismatch',
        )
        _assert_failure(
            tmp_dir,
            'underflow',
            '#track stack\npop\n#endtrack stack\n',
            'underflow',
        )
        _assert_failure(
            tmp_dir,
            'layout-use',
            '#track stack\n.org COUNTER(stack)\n#endtrack stack\n',
            'not allowed in layout expressions',
        )
        _assert_failure(
            tmp_dir,
            'disabled-dependency',
            '#track stack\ndepth COUNTER(stack)\n#endtrack stack\n',
            'static analysis is disabled',
            static_analysis=False,
        )
        _verify_editor_extension(tmp_dir / 'editor')

        print(f'Byte-identical output: {tracked.hex(" ")}')
        print('Generated VS Code flow syntax and hover docs: PASS')
        print('M1 development acceptance: PASS')


if __name__ == '__main__':
    main()
