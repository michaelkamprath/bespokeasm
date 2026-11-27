"""`.phase` and `.dephase`, which assemble code for one address while its bytes go somewhere else,
and the other assembler changes migrating Carsten Herting's programs needed."""
import contextlib
import importlib.resources as pkg_resources
import io

import pytest
from bespokeasm.assembler.engine import Assembler
from bespokeasm.assembler.line_object.instruction_line import InstructionLine
from bespokeasm.assembler.symbol_scope import SymbolScope
from intelhex import IntelHex

from test import config_files
from test.isa_configs import json_config_copy

SUBSET = pkg_resources.files(config_files).joinpath('slu4').joinpath('minimal-64x4-subset.yaml')
JPA, NOP, LDI, FPA = 0x64, 0x00, 0x74, 0x5b


@pytest.fixture(autouse=True)
def _reset_assembler_state():
    InstructionLine.reset_instruction_pattern_cache()
    SymbolScope._global_scope = None
    yield
    SymbolScope._global_scope = None


def _assemble(tmp_path, source: str, fmt: str = 'intel_hex') -> str:
    config = json_config_copy(SUBSET, tmp_path)
    (tmp_path / 'main.min64x4').write_text(source)
    assembler = Assembler(
        str(tmp_path / 'main.min64x4'), config, False, None, 0, None, 0,
        True, fmt, str(tmp_path / 'out.txt'), 0, [], [],
    )
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        assembler.assemble_bytecode()
    return (tmp_path / 'out.txt').read_text()


def _image(tmp_path, source: str) -> dict[int, int]:
    return IntelHex(io.StringIO(_assemble(tmp_path, source))).todict()


def _error(tmp_path, source: str) -> str:
    with pytest.raises(SystemExit) as exc_info:
        _assemble(tmp_path, source)
    return str(exc_info.value)


def _bytes(image: dict[int, int], start: int, count: int) -> list[int]:
    return [image[address] for address in range(start, start + count)]


# ---- .phase and .dephase ---------------------------------------------------------------------


def test_a_phase_assembles_for_its_address_while_the_bytes_continue_in_place(tmp_path):
    image = _image(tmp_path, (
        '.org 0x0010\n'
        '  .2byte App, AppEnd-App\n'
        '.phase 0xfc00\n'
        'App: jpa App\n'
        '  .2byte *\n'
        'AppEnd:\n'
    ))
    assert sorted(image) == list(range(0x10, 0x10 + 9))
    assert _bytes(image, 0x10, 9) == [0x00, 0xfc, 0x05, 0x00, JPA, 0x00, 0xfc, 0x03, 0xfc]


def test_a_new_phase_starts_where_the_image_is(tmp_path):
    image = _image(tmp_path, (
        '.org 0x0000\n'
        '.phase 0xfc00\n'
        'One: jpa One\n'
        '.phase 0xfc00\n'
        'Two: jpa Two\n'
    ))
    assert _bytes(image, 0, 6) == [JPA, 0x00, 0xfc, JPA, 0x00, 0xfc]


def test_dephase_continues_from_the_image_position_and_org_ends_a_phase(tmp_path):
    image = _image(tmp_path, (
        '.org 0x0100\n'
        '.phase 0xfc00\n'
        '  nop\n'
        '.dephase\n'
        'Here: .2byte *, Here\n'
        '.phase 0xfc00\n'
        '  nop\n'
        '.org 0x0200\n'
        'There: .2byte There\n'
    ))
    assert _bytes(image, 0x100, 6) == [NOP, 0x01, 0x01, 0x01, 0x01, NOP]
    assert _bytes(image, 0x200, 2) == [0x00, 0x02]


def test_a_phase_belongs_to_its_memory_zone(tmp_path):
    image = _image(tmp_path, (
        '#create_memzone OTHER 0x0300 0x03ff\n'
        '.org 0x0100\n'
        '.phase 0xfc00\n'
        '  nop\n'
        '.memzone OTHER\n'
        'Other: .2byte Other\n'
        '.memzone GLOBAL\n'
        'Back: .2byte Back\n'
    ))
    assert _bytes(image, 0x100, 3) == [NOP, 0x01, 0xfc]
    assert _bytes(image, 0x300, 2) == [0x00, 0x03]


def test_a_phase_address_outside_the_address_space_is_an_error(tmp_path):
    assert '.phase address 65536 (0x10000) is outside the address space' in _error(tmp_path, '.phase 0x10000\n')


def test_a_label_may_follow_a_phase_directive_as_it_may_follow_org(tmp_path):
    image = _image(tmp_path, '.org 0x0000\n.phase 0xfc00 start: jpa start\n.dephase back: .2byte back\n')
    assert _bytes(image, 0, 5) == [JPA, 0x00, 0xfc, 0x03, 0x00]


def test_phase_directives_are_checked_for_their_arguments(tmp_path):
    assert '.phase directive requires the address to assemble for' in _error(tmp_path, '.phase\n')
    assert '.dephase directive takes no arguments' in _error(tmp_path, '.dephase 5\n')


def test_bytes_past_the_end_of_the_address_space_are_an_error(tmp_path):
    message = _error(tmp_path, '.org 0xfffe\n.phase 0x0000\n  jpa 0\n')
    assert 'image position 0xfffe, past the end of the address space' in message


def test_the_listing_shows_the_phased_address(tmp_path):
    listing = _assemble(tmp_path, '.org 0x0010\n.phase 0xfc00\nApp: jpa App\n', fmt='listing')
    assert 'fc00 | 64 00 fc' in listing


# ---- .align ------------------------------------------------------------------------------------


def test_align_keeps_an_address_already_on_a_boundary(tmp_path):
    image = _image(tmp_path, '.org 0x0100\n.align\nA: .2byte A\n.align 16\nB: .2byte B\n')
    assert _bytes(image, 0x100, 2) == [0x00, 0x01]
    assert _bytes(image, 0x110, 2) == [0x10, 0x01]


def test_align_in_a_phase_aligns_the_address_and_moves_the_image_as_far(tmp_path):
    image = _image(tmp_path, '.org 0x0000\n.phase 0xfcfe\n  nop\n.align\nA: .2byte A\n')
    assert _bytes(image, 0x02, 2) == [0x00, 0xfd]


# ---- other changes -------------------------------------------------------------------------------


def test_muted_lines_do_not_overlap_emitted_bytes(tmp_path):
    image = _image(tmp_path, '.org 0x0080\n  jpa 0x1234\n#mute\n.org 0x0080\nvar: .2byte 0xffff\n#emit\n')
    assert _bytes(image, 0x80, 3) == [JPA, 0x34, 0x12]


def test_a_tab_may_separate_a_mnemonic_from_its_operands(tmp_path):
    image = _image(tmp_path, '.org 0x0000\n\tldi\t5\tjpa\t0x1234\n')
    assert _bytes(image, 0, 5) == [LDI, 5, JPA, 0x34, 0x12]


def test_a_low_byte_fast_jump_target_skips_the_page_check(tmp_path):
    image = _image(tmp_path, '.org 0x1200\nhere: fpa <0xcc\n  fpa here\n')
    assert _bytes(image, 0x1200, 4) == [FPA, 0xcc, FPA, 0x00]
    assert 'does not have the same MSBs' in _error(tmp_path, '.org 0x1200\n  fpa 0x34cc\n')
