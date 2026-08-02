#!/usr/bin/env python3
"""Exercise the M5.1 flow-counter documentation acceptance contract."""
from pathlib import Path
from tempfile import TemporaryDirectory

from bespokeasm.docsgen import DocumentationGenerator


PROJECT_ROOT = Path(__file__).resolve().parents[3]
HARNESS_CONFIG = Path(__file__).with_name('flow-counters-m5.1.yaml')
NON_FLOW_CONFIG = (
    PROJECT_ROOT / 'test' / 'config_files' / 'eater-sap1-isa.yaml'
)


def _generate(config_path: Path, output_path: Path) -> str:
    """Generate and return Markdown documentation for one ISA config."""
    DocumentationGenerator(str(config_path)).generate_markdown_documentation(
        str(output_path),
    )
    return output_path.read_text()


def main() -> None:
    """Verify flow docs and non-flow gating through the public docs API."""
    with TemporaryDirectory(prefix='bespokeasm-m5-1-') as temp_dir:
        output_dir = Path(temp_dir)
        flow_docs = _generate(
            HARNESS_CONFIG,
            output_dir / 'flow.md',
        )
        non_flow_docs = _generate(
            NON_FLOW_CONFIG,
            output_dir / 'non-flow.md',
        )

    required_flow_text = (
        '# Flow Counters',
        '## Data Stack Depth (`stack`)',
        '| Counter | stack | +1 physical effect. |',
        '| Counter | stack | -ARG(0) physical effect. |',
        'before the instruction effect',
        'caller-visible net effect after return: +0',
        '| Invalidated By Writes To | `0xff` |',
        (
            'Becomes indeterminate when zero-based write-target operand(s) 0 '
            'may address 0xff.'
        ),
        'Unconditionally becomes indeterminate.',
    )
    for expected in required_flow_text:
        assert expected in flow_docs, expected

    assert '# Flow Counters' not in non_flow_docs
    assert '| Counter |' not in non_flow_docs

    print('M5.1 development acceptance: PASS')


if __name__ == '__main__':
    main()
