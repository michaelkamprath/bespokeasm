# Flow Counters M3 Development Acceptance Harness

M3 moves the RTS-style return instruction inside a straight-line tracking
region. The region tracks only stack movement owned by the routine:

- `#track stack mode=called` selects the ISA's `0 -> 0` entry contract;
- `.candidate := COORDINATE(stack, 3)` directly means the caller's value is at
  `sp+3`; the mode's initial value is not added to that physical coordinate;
- a four-byte local push changes `OFFSET(.candidate)` from 3 to 7 and the
  return-value slot from 7 to 11;
- `addsp 4` uses the configured `-ARG(0)` effect to restore the routine-owned
  counter to zero;
- `rts` uses `flow_terminal.stack: before_effect`, so it verifies zero before
  its physical `-2` return-address pull and then closes the execution path;
- the following unreachable `#endtrack stack` ends lexical extent without a
  second exit check.

`subroutine-parameters-stripped.asm` contains the same program with hand-written
offsets and no analysis annotations. The harness proves both versions emit
identical bytes. It also proves that a wrong frame adjustment fails at `rts`,
that runtime register operands are never mistaken for compile-time `ARG()`
values, and that `after_effect` terminal reconciliation remains available for
ISAs whose terminal effect belongs inside the region.

From the repository root:

```bash
source .venv/bin/activate
PYTHONPATH=src python dev/flow-counters-m3/verify_m3.py
```
