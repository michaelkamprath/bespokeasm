# Flow Counters M1 Development Acceptance Harness

This harness exercises the first user-visible flow-counter milestone:

- `#track` and `#endtrack`,
- scalar `COUNTER()` in an instruction operand and fixed-size data value,
- constant instruction deltas,
- balanced exits and configured bounds,
- byte identity with a hand-stripped source, and
- disabled-check value resolution without verification output, and
- ISA-gated generated editor syntax and hover documentation.

From the repository root:

```bash
source .venv/bin/activate
PYTHONPATH=src python dev/flow-counters-m1/verify_m1.py
```

The command exits successfully after proving the assembly and diagnostic cases,
generating a VS Code extension from the flow-enabled fixture, and printing
`M1 development acceptance: PASS`.
