"""MOS 6502 milestone 6: the MOS 6502 and WDC W65C02S configs.

``config_files/mos6502`` holds copies of ``examples/mos6502/mos6502.yaml`` and ``w65c02.yaml``
(re-copy them when the examples change) and bytes captured from ca65 2.18, which the tests
compare against; they never run ca65."""
import contextlib
import importlib.resources as pkg_resources
import io
import json

import pytest
from bespokeasm.assembler.engine import Assembler
from bespokeasm.assembler.line_object.instruction_line import InstructionLine
from bespokeasm.assembler.symbol_scope import SymbolScope

from test import config_files
from test.isa_configs import json_config_copy
from test.isa_configs import load_config

FIXTURES = pkg_resources.files(config_files).joinpath('mos6502')
CONFIGS = {'6502': FIXTURES.joinpath('mos6502.yaml'), '65C02': FIXTURES.joinpath('w65c02.yaml')}


@pytest.fixture(autouse=True)
def _reset_assembler_state():
    InstructionLine.reset_instruction_pattern_cache()
    SymbolScope._global_scope = None
    yield
    SymbolScope._global_scope = None


def _fixture(name: str) -> dict:
    return json.loads(FIXTURES.joinpath(name).read_text())


def _assemble(tmp_path, cpu: str, source: str, start: int = 0) -> tuple[bytes, str]:
    """The binary from ``start`` and what the assembler wrote to stderr."""
    InstructionLine.reset_instruction_pattern_cache()
    SymbolScope._global_scope = None
    (tmp_path / 'main.a65').write_text(source)
    stderr = io.StringIO()
    assembler = Assembler(
        str(tmp_path / 'main.a65'), json_config_copy(CONFIGS[cpu], tmp_path), True, str(tmp_path / 'out.bin'),
        start, None, 0, False, None, None, 0, [], [],
    )
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(stderr):
        assembler.assemble_bytecode()
    return (tmp_path / 'out.bin').read_bytes(), stderr.getvalue()


def _error(tmp_path, cpu: str, source: str) -> str:
    with pytest.raises(SystemExit) as info:
        _assemble(tmp_path, cpu, source)
    return str(info.value)


@pytest.mark.parametrize(('cpu', 'fixture', 'opcodes'), [
    ('6502', 'ca65-opcodes-6502.json', 151),
    ('65C02', 'ca65-opcodes-65c02.json', 212),
])
def test_every_opcode_matches_ca65(tmp_path, cpu, fixture, opcodes):
    data = _fixture(fixture)
    lines = data['lines']
    source = f'.org {data["origin"]}\n' + ''.join(f'{line["source"]}\n' for line in lines)
    binary, _ = _assemble(tmp_path, cpu, source, start=data['origin'])
    offset = 0
    mismatches = []
    for line in lines:
        want = line['bytes'].split()
        got = binary[offset:offset + len(want)].hex(' ').upper().split()
        if got != want:
            mismatches.append(f'{line["source"]}: ca65 {" ".join(want)}, BespokeASM {" ".join(got)}')
        offset += len(want)
    assert mismatches == []
    assert len(binary) == offset
    assert len({line['bytes'].split()[0] for line in lines}) == opcodes


@pytest.mark.parametrize(('cpu', 'fixture'), [('6502', 'ca65-program-6502.json'), ('65C02', 'ca65-program-65c02.json')])
def test_programs_match_ca65(tmp_path, cpu, fixture):
    data = _fixture(fixture)
    binary, stderr = _assemble(tmp_path, cpu, '\n'.join(data['source']) + '\n', start=data['origin'])
    assert binary.hex(' ').upper() == data['bytes']
    assert stderr == ''


def test_a_6502_program_assembles_the_same_on_the_65c02(tmp_path):
    data = _fixture('ca65-program-6502.json')
    binary, _ = _assemble(tmp_path, '65C02', '\n'.join(data['source']) + '\n', start=data['origin'])
    assert binary.hex(' ').upper() == data['bytes']


