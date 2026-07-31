# Flow Counters M4 Development Acceptance Harness

M4 adds manual control of scalar counters and permits multiple named counter
instances to overlap:

- `stack`, `outer`, and `inner` are tracked concurrently;
- each instruction updates every non-suspended instance from its own class's
  configured effect source;
- general `#assert` uses the same conditions and preprocessor values as `#if`,
  with an optional `#print`-style colored failure message;
- flow-aware `#assert` checks one instance without changing it;
- `#set` re-anchors only the named instance;
- `#suspend` pauses one instance while the others continue to advance;
- `#resume` restores the suspended instance to a programmer-supplied value;
- each `#endtrack` checks and closes its named instance independently.

The stack instance retains the practical caller-parameter use case: a
coordinate declared at `sp+3` is accessed as `sp+4` after a one-byte local
push, without changing its `LDS .candidate` source expression.

The harness compares the annotated program with a hand-stripped twin, checks
the emitted bytes (including a coordinate-derived stack position), and proves
that reading a suspended counter is rejected.

From the repository root:

```bash
source .venv/bin/activate
PYTHONPATH=src python dev/flow-counters-m4/verify_m4.py
```
