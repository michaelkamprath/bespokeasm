# Flow Counters M0 Development Acceptance Harness

This development harness exercises the M0 static-analysis substrate without using any
flow-counter source syntax (that syntax begins in M1).

It proves that a flow-enabled compile retains immutable records for:

- a selected instruction variant and alias,
- a symbolic branch-target expression,
- two instructions on one source line, and
- both constituents of an instruction macro.

It then repeats the compile with flow checks disabled and with all flow
metadata removed. The flow-capable compile retains records in both check modes
so emitted dependencies can be discovered after parsing; the non-flow ISA
retains none. All three emit the same bytes.

From the repository root, with the project virtual environment active:

```bash
PYTHONPATH=src python dev/flow-counters-m0/verify_m0.py
```

The command exits successfully after printing `M0 development acceptance: PASS`.