@pytest.mark.parametrize(('source', 'expected'), [
    ('stz $10', 'unknown instruction "stz"'),
    ('lda ($12)', 'parentheses around the whole operand select another form here; expected (address, x)'),
    ('jmp ($1234,x)', 'expected an address, or (address)'),
    ('inc', 'instruction "inc" takes 1 or 2 operands, but 0 were given'),
    ('bit #$80', '"#" marks an immediate value, which this operand does not take'),
    # Every variant failing at the operand says what it could have been.
    ('sta #$10', 'expected an address, or (address, x)'),
])
def test_the_6502_rejects_65c02_and_invalid_forms(tmp_path, source, expected):
    assert expected in _error(tmp_path, '6502', f'{source}\n')


@pytest.mark.parametrize(('source', 'expected'), [
    ('stx $1234,y', '"$1234" is $1234, outside memory zone ZERO_PAGE'),   # there is no stx absolute,y
    ('lda ($1234),y', 'value 4660 is out of range for bit_size 8'),
    ('lda #256', 'value 256 is out of range for bit_size 8'),
    ('bne $9000', 'Relative address offset is larger than configured maximum value of 127'),
])
def test_values_that_dont_fit_their_form_are_errors(tmp_path, source, expected):
    assert expected in _error(tmp_path, '6502', f'.org $8000\n{source}\n')


@pytest.mark.parametrize('cpu', ['6502', '65C02'])
def test_a_zero_page_label_defined_later_selects_zero_page(tmp_path, cpu):
    # ca65 uses absolute for a forward reference; BespokeASM selects zero page once the label is placed.
    source = '.org $8000\nlda counter\nsta counter,x\n#mute\n.memzone ZERO_PAGE\n.org $40\ncounter: .byte 0\n'
    assert _assemble(tmp_path, cpu, source, start=0x8000)[0] == bytes([0xA5, 0x40, 0x95, 0x40])


@pytest.mark.parametrize('cpu', ['6502', '65C02'])
def test_flow_counters_track_the_stack_and_cycles(tmp_path, cpu):
    source = (
        '.org $8000\n'
        '#track stack mode=called\n'
        '#track cycles\n'
        'sub: pha\n'                  # 3 cycles, stack 1
        '    lda #1\n'                # 2
        '    sta $10\n'               # 3
        '    pla\n'                   # 4, stack 0
        '#assert stack == 0\n'
        '#endtrack cycles exit=12\n'
        '    rts\n'
    )
    _, stderr = _assemble(tmp_path, cpu, source, start=0x8000)
    assert stderr == ''


def test_function_names_can_name_symbols(tmp_path):
    """LSB, BYTE0 and the flow functions COUNTER and COORDINATE are functions only when written
    as a call, so 6502 source may use their names for its own labels and constants."""
    source = (
        'COUNTER = $2E\n'
        'LSB = $10\n'
        '.org $0200\n'
        '#track stack mode=called\n'
        'BYTE0:  inc COUNTER\n'
        '        lda #LSB(BYTE0)\n'
        '        lda #BYTE1(COORDINATE)\n'
        '        pha\n'
        '#assert COUNTER(stack) == 1\n'
        '        pla\n'
        '        rts\n'
        'COORDINATE: .byte LSB\n'
    )
    binary, _ = _assemble(tmp_path, '65C02', source, start=0x0200)
    assert binary.hex(' ') == 'e6 2e a9 00 a9 02 48 68 60 10'


def test_an_unbalanced_subroutine_is_reported(tmp_path):
    source = '.org $8000\n#track stack mode=called\nsub: pha\n    rts\n'
    assert 'flow counter "stack"' in _error(tmp_path, '6502', source)


@pytest.mark.parametrize('cpu', ['6502', '65C02'])
def test_every_instruction_form_is_documented(cpu):
    """Each instruction has a category, title and description, and each form a title (its
    addressing mode) and a cycle count, which the `cycles` flow counter reads."""
    config = load_config(CONFIGS[cpu])
    undocumented = []
    for mnemonic, instruction in config['instructions'].items():
        documentation = instruction['documentation']
        if not all(documentation.get(key) for key in ('category', 'title', 'description')):
            undocumented.append(mnemonic)
        forms = instruction.get('variants') or [instruction]
        for form in forms:
            form_documentation = form['documentation'] if 'variants' in instruction else documentation
            if 'cycles' not in form_documentation or ('variants' in instruction and not form_documentation.get('title')):
                undocumented.append(f'{mnemonic} {form.get("operands")}')
    assert undocumented == []
