"""Run the flow-counter M4 development acceptance harness."""
import tempfile
from pathlib import Path

from bespokeasm.assembler.engine import Assembler
from bespokeasm.assembler.symbol_scope import SymbolScope


HARNESS_DIR = Path(__file__).resolve().parent
CONFIG_PATH = HARNESS_DIR / 'flow-counters-m4.yaml'


def _assemble(source_path: Path, output_path: Path) -> bytes:
    """Assemble one M4 fixture and return its emitted bytes."""
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
        flow_checks=True,
    )
    assembler.assemble_bytecode()
    return output_path.read_bytes()


def main() -> None:
    """Run the executable M4 acceptance demonstration."""
    with tempfile.TemporaryDirectory(prefix='bespokeasm-m4-') as tmp_dir_name:
        tmp_dir = Path(tmp_dir_name)
        annotated = _assemble(
            HARNESS_DIR / 'manual-control.asm',
            tmp_dir / 'annotated.bin',
        )
        stripped = _assemble(
            HARNESS_DIR / 'manual-control-stripped.asm',
            tmp_dir / 'stripped.bin',
        )
        assert annotated == stripped == bytes(
            [0x10, 0x20, 0x04, 0x00, 0x00, 0x00, 0x11, 0x69]
        )

        try:
            _assemble(
                HARNESS_DIR / 'suspended-read.asm',
                tmp_dir / 'suspended-read.bin',
            )
        except SystemExit as error:
            assert 'cannot be resolved while flow counter "cycles" is suspended' in str(error)
        else:
            raise AssertionError('suspended COUNTER() read unexpectedly assembled')

        print('Concurrent stack and overlapping cycle windows: PASS')
        print('General #assert condition and optional message: PASS')
        print('Named #assert, #set, #suspend, and #resume control: PASS')
        print('Annotated/stripped byte identity: PASS')
        print('Suspended COUNTER() diagnostic: PASS')
        print('M4 development acceptance: PASS')


if __name__ == '__main__':
    main()
