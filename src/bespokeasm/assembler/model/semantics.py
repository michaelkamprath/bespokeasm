"""Shared merge of instruction-level semantics with a variant's overrides.

Both the analysis-record retention path (``InstructionVariant``) and the
config-load validation path (``AssemblerModel._effective_instruction_configs``)
must see the same merged semantics, so the merge lives here and both import it.
"""
# ``bytecode`` and ``operands`` are read wholesale from the selected variant's
# own config by the emission machinery, so the semantic view must replace them
# wholesale as well — a deep merge would claim root bytecode/operand details
# (e.g. a suffix) that the variant does not actually assemble with.
_WHOLESALE_KEYS = frozenset({'bytecode', 'operands'})


def merge_instruction_semantics(
    instruction_config: dict,
    variant_config: dict,
) -> dict:
    """Merge root instruction semantics with one variant's overrides.

    Nested metadata dictionaries (``documentation``, ``flow_effects``, and any
    custom fields) merge recursively key-by-key with the variant winning per
    key; scalars, lists, and the wholesale keys replace entirely. A ``None``
    override is ignored — a variant cannot remove a root key. The structural
    ``variants`` list is excluded from both sides.
    """
    merged = {
        key: value
        for key, value in instruction_config.items()
        if key != 'variants'
    }
    for key, value in variant_config.items():
        if key == 'variants' or value is None:
            continue
        base = merged.get(key)
        if (
            key not in _WHOLESALE_KEYS
            and isinstance(base, dict)
            and isinstance(value, dict)
        ):
            merged[key] = _merge_nested(base, value)
        else:
            merged[key] = value
    return merged


def _merge_nested(base: dict, override: dict) -> dict:
    merged = dict(base)
    for key, value in override.items():
        if value is None:
            continue
        nested = merged.get(key)
        if isinstance(nested, dict) and isinstance(value, dict):
            merged[key] = _merge_nested(nested, value)
        else:
            merged[key] = value
    return merged
