# Flow Counters M2 Development Acceptance Harness

This harness demonstrates the original motivation for counter coordinates: naming
caller-owned parameters on the stack so their source expressions do not change
when a subroutine manipulates its local stack.

- `subroutine-parameters.asm` models the `is_prime32` entry contract from
  `examples/slu4-minimal-64x4/software/primes.min64x4`: the candidate starts at
  `sp+3` and the return-value placeholder at `sp+7`;
- `subroutine-parameters-with-local.asm` adds a 4-byte local push while leaving
  both parameter access expressions unchanged; their emitted offsets
  automatically become `sp+7` and `sp+11`;
- `subroutine-parameters-with-rts.asm` models a complete called routine:
  tracking begins at 0, local stack use balances back to 0, and the M2
  `#endtrack` performs the reconciliation immediately before `rts`;
- the accesses use Minimal 64x4-style `LDS <stack-position>` and
  `STS <stack-position>` instructions, so the tracked form replaces literals
  such as `lds 3` and `sts 7` directly;
- hand-resolved twins prove byte-for-byte equivalence;
- scoped `:= COORDINATE(counter, offset)` declarations express the stack
  position exactly as the programmer sees it (`sp+3`, `sp+7`) while remaining
  distinct from ordinary constants;
- the stack class uses `coordinate_offsets: positive` and
  `allow_zero_offset: false`, rejecting both `sp-N` and `sp+0`; other ISAs may
  select `negative` or `both` and may independently allow zero;
- bare coordinate references are exercised as the stack-position operands to `LDS` and `STS`;
- permanent invalidation after a slot is popped,
- scalar elapsed-cycle coordinates,
- disabled-check coordinate-reference resolution without verification output, and
- ISA-gated syntax and hover documentation for VS Code, Sublime Text, and Vim.

M2 analyzes straight-line instruction effects only. It demonstrates the
parameter-marker arithmetic used by `is_prime32`, but the actual routine's
branches, calls, and returns cannot be analyzed end-to-end until control-flow
analysis ships in a later milestone. M3 will give `rts` terminal semantics
whose exit reconciliation occurs before its physical -2 stack effect.

From the repository root:

```bash
source .venv/bin/activate
PYTHONPATH=src python dev/flow-counters-m2/verify_m2.py
```

The command proves byte identity against hand-stripped fixtures and prints
`M2 development acceptance: PASS`.
