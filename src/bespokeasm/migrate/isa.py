"""What migration rules need to know about an instruction set's instructions."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class InstructionShape:
    """What migration needs to know about an instruction."""
    operand_count: int
    # The instruction's own bytecode, or None when it isn't fixed.
    opcode: int | None = None


def instruction_shapes(config: dict) -> dict[str, InstructionShape]:
    """The shape of each instruction and macro, by lower-case mnemonic and alias. A mnemonic
    whose variants take different numbers of operands is left out."""
    shapes: dict[str, InstructionShape] = {}

    def shape(entry: dict) -> InstructionShape | None:
        count = (entry.get('operands') or {}).get('count', 0)
        if not isinstance(count, int):
            return None
        bytecode = entry.get('bytecode') or {}
        value = bytecode.get('value')
        return InstructionShape(count, value if isinstance(value, int) and 'suffix' not in bytecode else None)

    def add(names, entries) -> None:
        found = [s for s in (shape(entry) for entry in entries) if s is not None]
        if not found or len({s.operand_count for s in found}) != 1:
            return
        merged = found[0] if len(set(found)) == 1 else InstructionShape(found[0].operand_count)
        for name in names:
            shapes[str(name).lower()] = merged

    for mnemonic, entry in (config.get('instructions') or {}).items():
        entry = entry or {}
        add([mnemonic, *(entry.get('aliases') or [])], [entry, *(entry.get('variants') or [])])
    for mnemonic, entry in (config.get('macros') or {}).items():
        variants = entry if isinstance(entry, list) else (entry or {}).get('variants', [entry])
        add([mnemonic], [{'operands': v.get('operands')} for v in variants if isinstance(v, dict)])
    return shapes


def migration_context(model):
    """What migration rules need from an instruction set: its mnemonics, BespokeASM's directive
    names with the set's directive aliases, and each instruction's shape."""
    from bespokeasm.assembler.keywords import BYTECODE_DIRECTIVES_SET
    from bespokeasm.assembler.keywords import COMPILER_DIRECTIVES_SET
    from bespokeasm.assembler.keywords import PREPROCESSOR_DIRECTIVES_SET
    from bespokeasm.migrate.rules import MigrationContext
    return MigrationContext(
        mnemonics=frozenset(name.lower() for name in model.operation_mnemonics),
        directive_names=frozenset(
            COMPILER_DIRECTIVES_SET | BYTECODE_DIRECTIVES_SET | PREPROCESSOR_DIRECTIVES_SET | set(model.directive_aliases)
        ),
        shapes=instruction_shapes(model.config),
        string_terminator=model.cstr_terminator,
        embedded_strings=model.allow_embedded_strings,
    )
