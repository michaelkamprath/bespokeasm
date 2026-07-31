# Flow Counters M5 Development Acceptance Harness

M5 adds address-based control-flow analysis for scalar `require-equal`
counters:

- direct conditional and unconditional branches propagate independent states;
- equal states rejoin, while unequal states produce a join diagnostic;
- every return path is checked against its exit contract;
- net-zero loops converge without enumerating execution paths;
- `#entry` declares intentional alternate roots;
- conventional calls use configured caller-visible summaries;
- indirect transfers and physical fall-through into data or address gaps fail;
- coordinate validity is merged conservatively across paths;
- listing-format pretty print shows input-to-output transitions and resolved
  coordinate values, while leaving other unchanged rows blank.
- independent `stack` and `writes` classes can run concurrently over the same
  control-flow graph;
- a scalar `cycles` class verifies that both sides of a branch take the same
  number of configured clock cycles.
- an instruction may identify memory-write target operands; writing an
  address watched by a counter makes that counter indeterminate even through
  a macro expansion, until source explicitly re-anchors it with `#resume`.

The primary sample retains the practical stack-parameter use case. It declares
a caller-owned parameter at `sp+3`, pushes a common local value before
branching, and gives each arm its own return. One arm pushes an additional
path-local value. The unchanged `.candidate` reference consequently
emits `sp+5` on that arm and `sp+4` on the other; both exits independently
restore the routine-owned stack depth. The harness compares its bytes with a
hand-resolved twin and prints its annotated listing.

Additional fixtures demonstrate a leaked push on only one return path, an
explicit unreachable entry, a suspended runtime-length loop, an indirect
transfer error, fall-through into emitted data, a balanced tail call, and the
warning produced by an externally visible label after all known paths return.

`watched-address-reset.asm` invokes the `reset_stack` macro, which expands to
`write_addr 255`. The `stack` class declares address 255 in
`invalidate_on_write`, while `write_addr` declares operand zero in
`flow_write_operands`; analysis therefore sees the expanded real instruction,
changes `stack` to indeterminate, invalidates its old coordinates, and requires
the explicit `#resume stack = 0` before precise tracking continues.

`direct-reset.asm` demonstrates the complementary `flow_invalidates`
instruction contract for an anchor replacement that is not a memory write.
The fixture reaches that instruction through a macro expansion and explicitly
re-anchors the new stack with `#resume`, just like the watched-write case.

`concurrent-counters.asm` tracks routine-owned stack depth and completed memory
writes at the same time. Because a stack push also writes memory, its listing
row renders `stack=0 → 1`, followed by `writes=0 → 1` on a continuation row
whose other columns are blank. A `store` changes only `writes`, while `pop`
changes only `stack`; the two return paths finish with write counts of three
and two. Both values are emitted through `COUNTER(writes)` and checked against
a hand-resolved twin.

`macro-stack.asm` invokes `push_three`, a single source-level instruction macro
that expands to three stack-changing `push` instructions. The listing renders
their aggregate effect on that row as `stack=0 → 3`, and the harness compares
the emitted bytes with a hand-expanded twin.

`macro-shared-continuation.asm` invokes `push_seven` while tracking both
`stack` and `writes`. Six emitted push opcodes and the aggregate stack
transition appear on the source row. The seventh opcode and aggregate writes
transition share the next continuation row, demonstrating that the bytes and
flow columns do not create redundant overflow rows.

`cycle-counting.asm` assigns realistic, unequal costs to its branch, no-op,
jump, and return instructions. Its two branch arms each reach `.done` at
exactly five cycles, where `#assert cycles == 5` and `#endtrack ... exit=5`
verify the result.

From the repository root:

```bash
source .venv/bin/activate
PYTHONPATH=src python dev/flow-counters-m5/verify_m5.py
```

To inspect only the annotated primary listing:

```bash
PYTHONPATH=src python src/bespokeasm/__main__.py compile \
  -c dev/flow-counters-m5/flow-counters-m5.yaml \
  -n -p dev/flow-counters-m5/branching-stack.asm
```

Inspect the concurrent counters:

```bash
PYTHONPATH=src python src/bespokeasm/__main__.py compile \
  -c dev/flow-counters-m5/flow-counters-m5.yaml \
  -n -p dev/flow-counters-m5/concurrent-counters.asm
```

Inspect the aggregate effect of a multi-instruction macro:

```bash
PYTHONPATH=src python src/bespokeasm/__main__.py compile \
  -c dev/flow-counters-m5/flow-counters-m5.yaml \
  -n -p dev/flow-counters-m5/macro-stack.asm
```

Inspect a macro whose bytes and flow annotations share a continuation row:

```bash
PYTHONPATH=src python src/bespokeasm/__main__.py compile \
  -c dev/flow-counters-m5/flow-counters-m5.yaml \
  -n -p dev/flow-counters-m5/macro-shared-continuation.asm
```

Inspect clock-cycle propagation across the balanced branch:

```bash
PYTHONPATH=src python src/bespokeasm/__main__.py compile \
  -c dev/flow-counters-m5/flow-counters-m5.yaml \
  -n -p dev/flow-counters-m5/cycle-counting.asm
```
