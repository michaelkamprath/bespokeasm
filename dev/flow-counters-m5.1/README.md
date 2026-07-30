# Flow Counters M5.1 Development Harness

This harness demonstrates generated ISA documentation for flow counters. Its
configuration is a documentation-enabled copy of the M5 harness ISA with an
operand-dependent `adjust` instruction added for the `-ARG(0)` documentation
case.

From the repository root, run:

```sh
PYTHONPATH=src python dev/flow-counters-m5.1/verify_m5_1.py
```

The verifier generates Markdown through the same `DocumentationGenerator` API
used by `bespokeasm docs`. It checks the top-level Flow Counters section,
constant and operand-dependent counter effects, terminal reconciliation, a
call summary, memory-write invalidation of a watched counter anchor, and
unconditional invalidation by an instruction that directly replaces an
anchor. It also generates documentation for a non-flow ISA and confirms that
no flow-counter content appears.
