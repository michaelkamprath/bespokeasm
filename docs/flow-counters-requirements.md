# Flow Counters (Assembly-Time Tracked Counters)

Status: **DRAFT — feature specification in progress**

Addresses GitHub issue [#18 — Stack Position Labels](https://github.com/michaelkamprath/bespokeasm/issues/18).

## Overview
The original request in issue #18 is for symbolic stack-slot labels: give a value pushed onto the stack a name, and let the assembler compute its current stack-pointer-relative offset at any later point in the code. That only works if the assembler tracks how each instruction moves the stack pointer.

The generalized mechanism is the **flow counter**: a named integer value that the assembler advances line-by-line through the source code according to per-instruction effects declared in the ISA configuration. Flow counters:

* exist only at assembly time and emit no bytecode — the feature is static analysis only, and assembled output is identical with or without it (see *Guiding Requirement* below),
* are usable in operand expressions (current value and snapshots),
* are checked for consistency, with ambiguous or out-of-bounds usage reported as errors,
* are instances of **counter classes** declared in the ISA configuration — instructions declare effects against classes, source code instantiates counters, and any number of counters may be active simultaneously, each tracked independently.

Stack depth is the flagship use case, but the mechanism is deliberately general. Because BespokeASM ISAs are user-defined, what a counter *means* is entirely the configuration author's choice — the assembler only does bookkeeping and consistency checking.

## Motivating Use Cases
1. **Stack slot labels** (issue #18): name pushed values; compute `sp`-relative offsets automatically so inserting a new `push` does not require manually updating every offset below it.
2. **Hardware call-stack depth limits**: many small CPUs have tiny fixed call stacks (e.g., PIC's 8-level hardware stack). A counter where `call` is +1 and `ret` is −1 with a configured maximum turns a silent runtime crash into an assembly error.
3. **Two-stack machines**: Forth-style CPUs track the data stack and return stack independently — two simultaneous counters.
4. **Cycle counting**: each instruction declares its cycle cost as a delta; the difference between two snapshots gives cycle-exact timing for delay loops, bit-banged protocols, or video signal generation. With `join: interval` (below), the same machinery yields **worst-case execution timing** across branches — assert that any path through a region fits a cycle budget. Cycle counting stresses two design features not needed by stack-style counters: per-class **join semantics** and **edge-dependent deltas** (see those sections).
5. **Constant-time verification**: a cycle counter with `join: require-equal` errors precisely when two control-flow paths through a routine differ in cycle count — exactly the check needed for timing-attack-resistant crypto (e.g., MAC comparison). Same mechanism as stack-depth join checking, opposite intent: here, path divergence *is* the bug being hunted.
6. **Paired-operation balance**: `di`/`ei` interrupt nesting, Z80 `exx` shadow-register parity, bank-switch nesting — assert the counter is balanced at region end.
7. **Register save/restore symmetry**: verify a subroutine epilogue pops exactly what the prologue pushed.

## Conceptual Model: A Generalization of the Address Counter
Flow counters are best understood as a generalization of machinery the assembler already has. The assembler maintains one counter today — the **address counter** (`current_address` in the `MemoryZoneManager`) — and a flow counter behaves like it in nearly every respect:

| Address counter (existing) | Flow counter (this feature) |
|:--|:--|
| single, implicit, always active | many, explicit, opened by `#track` |
| starts at `origin`; `.org` re-anchors it | starts at `init`; `#set` / `#resume` re-anchor it |
| advances by each line's `word_count` | advances by each instruction's declared `flow_effects` delta |
| an address label (`foo:`) snapshots its current value | a slot constant (`.var = COUNTER(stack)`) snapshots its current value |
| the snapshot feeds address operand values | the snapshot feeds `OFFSET()` operand values |
| bounded by memory zone start/end | bounded by `min_value` / `max_value` |
| resolved in the first pass, in source order | resolved in the first pass, in source order |

In other words, the address counter is essentially one hardwired flow counter: a single always-on instance whose per-line delta happens to be forced by emission rather than declared in configuration, re-anchored by `.org`, and snapshotted by labels. **The implementation should reuse the existing first-pass walk and the label-scope snapshot machinery rather than build a parallel system** — a slot constant is, mechanically, an address label whose value comes from a counter instead of the address counter.

The generalization is not total, and the one axis where it breaks is the most important design fact about the feature:

* **The address counter lives in the *layout* dimension; flow counters live in the *execution* dimension.** The address counter tracks where bytes land in memory, and physical layout is linear and monotonic — a given source position has exactly one address by construction, so the address counter never branches and never has to ask whether its value is consistent. Flow counters track quantities as the CPU *executes*, where the same instruction may be reached by multiple control-flow paths. That is the entire reason the join-consistency and push-leak analysis (milestone M5) exists; the address counter has no analogue because addresses have no "paths."
* **Direction:** the address counter is monotonic (only `.org` moves it backward, and that is a re-anchor, not a delta); flow counters are bidirectional by nature.
* **Emission vs. execution order:** the address counter advances in emission order; a flow counter advances in execution order. Normally the same source walk, but `#mute` and conditional assembly are exactly where the two diverge — which is why tracking follows compiled code, not emitted bytes.

So flow counters generalize the *counter-with-snapshots mechanism* the assembler already uses for addresses, and add one dimension — control flow — that the address counter never had to model. The address counter is the degenerate case: single instance, monotonic, layout-space, no branches.

### How Much Should They Share?
The parallel above is a guide to *reuse*, not a mandate to *unify*. The intended relationship:

* **Share the paradigm.** The two should feel like the same idea: a counter advanced during the first pass, re-anchored by a directive, snapshotted into a named compile-time value. Directive and expression design should deliberately echo the address-counter vocabulary (`#track`/`init=` mirroring `.org`/`origin`; slot constants mirroring address labels) so the feature reads as an extension of what users already know.
* **Share one primitive: the label-scope value sink.** The deepest commonality is not "two counters" but that both produce *named values captured at a source position during the first pass* into the label-scope system. The address counter already does this (an address label is a snapshot of `current_address`). Flow counters should join as a **second producer** into that same machinery — a slot constant is an address-label-like value whose source is a counter instead of the address counter (see Open Question 2 on tagged-origin constants). Reuse flows in one direction: flow counters borrow the existing label/first-pass primitives; the address counter is **not** re-expressed on top of a flow-counter engine.
* **Do not unify them under a common Counter base.** A shared base class would be lopsided — the address counter carries memory zones, overlap detection, `.fill`/`.align`, and monotonicity that no flow counter uses, while flow counters carry signed deltas, bounds, suspend/resume, and control-flow analysis that the address counter never uses. The shared bookkeeping is a small fraction of either; a common base would mostly be two disjoint sets of special cases.
* **Isolation is a hard constraint, not a preference.** The *Static Analysis Only* guarantee forbids flow-counter logic from perturbing address assignment or byte code. Sharing mutable state or a common advance path between the two would create exactly the channel through which an analysis bug could shift an address. Keeping the implementations separate — touching only the immutable label-scope primitive — is what makes the byte-identical guarantee structurally enforceable rather than merely intended. The address counter is also load-bearing and predates this feature; there is no functional upside to refactoring it.

### The Symmetric Case: Layout Counters (out of scope, noted for coherence)
The layout/execution duality is symmetric, and recognizing this keeps the feature boundary sharp. The address counter is the first member of a **layout-counter family** (monotonic, single-valued per position, snapshot = physical location, *produces real addresses that byte code depends on*); flow counters are the **execution-counter family** (bidirectional, multi-path, snapshot = a convenience value, *never owns byte code*). They share the paradigm — counter, re-anchor, snapshot-into-a-label — but sit in different dimensions and obey opposite rules about byte code.

The motivating example is a **microcode compiler**, where an instruction's control-store entry begins at a base sub-address and each microstep occupies the next word:

* **Labeling microcode steps relative to the instruction start is a *layout* concern, not a flow counter.** A step label is the target of a microcode branch, so it must equal the physical control-store sub-address where the step is stored — single-valued, fixed by layout, and required to be a real address other byte code depends on. Modeling it with a flow counter would be the wrong dimension: a flow-counter snapshot only equals the sub-address if it advances in lockstep with the address counter, at which point it is merely `current_address − instruction_base` (a derived view of the address counter), and it would forfeit the layout guarantees (overlap detection, bounds) that make branch targets correct by construction. This belongs to a *sibling* generalization — a sub-address counter that resets per instruction and is bounded by the step-field width — which would live on the addressing side, **not** in this feature. (It can be approximated today with `.org (opcode << step_bits)` per instruction plus ordinary address labels and subtraction, with `word_size` set to the microcode word width.)
* **Flow counters fit microcode only for *execution* consistency across microcode branches:** verifying a T-state / microstep budget is met on every path through an instruction's microcode, or that a control signal asserted on one microcode path is deasserted before the instruction ends. These are bidirectional, multi-path, byte-code-neutral checks — squarely the flow-counter family.

The lesson for scope: when a counter's snapshot must *be* an address that byte code depends on, it is layout-family and does not belong here; when the snapshot is a convenience value and the interesting question is consistency across execution paths, it is a flow counter.

## Requirements

### Guiding Requirement: Static Analysis Only
Flow counters are purely a static-analysis feature. **The assembled byte code must be identical whether or not the feature is used** — its only observable effects are diagnostics (and assembly failure when those diagnostics are errors). Specifically:

* Flow counter directives (`#track`, `#endtrack`, `#assert`, `#set`, `#entry`, `#suspend`, `#resume`, `#loop`) emit no byte code and occupy no address space, like all other preprocessor directives.
* The analysis never alters code generation: no instruction insertion, removal, reordering, padding, or operand rewriting based on analysis results. Tracking state has no influence on instruction encoding, address assignment, or memory zone behavior.
* `COUNTER()` and `OFFSET()` resolve to compile-time constants determined solely by the declared instruction effects and the source's structure — the emitted byte code is bit-identical to what hand-writing the resolved numeric values would produce. They are conveniences for computing values the programmer would otherwise compute (and today does compute) by hand.
* Equivalence invariant, suitable for a conformance test: take any program that assembles cleanly with flow counters in use; strip every flow counter directive and replace every `COUNTER()`/`OFFSET()` expression with its resolved numeric value; the assembled output must be byte-identical.
* Adding `flow_counters` and per-instruction effect metadata to an ISA configuration must not change the assembly of any existing source file that does not use the feature.

### Feature Enablement (ISA Configuration)
Flow counters are **off unless the instruction set explicitly enables them**, and any failure is **gated on actual use**:

* The presence of a `flow_counters` section in the ISA configuration *is* the explicit enablement, and the counter classes it declares *are* the enabled types — an ISA enables exactly the counter types it lists, nothing more. There is no implicit or global "all counters" set to enable, because counter classes are author-defined; the section is the enumeration.
* An ISA with **no `flow_counters` section** has the feature disabled entirely. It assembles exactly as today, and none of the metadata-completeness or soundness checks ever run.
* Using any flow-counter construct (`#track` and the other directives, or `COUNTER()`/`OFFSET()`) in source compiled against an ISA that does not enable the feature is an **error** — "this instruction set does not enable flow counters" — and that error fires **only because the construct was used**. Source that uses no flow-counter construct never errors, regardless of configuration.
* Likewise, every requirement in *Required Metadata: Fail Loud, Never Silently Inert* is usage-gated: a metadata gap for counter class `X` is an error only when source actually tracks or references `X`. An enabled-but-unused class imposes no obligations and raises no diagnostics.

This keeps the *Static Analysis Only* guarantee intact from both directions: enabling the feature on an ISA changes nothing for source that does not use it, and source cannot accidentally invoke it against an ISA that did not opt in.

### Counter Classes (ISA Configuration)
The configuration declares counter **classes**; source code creates counter **instances** of those classes with `#track`. This split separates two concerns: the ISA author knows what instructions *do* (a `push` deepens any stack-depth tracker by 1), while only the programmer knows how many trackers they want running and over what code (one stack tracker; or two overlapping cycle-measurement windows). An instruction's declared effect applies to **every active instance** of the affected class.

In the common case the distinction is invisible: `#track stack` creates an instance whose name defaults to its class name, and everything reads as if "stack" were simply a counter.

#### There Is No Fixed Taxonomy of Counter "Types"
A counter has no built-in kind. Its behavior is **emergent from the combination of two things**: the class-declaration knobs (`join`, `min_value`/`max_value`, `entry_modes`, `unknown_instructions`) and how each instruction declares it interacts with the class (`flow_effects`, `flow_terminal`, `flow_transfer`). "Stack depth," "cycle counter," "constant-time counter," and "hardware-call-stack limit" are *recognizable configurations* of those knobs, not enumerated types the assembler knows about. The use cases listed earlier are therefore presets/patterns, not a closed set — an ISA author can compose new ones (e.g., a bank-nesting balance counter) purely by choosing knobs and per-instruction effects, with no assembler change. Wherever this document says "a cycle counter" or "a stack counter," read it as shorthand for "a counter configured this way," not a distinct mechanism.

A new optional top-level configuration section, `flow_counters`, declares the classes available to source code:

```yaml
flow_counters:
  stack:
    documentation:
      title: Data Stack Depth
      description: data stack depth in bytes
    source: stack_effect      # read each instruction's delta from its `stack_effect` field
    operation: add            # accumulate by signed addition (the default)
    join: require-equal       # paths must agree at a join (default); else join-mismatch error
    min_value: 0              # optional; error if tracking goes below
    max_value: 64             # optional; error if exceeded
    unknown_instructions: error   # ignore | warn | error (default: warn)
    default_init: 0           # init value when #track gives neither init= nor mode=
    entry_modes:              # named entry conventions, usable as #track mode=<name>
      called:                 # entered via `call`: 16-bit return address on the stack
        init: 2
        exit: 0               # `ret` (-2) consumes the return address
      jumped:                 # entered via `jmp` or fall-through: nothing extra
        init: 0
      interrupt:              # ISR entry: return address plus pushed status byte
        init: 3
        exit: 0
  cycles:                     # a worst-case-timing counter: paths may differ, track the hull
    source: documentation.cycles  # reuse the per-instruction timing already in documentation
    operation: add
    join: interval
    unknown_instructions: error
  ct_cycles:                  # a constant-time counter: paths MUST agree
    source: documentation.cycles  # same source field, different join policy
    join: require-equal
    unknown_instructions: error
```

The section is a dictionary keyed by class name, matching the `operand_sets`/`instructions` convention. The `stack` class above reads each instruction's delta from a purpose-defined `stack_effect` field; the `cycles` class reads the per-instruction timing straight out of `documentation.cycles`, so the cycle count is authored once and serves both documentation and the counter.

| Option Key | Value Type | Description |
|:-:|:-:|:--|
| `documentation` | dictionary | _(Optional)_ `title` and `description`, per the documentation convention used by other config entities (and available to editor hover tooling the same way). |
| `source` | string | _(Optional)_ Dotted path into each instruction's configuration giving this counter's per-instruction delta — e.g., `documentation.cycles`, or a top-level instruction key like `stack_effect`. Lets a counter **reuse an existing integer field** (single source of truth) or bind to a field defined just for it. Defaults to `flow_effects.<class-name>` (the conventional per-instruction map) when omitted. Multiple classes may read the same field. |
| `operation` | string | _(Optional)_ How each instruction's source value combines into the counter. `add` — signed accumulation — is the default and the primary operation; the field is reserved for future combinators. |
| `join` | string | _(Optional)_ How values from multiple control-flow paths are reconciled at a join (path analysis, M5/M6). `require-equal` (default): paths must carry the same value or a join-mismatch error is raised — correct for stack depth, hardware-stack limits, and constant-time checks. `interval`: the value becomes a `[min,max]` hull unioned across paths, never an error at the join — correct for worst-case timing and other budgets where paths legitimately differ. An `interval`-class counter has no single scalar value, so bare `COUNTER(cycles)` and `OFFSET()` are invalid as operand values; its bounds are read only through `COUNTER(cycles).min` / `.max` in a flow assertion. |
| `min_value` | integer | Optional lower bound. Tracking below this value is an error. |
| `max_value` | integer | Optional upper bound. Tracking above this value is an error. |
| `unknown_instructions` | string | Behavior when an instruction with no declared effect for this class appears inside an active tracking region: `ignore`, `warn`, or `error`. Default `warn`. |
| `default_init` | integer | _(Optional)_ Initial value used when `#track` provides neither `init=` nor `mode=`. Defaults to 0. |
| `entry_modes` | dictionary | _(Optional)_ Named entry conventions. Each key is an author-defined mode name usable in source as `#track ... mode=<name>`; each value is a dictionary with `init` (required) and `exit` (optional, defaults to `init`). This keeps ISA knowledge — the return-address size, what an interrupt entry pushes — declared once in the configuration, while source code only names *how* a routine is entered. |

These are class-level properties, inherited by every instance.

The whole feature is opt-in by the presence of this section (see *Feature Enablement* above): configurations without a `flow_counters` section have it disabled and behave exactly as today.

### Instruction Effects (ISA Configuration)
An instruction's effect on a counter is its **delta value, read from the field the counter class names in `source`** (defaulting to `flow_effects.<class>`), combined per the class's `operation`. Separately, two classification keys — `flow_terminal` and `flow_transfer` — describe region-ending and control flow; these are not deltas and are always their own keys.

```yaml
instructions:
  push:
    stack_effect: 1           # read by the `stack` class (source: stack_effect)
    documentation:
      cycles: 11              # read by the `cycles`/`ct_cycles` classes (source: documentation.cycles)
  pop:
    stack_effect: -1
    documentation:
      cycles: 10
  ret:
    stack_effect: -2          # see modeling note
    documentation:
      cycles: 10
    flow_terminal: [stack]    # ends a tracking region for these counters
  jmp:
    documentation: { cycles: 8 }
    flow_transfer: unconditional
  jz:
    flow_transfer: conditional
  call:
    flow_transfer: call
  jmp_hl:                     # computed/indirect jump
    flow_transfer: indirect
  mov_reg:
    flow_effects: { scratch: 1 }   # default source field, for a class that omits `source`
```

The delta read from `source` is an integer in the common case, but may also be an operand expression or an edge-map (see *Operand-Dependent Effects* and *Edge-Dependent Deltas*); `operation` governs how it accumulates regardless of form. A counter reading `documentation.cycles` simply finds an integer there. `flow_terminal`/`flow_transfer` are independent of `source` and apply to whichever classes they name (terminal) or to the CFG (transfer).

> **Modeling note:** whether `call`/`ret` carry a `stack` delta (a value in the `stack` class's
> source field) is the configuration author's choice of what the counter *means*. A counter measuring only the
> subroutine's own frame depth gives them no effect; a counter measuring true stack depth
> gives them +2/−2 (for a 16-bit return address). The depth-accurate style is preferred
> when subroutines need to address caller-pushed values (arguments) through the stack
> pointer, because the `call` effect encodes the return-address size sitting between the
> callee's frame and the caller's slots — see *Subroutine Arguments and the Return Address*.

1. **Delta** — each counter class reads its per-instruction delta from the field named by its `source` (default `flow_effects.<class>`), applied to *every active instance* of that class when the instruction is encountered. `flow_effects` is thus the *default* source field — a map of class → delta — but a class may instead point `source` at any integer field (e.g., `documentation.cycles`) to reuse existing data. A delta may be a constant integer or, optionally, an operand expression or edge-map (see *Operand-Dependent Effects* and *Edge-Dependent Deltas*).
2. **`flow_terminal`** — list of counter classes for which this mnemonic terminates tracking regions (typically `ret`, `reti`, `rts`). It terminates *every active instance* of the listed classes, each checked against its own exit value. This is how "end of subroutine" is expressed without the assembler having to infer subroutine structure.
3. **`flow_transfer`** — classifies control-transfer instructions so the control-flow consistency analysis (see below) knows where execution can flow:
   * `conditional` — execution may continue at the branch target *or* fall through.
   * `unconditional` — execution continues only at the branch target; the following line is not a fall-through successor.
   * `call` — execution transfers away and returns to the following line. The counter value at the fall-through line is computed by the call-composition rule (see *Path Analysis*), which accounts for both the call's own push and the callee's terminal pop.
   * `indirect` — a computed or register-indirect jump whose target is unknowable at assembly time. Inside an active region this is an error for any tracked counter (unless the counter is suspended), because the analysis cannot follow it.

   This classification — plus the branch target, which the assembler already knows from the operand — is *all* the instruction-behavior knowledge the path analysis requires. The analyzer does not need to understand what instructions do, only where control can go and what each one's declared counter deltas are.

Referencing an undeclared counter class in any of these keys is a configuration error (validated in `AssemblerModel._validate_config()`).

Placement follows existing instruction-config structure: the keys may be declared at the instruction level and overridden per `variants` entry (which is how a `ret 2` callee-pops variant declares a different `stack` delta than plain `ret`). Instruction `aliases` share the root mnemonic's configuration, so effects apply to aliases automatically. Configurations using these keys must declare a `min_version` of at least the release introducing them.

Note the precedent of the existing `documentation.modifies` metadata, where instructions already declare which registers/flags/memory they touch — but only for documentation output. `flow_effects` is the machine-checked analogue for counter state; documentation generation could eventually surface declared flow effects alongside `modifies`.

#### Operand-Dependent Effects
An instruction's effect on a counter may depend on its operand(s), not just its mnemonic. The canonical case is stack-frame adjustment — `add sp, N` / `sub sp, N` moves the stack pointer by an operand-supplied amount — which is a *core* stack-tracking idiom on many ISAs, not an exotic case. The delta value in a counter's `source` field may therefore be an expression referencing the matched operands' resolved argument values (notation strawman, reusing the macro-token vocabulary already in the config language; shown here in the `stack` class's `stack_effect` source field):

```yaml
  add_sp:                       # `add sp, N`
    stack_effect: -ARG(0)       # delta is minus the first operand's argument value
  pushm:                        # push a register set, e.g. `pushm {r0-r3}`
    stack_effect: COUNT(0)      # delta is the count of registers in operand 0
```

Determinism is the governing rule, and it follows directly from the *Static Analysis Only* guarantee:

* If the operand resolves to a **compile-time constant** (`add sp, 4`, or `add sp, FRAME_SIZE` where `FRAME_SIZE` is a constant), the delta is fully determined and tracking proceeds normally. This is the common stack-frame case and is needed for basic stack tracking — so operand-dependent *constant* deltas are scheduled early (M3, with the subroutine-frame work), not deferred to M7.
* If the operand resolves to a **runtime value** the assembler cannot know (`add sp, a` where `a` is a register, or a value computed at runtime), the delta is unknowable; the counter enters the indeterminate state exactly as a runtime-variable push loop does (handled per `#suspend`, or an error if used while not suspended). The analysis never guesses.
* Structural operand quantities (register-set cardinality, page-cross penalties, repeat counts) are the richer cases and remain **M7**.

Operand-dependent deltas depend on the line retaining its resolved operand argument values (architecture change A), which the assembler currently discards.

#### Macros Influence Counters Only in Aggregate
A macro carries **no independent flow metadata** — `flow_effects`, `flow_terminal`, and `flow_transfer` are not accepted on a macro definition (declaring them is a configuration error). A macro's entire influence on every counter is **the aggregate of the effects of the instructions it expands to**, computed by the analysis seeing through to the expansion (each constituent instruction contributes its own effect, including operand-dependent ones evaluated against the macro's actual arguments). This is definitional, so a macro's counter effect can never drift from what it actually assembles — there is no place to declare an effect that disagrees with the expansion. Consequently a macro may also contain a `flow_terminal` instruction (ending a region) or a control transfer; these participate exactly as if written inline. Macro expansion already produces the constituent instructions (`CompositeAssembledInstruction`), so the aggregate falls out of walking the expansion rather than requiring separately-declared macro effects.

#### Required Metadata: Fail Loud, Never Silently Inert
A flow counter is only as trustworthy as the configuration behind it. The feature **must error when the ISA configuration lacks the metadata a requested capability depends on**, rather than silently tracking nothing or analyzing unsoundly. A counter that quietly stays at its initial value because no instruction declares an effect on it would give false confidence — "the stack is balanced" about an analysis that never ran — which is worse than not offering the feature. The required-metadata checks, by capability:

* **Tracking a class at all.** `#track X` requires class `X` to be declared in `flow_counters` (else error) **and** at least one instruction in the ISA to populate `X`'s `source` field (or a `flow_terminal` listing `X`). A *declared-but-inert* class — tracked in source yet whose `source` field is set on no instruction — is an error: the configuration cannot actually track it. (A per-counter override exists for the rare counter intended to move only via `#set`, but inert is an error by default.) Validation also checks that `source` is a well-formed config path and that the values found there are deltas (integer or a supported delta expression), not arbitrary data — a `source` pointing at a non-numeric field is a configuration error.
* **Entry modes.** `#track X mode=M` requires class `X` to declare `entry_modes.M` (else error).
* **Path analysis (M5).** If a tracked region contains a control-transfer instruction that declares no `flow_transfer`, the CFG cannot be built soundly for that region → error naming the unclassified instruction ("`jz` transfers control inside a region tracking `X` but declares no `flow_transfer`"). The analyzer must never silently treat a branch as a straight-line instruction.
* **Terminal-based ending.** A region that relies on a `flow_terminal` instruction to close (no explicit `#endtrack`) requires the ISA to declare `flow_terminal[X]` on at least one instruction; absent that, the region can only be closed explicitly, and reaching its end otherwise is the existing no-clear-end-point error — but the diagnostic should name the missing-terminal cause when the ISA declares no terminal for `X` at all.
* **Interval timing (M6).** Using `join: interval` across conditional branches that declare only scalar cycle deltas is permitted (scalar = same cost on both edges) and is not an error, only less precise.

Two error timings: **config-load checks** run in `AssemblerModel._validate_config()` independent of any source (internal consistency — an undeclared class named in `flow_effects` or `flow_terminal`, malformed `entry_modes`, divergent `flow_terminal` effects for one class); **usage-time checks** run when a counter is instantiated or used, because what counts as "sufficient metadata" depends on the capability the source actually invokes (inert-class, `flow_transfer` coverage, mode availability). Both report in the `flow` diagnostic category.

#### Edge-Dependent Deltas (configuring a branch with two-or-more relevant values)
A scalar delta assumes the effect is the same however control proceeds. That holds for stack operations but breaks for **conditional-branch cycle costs**: real CPUs charge different cycles for a branch taken vs. not taken (6502: 2 not-taken / 3 taken / 4 taken-across-page; Z80 conditional `RET`: 5 vs 11; `JR cc`: 7 vs 12). The cost belongs to the *edge*, not the instruction.

So the value found in a counter's `source` field may be an **edge-keyed map** instead of a scalar, for instructions classified `flow_transfer: conditional` (two edges: `taken`, `fall_through`) or `call`:

```yaml
  jr_cc:                          # `cycles` class has source: documentation.cycles
    flow_transfer: conditional
    documentation:
      cycles: { taken: 12, fall_through: 7 }   # edge-keyed; documentable as "12/7"
    stack_effect: 0               # scalar: a branch cannot change stack depth by outcome
```

This is how "two or more relevant integer values" on one branch are configured, and it composes along two independent axes:

* **Across edges** — the source value is a map keyed by edge; the analysis applies `taken` on the branch-target edge and `fall_through` on the fall-through edge. A scalar is shorthand for "same on every out-edge" (the only sensible form for `stack`, whose depth cannot depend on branch outcome).
* **Across counters** — each counter reads its *own* source field independently, so one branch can carry an edge-map for `cycles` and a scalar (or nothing) for `stack` at the same time. The full effect of a branch is the cross-product {tracked counters} × {out-edges}, each cell declared independently.
* **Multi-way branches** (a jump table / dispatch with a declared target set — otherwise `indirect`): N out-edges. A scalar applies to all N (the usual case — a table dispatch costs the same regardless of which entry is taken); per-edge maps for >2 edges are permitted but rarely needed.

Edge-keyed cycle costs are an M6 feature (meaningless without the edge-aware CFG of M5) and the natural companion to `join: interval`: together they give correct worst-case timing across asymmetric branches. Page-crossing and operand-count-dependent costs (6502 indexed `+1 if page crossed`, Z80 `LDIR`) are *operand-dependent* deltas (M7); until then they are modeled conservatively (worst case) or the region is `#suspend`ed.

### Source Notation

#### Tracking Regions
Subroutine boundaries cannot be reliably inferred from assembly source, and subroutines may have multiple entry points (multiple labels). Therefore region starts are **declared, not inferred**:

```asm
#track stack                    ; begin tracking; counter starts at 0
multiply:                       ; any number of labels may follow the directive —
multiply_alt_entry:             ;   all are entry points, all see the same counter state
    push a                      ; stack: 0 -> 1
.var_x = COUNTER(stack)         ; snapshot: name this stack slot
    push b                      ; stack: 1 -> 2
.var_y = COUNTER(stack)
    ld a, [sp + OFFSET(var_x)]  ; assembler computes current offset to var_x ( = 1 )
    pop b                       ; stack: 2 -> 1
    pop a                       ; stack: 1 -> 0
    ret                         ; flow_terminal for 'stack' -> region ends cleanly
```

* `#track <class> [as=<counter name>] [mode=<entry mode>] [init=<initial value>] [exit=<exit value>]` — creates a counter instance of the named class and opens its tracking region (keyword parameters follow the `#create-scope prefix="..."` convention). The counter's name defaults to the class name, so `#track stack` creates a counter named `stack`. `mode=` selects one of the class's configured `entry_modes`, supplying both init and exit values; explicit `init=`/`exit=` override the mode's values. With neither, the initial value is the class's `default_init` (0 unless configured) and the exit value equals the initial value. Opening a counter whose name is already active is an error (the prior region had no clear end point); multiple *concurrent* instances of the same class are allowed with distinct `as=` names.
* All other directives (`#assert`, `#set`, `#suspend`, `#resume`, `#endtrack`, `#entry`) and the `COUNTER()` / `OFFSET()` expression operators reference counter *instances* by name; slot snapshots record the instance they were taken from.
* A `flow_terminal` instruction (e.g. `ret`) ends the *path* that reaches it; an `#endtrack` ends the region explicitly. These are similar — both apply the exit-value check — but not identical: a `flow_terminal` is a real instruction that applies its own delta *before* the check and may occur many times (one per return path, each checked independently), whereas `#endtrack` is a single no-bytecode directive applying no delta. A region needs no `#endtrack` when every path terminates at a `flow_terminal`; it is closed once all paths have terminated. At every terminal, the counter value (after applying the terminal instruction's own delta, if any) must equal the region's exit value — a mismatch is an error. This is the **push-leak check**: every path out of the region must be balanced, not just the one the programmer was thinking about.
* `#endtrack <counter> [exit=<expected value>]` — explicitly ends a region; needed for counters with no natural terminal instruction (e.g., a cycle counter). The expected value defaults to the region's exit value. In CFG terms it is an exit node: every reachable edge arriving at it is exit-checked, and no edge may bypass it from inside the region to code after it. An edge entering after `#endtrack`, or leaving a region other than through its terminal / `#endtrack`, is a region-boundary error rather than a warning.
* `#entry <counter>` — declares the immediately following label an intentional alternate entry point at the current tracked value. It suppresses the mid-region entry-point warning **and adds that label as an independent CFG root** carrying the declared value, so its path to an exit is checked even when no in-region edge reaches it. Any ordinary incoming edge must reconcile with that value under the class's join policy.
* `#loop count=<N>` / `#loop max=<N>` — declares the number of **loop iterations** of the loop whose head immediately follows, letting interval counters compute a finite contribution and accumulating `require-equal` counters know the post-loop value (see *Loops*; M7). Thus `count=1` executes the body once and takes its back-edge zero times. `<N>` must be a compile-time constant.
* Multiple counters may have active regions simultaneously — whether of different classes or the same class — and each is tracked independently.

Concurrent instances of one class are what make measurement-window use cases work. Two overlapping cycle windows, where every instruction's declared cycle cost accrues to both:

```asm
#track cycles as=scanline init=0    ; outer window: whole scanline budget
    ...
#track cycles as=sync init=0        ; inner window opens mid-scanline
    out p, a
    nop
#endtrack sync exit=14              ; sync pulse must be exactly 14 cycles
    ...
#endtrack scanline exit=228         ; scanline must be exactly 228 cycles
```

#### Expressions
Counter access uses function-style expression operators, following the existing `BYTE0(..)` / `LSB(..)` precedent in the numeric expression grammar (a sigil prefix is not viable: `^` is the bitwise XOR operator, `$` is a hex prefix, `%` is binary, `@` is the operand-label sigil, `#` introduces preprocessor directives):

* `COUNTER(<counter>)` — the counter's current tracked scalar value at this line, usable in any numeric expression (including indirect-register offsets, which accept numeric expressions). It is invalid for an `interval` class.
* `COUNTER(<counter>).min` / `COUNTER(<counter>).max` — the lower / upper bound of an `interval` counter at this line. These selectors are valid only in flow assertions, never as ordinary numeric operands. Scalar counters have no `.min` / `.max` selectors.
* Slot snapshots are ordinary constants assigned from a counter value (`.var_x = COUNTER(stack)`), riding the existing constant-label syntax and label-scope machinery. No new scoping rules.
* `OFFSET(<slot>)` — sugar for `COUNTER(<counter>) - <slot>`: the current offset of a snapshotted slot relative to the associated scalar counter's present value. This is the feature issue #18 asks for. (The counter association of a slot is recorded at snapshot time; see Open Questions.) It is invalid for interval counters.

#### Assertions and Re-anchoring
* `#assert <counter> == <expr>` is shorthand for `#assert COUNTER(<counter>) == <expr>`. The general form is `#assert <flow-value> <comparison> <expr>`, where `<flow-value>` is `COUNTER(name)` for scalar counters or `COUNTER(name).min` / `.max` for interval counters, and `<comparison>` is one of `==`, `!=`, `<`, `<=`, `>`, or `>=`. It is a checkpoint: assembly errors when the comparison is false. For a scalar counter it also supplies ground truth at a join; for an interval assertion it checks the relevant bound and does not collapse the interval.
* `#set <counter> = <expr>` — re-anchors the tracked value when the programmer knows better than the assembler (e.g., after a stack-pointer manipulation the effect model cannot express). This is a programmer assertion and is taken on faith. In the CFG it transforms each incoming scalar state into the asserted scalar outgoing state; paths that bypass it remain unchanged and reconcile normally at a later join.

#### Subroutine Arguments and the Return Address
On many 8-bit ISAs, `call` pushes a 16-bit return address (+2) and `ret` pops it (−2). A subroutine that addresses caller-pushed arguments through the stack pointer must account for that return address sitting between its own frame and the caller's slots. Flow counters express this with two pieces already defined above: the region's *initial value* encodes the entry-time depth (the return address), and slot constants at or below that entry depth represent caller-owned slots.

```asm
; ---- caller ----
#track stack
    push a                  ; argument: stack 0 -> 1
    call my_func            ; composition rule: +2 (call) -2 (ret) -> net 0
    pop a                   ; reclaim argument: stack 1 -> 0
    ret

; ---- callee (possibly in another file) ----
#track stack mode=called    ; from ISA config: init=2 (16-bit return address), exit=0
my_func:
.arg_x = 0                  ; caller's argument sits just below the return address
    push b                      ; stack: 2 -> 3
    ld a, [sp + OFFSET(arg_x)]  ; = COUNTER(stack) - arg_x = 3:
                                ;   past pushed b (1) + return address (2)
    pop b                       ; stack: 3 -> 2
    ret                         ; applies -2 -> 0, matching the declared exit value
```

(The `.arg_x` constant is declared after `my_func:` because local-scope symbols cannot precede their parent non-local label; it lands in `my_func`'s local scope, which is where it belongs.)

Points of note:

* The `called` entry mode's `init: 2` *is* the return-address size, matching the `call` instruction's declared effect; its `exit: 0` exists because the terminal `ret` legitimately drives the counter below its entry value. `#track stack init=2 exit=0` is the equivalent explicit form, but the mode keeps that knowledge in the ISA configuration.
* Caller-side argument slots cannot be inherited automatically — a subroutine may be called from many sites at many depths. The callee instead *declares its calling convention* with explicit slot constants (`.arg_x = 0`, a second argument at `-1`, etc.), and `OFFSET()` arithmetic works unchanged. Inserting a new `push` inside the callee still updates every argument offset automatically, which is the core promise of issue #18.
* The caller's and callee's declarations are independent conventions; the analyzer cannot yet verify they agree (a caller pushing one argument where the callee expects two). That is the cross-region verification problem noted in Open Questions.

#### Entry Modes: Called vs. Jumped-To Routines
How a routine is *entered* is not inferable from its code — it is a calling-convention fact that lives in the heads of the routine's callers. A routine entered via `call` begins life with a return address on the stack; the same instructions entered via `jmp` (a dispatcher target, a coroutine, a tail-call destination) begin with nothing extra. The programmer declares which applies with `mode=`:

* **`mode=called`** — enters at the configured return-address depth and normally ends at a `flow_terminal` instruction (`ret`), whose effect consumes the return address down to the mode's exit value.
* **`mode=jumped`** — enters at 0 with no terminal instruction available: there is no `ret` to end the region, so the routine ends with an explicit `#endtrack` (exit check included) immediately before the unconditional transfer out:

```asm
#track stack mode=jumped
dispatch_handler:               ; reached via jmp from the dispatcher — no return address
    push a
    ...
    pop a
#endtrack stack                 ; exit check: balanced back to 0
    jmp dispatch_loop           ; transfer out — sanctioned, the region is already closed
```

* **Tail calls** mix the two: a routine entered via `call` that exits via `jmp` to another subroutine, leaving the original return address on the stack for the tail-callee's `ret` to consume. The tail path closes its region at the *entry* depth rather than the mode's exit value:

```asm
#track stack mode=called
process_fast:
    ...                         ; balanced body, back to depth 2
#endtrack stack exit=2          ; return address intentionally still on the stack
    jmp process_common          ; tail call; process_common's ret returns to our caller
```

* A routine entered via `call` from some sites and `jmp` from others has two genuinely different entry depths — no single static value exists, and the analyzer deliberately refuses to model it. The code must pick one convention (or be restructured, e.g., a thin called wrapper that falls into the jumped body).

### Tracking Semantics
* Tracking runs alongside the assembler's existing first pass (address assignment), which already walks line objects in source order.
* Every label inside an active region records the counter value at its position; these recorded values feed the consistency checks below.
* `COUNTER()` values and slot constants are fully determined during the first pass (constant deltas), so they resolve during second-pass expression evaluation exactly like label addresses — no new fixed-point iteration is required.
* Lines that emit no instructions (data directives, labels, comments) have no effect unless explicitly configured.

### Path Analysis and Ambiguity Rules
The analyzer is deliberately conservative: if it cannot prove the counter value at a line is unique, that is an error, not a guess.

#### The analysis model
Within a tracking region, the analyzer builds a small control-flow graph from the `flow_transfer` metadata and branch-target operands, then propagates counter values forward from the region entry and every `#entry` label with a worklist algorithm. A tracking region is a CFG region, not merely a source-text span: no CFG edge may enter after its `#track`, leave before a `flow_terminal` or `#endtrack`, or jump across an `#endtrack`. Such an edge is an error, because accepting it would create an untracked execution path. Directives are zero-bytecode CFG nodes: `#assert` checks and forwards its incoming state; `#set` re-anchors it; `#suspend` changes it to suspended; `#resume` restores a scalar state; and `#endtrack` is an exit node.

* Each line in the region gets *one* counter value per program point (not per path), reconciled across incoming edges per the class's `join` policy. Under `require-equal` (default) the first edge assigns the value and any later edge arriving with a *different* value is a join-mismatch error. Under `interval` the value is a `[min,max]` hull and a join unions the incoming hulls (never an error).
* A `conditional` transfer propagates to both the branch target and the fall-through line; an `unconditional` transfer propagates only to the target; a `call` propagates an abstract named-callee summary to the fall-through line. Each propagated edge applies that edge's delta — which for branch instructions may differ between the taken and fall-through edges (see *Edge-Dependent Deltas*).

* Every path must terminate at a `flow_terminal` instruction or `#endtrack`, where the exit-value check applies. `#suspend` / `#resume` must also be structurally balanced on every path: paths may not join in active and suspended states, bypass a `#resume`, or reach a terminal while suspended.
* Lines not reachable from any entry point have no counter value; referencing `COUNTER()` or `OFFSET()` on an unreachable line is an error (it usually indicates a label the analyzer could not connect, e.g., a target of an `indirect` jump).

The *Loops* and *Consecutive Branches and Path Count* subsections below explain how this per-point model handles cyclic and heavily-branched control flow.

Because each path is checked independently, **per-path imbalances ("push leaks") are detected even when only one path is wrong**:

```asm
#track stack
divide:
    push b                  ; stack: 0 -> 1
    cmp a, 0
    jz .div_by_zero
    ; ... normal path ...
    pop b                   ; stack: 1 -> 0
    ret                     ; exit check: 0 == 0, OK
.div_by_zero:
    ld a, 0xff
    ret                     ; ERROR: counter 'stack' is 1 at terminal, expected 0
                            ;   push at line 3 is never popped on this path
```

Had the two paths rejoined instead of returning separately, the join-mismatch rule catches the same leak at the rejoin label: one predecessor arrives with `stack = 0`, the other with `stack = 1`.

#### Loops
A loop is not a special construct — it is simply a `flow_transfer` branch whose target precedes it in execution order, i.e. a **back-edge** in the CFG. No loop-specific configuration exists; loops fall out of ordinary branch metadata. How the analysis accounts for one depends on the counter's `join` policy and whether the loop body is net-zero:

* **Net-zero body (`require-equal`).** The counter returns to the same value each iteration, so the loop head is consistent across the entry edge and the back-edge — no mismatch, fully sound, no annotation needed. This is the well-behaved common case (a loop that pushes and pops symmetrically per iteration).
* **Net-nonzero body (`require-equal`).** Each iteration changes the counter, so the loop head receives different values from the entry edge and the back-edge → **join-mismatch error**. This is correct: a stack-imbalanced loop is a bug. The exception is a loop that legitimately accumulates a runtime-determined amount (the arbitrary-length push) — handled by `#suspend`/`#resume` (see *Runtime-Variable Counter Changes*).
* **Accumulating body (`interval`).** Each iteration adds cost, so naive hull-unioning over the back-edge would widen forever (`entry`, `entry+C`, `entry+2C`, …) and never converge. The worklist therefore applies **widening at loop heads** — after a small fixed number of revisits it jumps the open end of the hull to `∞` — guaranteeing termination. An unbounded loop thus yields an unbounded WCET, reported honestly ("cannot bound cycles across this loop; supply an iteration count") rather than silently wrong.
* **Bounded loops (M7).** To get a *finite* bound through a loop, the programmer supplies the trip count the analyzer cannot infer:

```asm
#loop count=8            ; this loop body executes exactly 8 times
.fill_loop:
    st [hl], a
    inc hl
    dec c
    jnz .fill_loop
```

  `#loop count=N` (exact) or `#loop max=N` (upper bound) lets an `interval` counter compute a finite contribution for **N body executions**, including the fall-through cost on the final iteration, instead of widening to `∞`; it lets a `require-equal` counter that accumulates a *known* amount per iteration treat the post-loop value as deterministic (`entry + N × body`). The trip count must be a compile-time constant; otherwise the loop stays unbounded/indeterminate. Inside such a loop, `COUNTER()`/`OFFSET()` references remain indeterminate (the value differs per iteration) — the annotation makes the *post-loop* value knowable, not the interior.

#### Consecutive Branches and Path Count
A sequence of *k* branches creates up to 2ᵏ distinct execution paths, but the analysis **does not enumerate paths** — and this is the key to why it scales. The worklist computes one lattice value per *program point* and merges incoming edges there per the `join` policy, so cost is **O(nodes + edges), not O(2ᵏ paths)**. Consecutive branches simply add more nodes and merge points; nothing about them is exponential.

The deliberate trade is that the analysis is **path-insensitive**: merging at joins discards correlations between branches (it cannot know that "if branch A took the taken edge then branch B must too"), so it treats all 2ᵏ edge combinations as possible even when some are dynamically infeasible. Both join policies stay *sound* in the safe direction:

* `require-equal` never misses a real imbalance, but may report a mismatch on a path that cannot actually occur (a false positive).
* `interval` never under-estimates, but may report a WCET higher than any real execution reaches (a conservative over-approximation).

Where path-insensitivity costs precision, the programmer injects ground truth: `#assert` pins a counter to a known value at a point (collapsing spurious divergence), and `#set` re-anchors it. So consecutive branches are accounted for in linear time, with any imprecision surfaced as a *safe* error/over-estimate the programmer can refine — never as a silent wrong answer. Nested and consecutive branches compose freely: as long as each branch reconverges to a consistent value (for `require-equal`) before the next merge, arbitrarily many compose with no special handling.

#### Label-Scope Awareness (mid-region entry points)
The analysis only follows control flow it can see; it cannot know about a `jmp` or `call` elsewhere in the program targeting a label inside the region. Whether such an outside transfer is *possible* is determined by the label's scope, which the assembler already tracks:

* **Local labels (`.` prefix)** cannot be referenced from outside the local scope bounded by their parent label. They pose no external-entry risk and are exempt from this check.
* **Global, file (`_` prefix), and named-scope labels** are reachable from code the analyzer is not looking at. Each one inside a region is a *potential entry point* — and outside code transferring there will, by convention, assume the region's entry-time counter value.

Therefore: a global, file, or named-scope label inside an active region where the tracked value differs from the region's initial value is a **warning** by default — there is a latent runtime imbalance if anything ever enters there — escalatable to an error via the warnings-as-errors mechanism. Labels at the region's entry value produce no diagnostic, which is what makes the multiple-entry-point pattern (several labels at the top of a region, all at the initial value) work without ceremony.

For the rare label that *is* an intentional alternate entry at a non-entry depth, the `#entry <counter>` directive placed before the label acknowledges it: the warning is suppressed, the label's tracked value becomes its documented entry convention, **and the label is added as an independent CFG root carrying that value**. This verifies the alternate-entry path to its terminal now; a future cross-region verification phase can additionally check that outside call sites honor the convention.

This analysis needs surprisingly little knowledge of instruction behavior: only the transfer classification (4 categories), branch targets the assembler already parses, and the declared deltas. It does *not* model registers, memory, or flags — which is why `conditional` branches are treated as "either way is possible" and both paths must independently check out. The analysis can therefore flag a path that is dynamically impossible (e.g., a branch guarded by a condition that always holds); the `#set` / `#suspend` escape hatches and per-counter `unknown_instructions` setting exist for exactly those cases.

**Calls compose rather than inline:** when the analyzer encounters a `call`, it does not descend into the callee. Its fall-through value carries an abstract per-class summary, `CallEffect(<resolved callee label>, <counter class>)`. The summary records the callee identity instead of silently assuming that every class has the same callee behavior. A later interprocedural phase resolves it from the named callee's verified region.

For stack-style counters, the existing terminal convention is an immediately resolvable summary: the analyzer assumes the callee is balanced — that the callee's terminal instruction consumes exactly what the call pushed — and computes:

```
value_after = value_before + call.flow_effects + terminal.flow_effects
```

With `call: +2` and `ret: -2` this nets to zero, as it should: the return address is pushed and later popped, invisible to the caller. The rule also models callee-pops-arguments conventions naturally (e.g., a `ret 2` variant declared as `stack: -4` yields a caller-visible net of −2). Configuration validation requires all `flow_terminal` mnemonics for a counter to declare identical `flow_effects`; if an ISA needs divergent terminals, an explicit per-call-instruction net override would be required (deferred until a real ISA demands it).

For every other class — notably cycles — the summary remains unresolved in M5/M6. The analyzer must not turn it into a scalar, interval bound, or operand literal: a value after such a call cannot be used by `COUNTER()`/`OFFSET()`, bounds checks, or precise timing assertions until the later phase resolves the named callee. This is conservative by design: counting only the call instruction and omitting the callee body would make WCET and constant-time claims unsound.

The callee's own balance is verified by the callee's own tracking region. Stack-style composition therefore remains tractable — each subroutine is verified once and callers use the terminal convention — while other classes retain their named summary until the later whole-program phase verifies that a *specific callee* supplies the required effect (see Open Questions).

#### Error and warning rules
1. **No clear end point** — a `#track` region that reaches end of file, the start of another region for the same counter, or an unconditional transfer out of the region without hitting a `flow_terminal` instruction or `#endtrack` → error.
2. **Join mismatch** (`require-equal` classes only) — a line reachable along multiple paths carrying different counter values → error reporting both values and their source lines. Backward branches (loops) are the common case: a branch back to a loop head errors unless the loop body is net-zero for the counter — precisely the class of bug this feature should catch. See *Runtime-Variable Counter Changes* for loops that are intentionally not net-zero. For `interval` classes this is not an error; paths simply union into the hull, and divergence is surfaced only if a `#assert` bound is violated.
3. **Exit imbalance (push leak)** — any path reaching a `flow_terminal` instruction or `#endtrack` with a counter value different from the region's exit value → error identifying the path's distinguishing branch.
4. **Bounds violation** — counter exceeds `max_value` or drops below `min_value` (e.g., more pops than pushes) on any path → error.
5. **Dead slot reference** — a slot snapshot has a monotonic validity bit in addition to its numeric counter value. It is permanently invalidated on every path that drops below its snapshot value: the stack has popped that particular slot, and a later push to the same depth creates a different slot. At a join, a slot invalid on any incoming path is invalid thereafter. `OFFSET(slot)` on an invalid slot → error. This is distinct from a `min_value` violation: dropping below a slot's depth can be normal even when the counter remains within its configured bounds. `#set`, `#resume`, and an `#entry` root at a non-initial depth also invalidate prior slot snapshots unless a future explicit preservation contract says otherwise.
6. **Unknown instruction effect** — an instruction with no declared effect for an actively tracked counter, handled per the counter's `unknown_instructions` setting.
7. **Indirect transfer** — an `indirect` jump inside an active region → error (the analysis cannot follow it) unless the counter is suspended.
8. **Region-boundary crossing** — a branch targeting a label outside the active region for the counter, entering a region after its `#track`, or jumping across an `#endtrack` → error. Unlike a `.org` auto-close warning, this is an actual execution path that would otherwise be silently untracked.
9. **Mid-region external entry point** — a global, file-scope, or named-scope label inside a region where the tracked value differs from the region's initial value → warning by default, escalatable to an error via warnings-as-errors; suppressed by a preceding `#entry` directive. Local-scope (`.`) labels are exempt (see *Label-Scope Awareness*).

### Runtime-Variable Counter Changes (Indeterminate State)
Some code changes a tracked quantity by an amount that is only knowable at run time. The canonical example: pushing the characters of a null-terminated string of arbitrary length onto the stack.

```asm
push_string:                ; HL points to null-terminated string
.loop:
    ld a, [hl]
    cmp 0
    je .done
    push a                  ; stack +1 per iteration — iteration count unknown at assembly time
    inc hl
    jmp .loop
.done:
    ...
```

A flow counter is a *static* quantity; no assembly-time analysis can know the stack depth at `.done`. The design treats this honestly rather than guessing:

* **Default behavior:** the join-mismatch rule catches it. `.loop` is reachable from fall-in with `stack = 0` and from the backward branch with `stack = 1`; the analyzer errors with both paths identified. The programmer is forced to acknowledge that the counter is no longer statically known — there is no silent wrong answer.
* **Acknowledgement mechanism:** the counter can be placed in an explicit **indeterminate state**:

```asm
.before_push = COUNTER(stack)   ; snapshot the known depth
#suspend stack              ; counter becomes indeterminate
.loop:
    ld a, [hl]
    cmp 0
    je .done
    push a
    inc hl
    jmp .loop
.done:
    ; ... later, after a symmetric pop loop or restoring SP from a saved copy ...
#resume stack = .before_push   ; re-anchor; programmer assertion, taken on faith
```

* While a counter is **suspended**:
  * instruction effects are not applied and bounds/join checks are not performed for that counter;
  * any reference to `COUNTER()`, and any `OFFSET()` against it, is an **error** — there is no value to resolve;
  * creating new slot snapshots against it is an error;
  * encountering a `flow_terminal` instruction for the counter (e.g., `ret`) while suspended is an error: the region's balance cannot be verified, so the programmer must `#resume` (asserting a value) or `#endtrack` explicitly first.
* `#resume <counter> = <expr>` re-anchors the counter to a known value, typically a snapshot taken before suspension. Like `#set`, it is an unverifiable programmer assertion.
* Slot snapshots taken *before* suspension retain their numeric snapshot values, but `#suspend` / `#resume` does not prove that the run-time slots survived the indeterminate interval. Therefore `#resume` permanently invalidates every slot snapshot for that counter unless the directive explicitly names a future, stronger slot-preservation contract. An invalid snapshot may never be passed to `OFFSET()`.

Note the deliberate parallel with run-time reality: when the stack pointer moves by a runtime-determined amount, `sp`-relative addressing of older slots is invalid *at run time* too — the standard assembly idiom is to save the stack pointer into a frame-pointer register first. The indeterminate state mirrors exactly the window in which the programmer cannot use `sp`-relative offsets anyway, and the pre-suspension snapshot mirrors the frame pointer.

A possible refinement for *bounded* runtime variability (e.g., "this loop pushes at most 16 items") would be a suspended-with-bounds mode that keeps `min_value`/`max_value` checking alive using an interval instead of a point value (M7, alongside bounded-loop iteration counts). Out of scope for earlier milestones.

### Diagnostics
All violations are reported through the existing `DiagnosticReporter` with a new category (e.g., `flow`), so `--warnings-as-errors` selection and tooling integration come for free.

## Key Acceptance Test Cases
Organized by what each group proves. "Error/warning" expectations include asserting the diagnostic's category (`flow`), file, and line number — a diagnostic on the wrong line is a failing test.

### Static-analysis-only invariant (the load-bearing guarantee)
1. **Strip-equivalence golden test:** at each milestone, assemble a program exercising every **shipped** directive and expression operator; assemble its hand-stripped twin (directives removed, `COUNTER()`/`OFFSET()` replaced with resolved literals); outputs are byte-identical.
2. **Config inertness:** the same source assembles to identical bytes under an ISA config with and without `flow_counters`/`flow_effects` metadata, when the source uses no flow counter features.
3. **Zero address footprint:** label addresses and `.org`-relative layout are identical with and without flow counter directives interleaved in the source.

### Configuration validation
4. `flow_effects`, `flow_terminal`, or `flow_transfer` naming an undeclared counter → config error.
5. Two `flow_terminal` mnemonics for the same counter with different `flow_effects` → config error (composition rule would be ambiguous).
6. Invalid `unknown_instructions` value or non-integer delta → config error.

### Linear tracking and expressions (M1; slot/`OFFSET` cases in M2; control/multi-counter cases in M4)
7. `COUNTER(stack)` reflects declared deltas through a push/pop sequence; verified via emitted operand bytes.
8. **Issue #18 scenario:** slot snapshots + `OFFSET()`; inserting a new `push` between snapshot and use changes the emitted offset byte by exactly one — no source edits to the `OFFSET()` line.
9. `OFFSET()` inside an indirect-register operand (`[sp + OFFSET(x)]`) emits the same bytes as the hand-written literal.
10. `min_value` underflow (one pop too many) and `max_value` overflow → errors on the offending instruction's line.
11. `#assert` passing is silent; failing reports expected vs. actual.
12. `#set` re-anchors and downstream values reflect it.
13. Balanced region ending at a `flow_terminal` is silent; straight-line push leak → exit-imbalance error.
14. `#endtrack` default and explicit `exit=` expectations; mismatch → error.
15. Region reaching EOF unterminated → error; second `#track` for an active counter → error.
16. Two counters (`stack`, `cycles`) advance independently from one instruction stream; each reports its own violations.
17. `unknown_instructions: ignore | warn | error` each behave as configured for an effect-less instruction inside a region.

### Label-scope awareness
18. Global label mid-region at non-entry value → warning; escalated to error under warnings-as-errors; file-scope (`_`) and named-scope labels likewise.
19. Global label at the entry value (multi-entry pattern) → silent.
20. Local (`.`) label at any tracked value → silent.
21. `#entry` before the label suppresses the warning **and creates an independent CFG root at the declared value**; its path to a terminal is checked even with no in-region predecessor. `#entry` with no following label → error.

### Path analysis (M5)
22. Diverge/rejoin with both paths balanced → silent.
23. One branch missing its pop, paths rejoin → join-mismatch error naming both values and both source lines.
24. One branch missing its pop, paths return separately (the spec's `divide` example) → exit-imbalance error on that path's `ret` only. A slot popped on one path and not another is invalid after the join; pushing a replacement slot to the same depth does not make `OFFSET()` valid again.
25. Net-zero loop body → silent; net-positive loop body → join mismatch at the loop head.
26. Code after an unconditional `jmp` is not treated as fall-through; an unreachable line using `COUNTER()` → error.
27. Call composition: `call`(+2)/`ret`(−2) nets zero at the fall-through; a callee-pops variant (`ret 2` as −4) nets −2; verified via a subsequent `OFFSET()` operand byte.
28. `indirect` jump inside an active region → error; same jump with the counter suspended → accepted.
29. Branch targeting a label outside the region, entering after `#track`, or jumping across `#endtrack` → region-boundary error.

### Cycle counting, join policy, and edge deltas
30. Straight-line cycle counter: distinct per-instruction `cycles` deltas accumulate; the difference between two snapshots equals the hand-summed cost.
31. `join: interval` class: an `if/else` whose arms differ in cycles is **silent** (no join-mismatch error); `#assert COUNTER(cycles).max <= N` passes when both arms fit and fails when one exceeds.
32. `join: require-equal` cycle class (constant-time): two paths with equal cost → silent; arms differing by one cycle → join-mismatch error naming both totals (the constant-time-violation case).
33. Edge-dependent delta: a conditional branch with `cycles: { taken, fall_through }` contributes the correct cost on each edge; the interval hull at the rejoin reflects both.
34. Using an `interval`-class counter's bare `COUNTER()` as an operand value → error; using `COUNTER(cycles).min` / `.max` in a range `#assert` → accepted. A timing counter with an unresolved named-callee summary cannot be used in an operand, bound check, or precise timing assertion.

### Indeterminate state
35. Runtime-length push loop with no acknowledgement → join-mismatch error (the default catches it).
36. `#suspend` silences tracking; `COUNTER()` reference, new snapshot, or `flow_terminal` instruction while suspended → errors.
37. `#resume` to a pre-suspension snapshot restores tracking but invalidates pre-suspension slots; `OFFSET()` on one of those slots → error. A slot popped below its snapshot and then replaced by a new push at the same depth remains invalid (it is not resurrected).

### Subroutine arguments across the return address
38. Callee with `init=2 exit=0` and caller-arg slot constants at/below 0: `OFFSET(arg)` operand bytes account for callee pushes plus the return address; `ret`'s −2 satisfies `exit=0`.

### Entry modes
39. `#track stack mode=called` applies the class's configured `init`/`exit`; explicit `init=`/`exit=` on the same directive override the mode's values; `#track` with neither uses `default_init`.
40. Jumped-to routine: `#endtrack` (exit check passing) immediately before the unconditional `jmp` out → silent; the same `jmp` with the region still open → no-clear-end error.
41. Tail call: `mode=called` routine closing with `#endtrack exit=2` before a `jmp` to another subroutine → silent; the same tail `jmp` with an unbalanced frame → exit-mismatch error.
42. `#track mode=` naming a mode not declared in the class's `entry_modes` → error.

### Counter classes and instances
43. `#track stack` with no `as=` creates a counter named after its class; all references by class name work (the common-case ergonomics test).
44. Two concurrent instances of one class (the overlapping cycle-windows example): one instruction's declared cost accrues to both; each `#endtrack exit=` is checked independently.
45. Opening a counter whose name is already active → error; two concurrent instances with distinct `as=` names → accepted.
46. A `flow_terminal` instruction terminates every active instance of its class, each against its own exit value; an active instance of a *different* class is unaffected.
47. `#track` naming an undeclared class, or `COUNTER()` naming an inactive instance → errors.

### Interaction with existing features
48. Flow counter directives inside an inactive `#if` block are ignored entirely (no region opened).
49. `#mute` does not affect tracking (analysis follows compiled code, not emitted code).
50. Multiple instructions on one source line apply their effects in order.
51. Instruction macro inside a region contributes the aggregate effect of its expansion (e.g., a macro expanding to two `push`es moves `stack` by +2); a macro whose expansion contains a `flow_terminal` instruction ends the region. Declaring `flow_effects`/`flow_terminal`/`flow_transfer` on a macro definition → configuration error.
52. Region active at an `#include`, `.org`, or memory zone change → behavior per Open Questions 3 and 7 once settled; the test exists to force the decision.

### Required configuration metadata (fail loud)
53. `#track X` where `X` is declared in `flow_counters` but no instruction populates `X`'s `source` field (and no `flow_terminal` lists `X`) → error (declared-but-inert class); the counter is never silently tracked as a no-op. A `source` path pointing at a non-numeric field → configuration error.
54. A control-transfer instruction lacking `flow_transfer` appearing inside a region under path analysis → error naming the instruction (M5); the branch is never silently treated as straight-line.
55. Error timing: malformed `entry_modes` and divergent per-class `flow_terminal` effects error at config load even when no source uses the counter; inert-class and `flow_transfer`-coverage error only when the counter is actually tracked.

### Feature enablement (usage-gated)
56. ISA with **no** `flow_counters` section + source using a flow-counter construct (`#track`, `COUNTER()`, etc.) → error ("instruction set does not enable flow counters"); the error fires only because the construct was used.
57. ISA with no `flow_counters` section + source using no flow-counter construct → assembles byte-identically to the same source/ISA pre-feature (feature fully dormant).
58. ISA enabling classes `A` and `B`; source tracks only `A` → no diagnostic about `B`, even if `B` is inert or never used (enabled-but-unused class imposes no obligation).

### Operand-dependent and macro-aggregate effects
59. `add sp, 4` with `flow_effects: { stack: -ARG(0) }` → `stack` decreases by 4; a subsequent `OFFSET()`/`COUNTER()` value reflects it. `add sp, FRAME_SIZE` (constant symbol) resolves identically to the literal.
60. `add sp, a` (runtime register operand) inside a region tracking `stack` → counter indeterminate: error if `COUNTER()`/`OFFSET()` is used while not suspended; accepted under `#suspend`.
61. Macro expanding to `push`/`push` contributes net `stack` +2 (aggregate of expansion); a macro expanding to a sequence ending in a `flow_terminal` instruction ends the region. A macro definition declaring `flow_effects`/`flow_terminal`/`flow_transfer` → configuration error.

### Source field binding
62. A counter reading `source: documentation.cycles` accumulates each instruction's `documentation.cycles` integer; a class omitting `source` reads `flow_effects.<class>`; two classes (`cycles`, `ct_cycles`) reading the same `source` field both track it, differing only by `join`.
63. An instruction missing the `source` field of an actively-tracked class is handled per that class's `unknown_instructions` (so `error` enforces complete data, e.g. every instruction must carry `documentation.cycles`).

### Branches, loops, and path count
64. Edge-keyed delta: a `conditional` branch with `cycles: {taken, fall_through}` contributes the right cost on each edge; the interval hull at the rejoin reflects both; a scalar `stack_effect` on the same branch applies equally to both edges.
65. Multi-counter branch: one branch carrying an edge-map for `cycles` and a scalar for `stack` updates each counter from its own source field independently.
66. Net-zero loop body (`require-equal`) → silent; net-nonzero loop body → join-mismatch at the loop head; runtime-length accumulating loop under `#suspend` → accepted.
67. `interval` counter across an unbounded loop → WCET reported as unbounded (widening terminates the worklist); the same loop with `#loop count=N` → finite `body × N` contribution; `#loop count=<runtime expr>` → error (count must be compile-time constant).
68. `k` consecutive balanced branches assemble in time linear in lines (no 2ᵏ blow-up); an infeasible-path false positive under `require-equal` is silenced by `#assert`; interior `COUNTER()` inside a `#loop`-counted nonzero loop → indeterminate error.

### Tooling collateral (M1 and per-milestone)
69. At **each milestone**, extensions generated from a flow-enabled ISA include every **then-shipped** flow directive and expression form in all three grammars (VS Code, Sublime, Vim), with hover docs present; extensions generated from a non-enabled ISA contain none of the flow-counter tokens. Every shipped flow directive/operator has a `directive_docs.py` entry (enforced by the existing docsgen test). The fixture matrix grows as syntax ships: M1 (`#track`, `#endtrack`, `COUNTER()`); M2 (`OFFSET()`); M4 (`#assert`, `#set`, `#suspend`, `#resume`); M5 (`#entry`); M6 (`COUNTER(x).min` / `.max` assertion forms); M7 (`#loop`).
70. **Analysis-record preservation (M0):** assembling a flow-enabled program containing an instruction variant, a branch-target operand expression, and an instruction macro preserves an immutable analysis record for every constituent instruction (selected variant, source mnemonic, matched operands / expressions, and source-order identity), while producing byte-identical output to the same program assembled without the analysis pass.
71. **Straight-line slot invalidation (M2):** after a slot snapshot, a pop below its snapshot followed by a replacement push to the same counter value leaves `OFFSET(slot)` invalid; the original slot is never resurrected.

## Implementation Phasing
The work splits into small vertical slices, each independently shippable and gated by a specific group of acceptance tests (numbers refer to *Key Acceptance Test Cases*). Each milestone delivers a usable capability or de-risks the next, and is ordered by dependency. The three coarse stages map as: **analysis substrate = M0**, **linear tracking = M1–M4**, **path analysis = M5–M6**, **richer effects = M7**.

Each milestone names an **acceptance demo**: a concrete, runnable scenario with an observable outcome that proves the milestone's goal. The demos are specific enough to be committed as example programs under `examples/` and to double as end-to-end integration tests — a durable, re-runnable artifact per milestone, not just a green unit-test suite.

1. **M0 — Analysis substrate + inertness proof.** Retain an immutable analysis record for every selected instruction variant and macro constituent (selected variant, source mnemonic, parsed/matched operands, and source-order identity); add deferred flow-expression support so a future `COUNTER()` constant is not evaluated during source loading; establish a source-order executable-node index and the `flow` diagnostic category. Parse the `flow_counters` schema and per-instruction metadata, but expose no flow directives or expression operators yet. *Delivers:* the data needed by every later milestone while proving that carrying it does not alter assembly. *Gated by:* 2, 4–6, 70. **Demo:** assemble a flow-enabled program containing an instruction variant, a symbolic branch target, and a macro; the normal binary is byte-identical to its baseline, while an integration test inspects the retained analysis records and verifies every constituent’s metadata and operand expression.
2. **M1 — Single-counter linear core + tooling pipeline.** Ship `#track` / `#endtrack`, scalar `COUNTER()` in expressions, constant deltas, `min`/`max` bounds, and the exit-value check for straight-line regions. A region containing a transfer emits a "path analysis not yet applied" warning; `COUNTER()` / `OFFSET()` occurrences in such a region are errors until M5 can prove their values. Ship the editor/documentation pipeline with this first visible syntax: central keyword entries, hover docs, per-ISA grammar gating, generated-extension verification, wiki, and changelog. *Delivers:* straight-line depth/cycle tracking that changes no bytecode. *Gated by:* 1, 3, 7, 10, 14, 15, 17, 48–50, 56–58, 69. **Demo:** assemble a straight-line routine using `COUNTER(stack)` in an operand; its byte and hand-stripped twin are identical, while an explicit `#endtrack` mismatch and a `min_value` underflow each fail on the relevant line. Generate an extension from the same flow-enabled ISA and verify `#track`, `#endtrack`, and `COUNTER()` are highlighted with hover documentation.
3. **M2 — Stack slot labels (closes issue #18 for straight-line code).** Add deferred slot snapshots (`.x = COUNTER(stack)`), tagged origins, `OFFSET()`, and straight-line permanent dead-slot invalidation. *Delivers:* the headline issue-#18 capability without waiting for CFG analysis. *Gated by:* 8, 9, 71. **Demo:** the issue-#18 program snapshots a slot and addresses it with `[sp + OFFSET(x)]`; inserting one `push` changes the emitted offset from 1 to 2 without editing the access, while popping the slot and pushing a replacement at the same depth still makes `OFFSET(x)` fail.
4. **M3 — Linear subroutine and frame ergonomics.** Add unconditional `flow_terminal` processing, entry modes, called-entry argument slots, and compile-time-constant operand-dependent deltas (`add sp, N`). Calls, jumps, tail calls, and conditional terminals remain transfer-containing regions until M5. *Delivers:* straight-line called routines with return-address-aware stack offsets. *Gated by:* 13, 38–40, 42, 59. **Demo:** the `multiply`/`factorial` routine assembles under `#track stack mode=called`; an `[sp + OFFSET(arg)]` operand accounts for the return address and local pushes, and an `add sp, N` teardown balances at `ret`; a wrong pop or frame adjustment fails at the terminal.
5. **M4 — Manual linear control + concurrent counters.** Add scalar `#assert` / `#set`, `#suspend` / `#resume` for straight-line indeterminate spans, and concurrent instances/classes with `as=` naming. Full path-sensitive suspended-state checking waits for M5. *Delivers:* explicit programmer control and overlapping measurement windows. *Gated by:* 11, 12, 16, 36, 43–47. **Demo:** one routine tracks `stack` and two overlapping `cycles` windows; each instruction updates the active instances independently, an assertion and re-anchor affect only the named counter, and a suspended straight-line span rejects `COUNTER()` until resumed.
6. **M5 — CFG and path-consistency core.** Build `flow_transfer` CFG edges, label→executable-node resolution, per-program-point `require-equal` propagation, region-boundary validation, `#entry` roots, call summaries, tail-call handling, and complete suspended-state analysis. Add per-path terminal checks, join mismatches, net-zero loop checks, indirect-transfer errors, label-scope warnings, and path-aware slot invalidation. *Delivers:* branchy stack routines are genuinely verified rather than merely scanned in source order. *Gated by:* 18–29, 35, 37 (path-sensitive portion), 41, 54, 66, 68. **Demo:** Example C reports the leaked push at the incorrect return path; adding the missing pop succeeds. A runtime-length loop fails without `#suspend`, succeeds when suspended/resumed, and a tail-call routine closes at its entry depth before the jump.
7. **M6 — Timing and interval analysis.** Add `join: interval`, edge-keyed deltas, widening for unbounded loops, range assertions, and constant-time checking. Carry unresolved named-callee summaries so timing claims cannot silently exclude callees. *Delivers:* sound branch-sensitive WCET/constant-time analysis for regions without unresolved callees. *Gated by:* 30–34, 64, 65, 67 (unbounded case). **Demo:** a branchy routine passes or fails `#assert COUNTER(cycles).max <= N` based on its computed worst case; Example F catches unequal path timing; a timing assertion after an unresolved call is rejected.
8. **M7 — Rich effects and finite loops.** Add structural operand-dependent deltas (`COUNT(0)`, page-cross penalties), runtime-operand handling, conditional terminals, `#loop count=/max=`, and finite post-loop interval results. *Delivers:* bounded-loop timing and richer ISA-specific effects. *Gated by:* 51, 60, 61, 67 (bounded case), and extensions of earlier groups. **Demo:** Example E computes a finite bound for `#loop count=100` and becomes unbounded when the annotation is removed; `pushm {r0-r3}` and a macro expanding to two pushes each produce their expected tracked offsets.

**Collateral definition-of-done (every visible milestone from M1 on): new language surface ships with its collateral.** M1 builds the pipeline with its first directives/operators; afterward, any milestone that adds or activates source syntax, an expression form, or a config key must ride it in the same release: keyword-registry entries (`keywords.py`), hover/doc entries (`directive_docs.py`), regenerated-extension verification, wiki section, and changelog line. Concretely: `OFFSET()` lands with **M2**; `#assert`/`#set`/`#suspend`/`#resume` with **M4**; `#entry` with **M5**; interval selectors / assertion forms with **M6**; and `#loop` with **M7**. Config-key documentation (`join`, `entry_modes`, call summaries, edge maps) lands with the milestone that activates each. A milestone is not done while its syntax is invisible to the editors.

Sequencing notes:
* M0 is deliberately testable even though it adds no source syntax: its byte-identical compile plus retained-record integration test is the contract that permits every later milestone to rely on the new data without risking bytecode changes.
* M4's multi-counter support may prove nearly free atop M1 (a loop over active instances) and could merge earlier; it is kept separate to keep M1 minimal.
* Real verification of branchy code — i.e., every practical subroutine — arrives at **M5**; M1–M4 are intentionally linear-only. #18's straight-line request closes at **M2**, but "verify my subroutine's stack is balanced no matter the path" and all tail-call / runtime-loop claims need **M5**.

## Architecture Anchors
* **Config parsing/validation:** `AssemblerModel` (`src/bespokeasm/assembler/model/__init__.py`), `_validate_config()`.
* **Directive parsing:** new preprocessor line types alongside `#create-scope` et al. in `line_object/preprocessor_line/factory.py`.
* **Tracking pass:** a *separate* analysis pass in `Assembler.assemble_bytecode()` (`src/bespokeasm/assembler/engine.py`). It must run after first-pass address assignment (so labels resolve) but **before** the existing `compilable_line_obs.sort(key=address)` step — because the tracker walks *source/execution* order (fall-through = the next source line), whereas the sort reorders the list into *address* order for the second pass, and `.org`/memory-zone use makes the two orders differ. It must not share mutable state with, or alter, the address-counter / `MemoryZoneManager` advance path (see *How Much Should They Share?* and the *Static Analysis Only* guarantee).
* **Diagnostics:** `DiagnosticReporter` (`src/bespokeasm/assembler/diagnostic_reporter.py`) with a new `flow` category; lines are identified by the existing `LineIdentifier` (filename + line number) every line object already carries.

## Architecture Changes Required
A code-level review of the current assembler establishes that the pass scaffolding, diagnostics, label scope, expression parser, and preprocessor-directive system are all either ready or need only small additive changes — but two structural facts about the codebase drive real work. First, the assembler is a *generate-bytecode-then-discard* pipeline: once an `InstructionLine` produces its `AssembledInstruction` (bytecode parts + word count), it drops the matched `InstructionVariant`, the `isa_model`, the mnemonic, and the operand expression trees. Second, it has **no control-flow awareness whatsoever** — a branch operand is just an expression, with no notion of a target line, successor, or predecessor. The changes below are organized by how much they disturb existing code.

### Ready as-is (no change)
* **Pass insertion.** A third pass slots cleanly between first-pass address assignment and the existing second pass; the two existing passes have no coupling that a read-only analysis pass between them would break.
* **Branch-target → CFG-node resolution.** The engine already builds an address→line map (`line_dict`), but that alone is not sufficient: labels, directives, data, and multiple source lines may share one address. The CFG resolver must retain the resolved target label when available and map it to the next executable instruction node; an address-only target must resolve uniquely to such a node or report a flow diagnostic. A target into data, a non-executable directive, or an ambiguous same-address group is not silently assigned a successor.
* **New `#` directives.** `#track` and friends follow the existing `#create-scope` / `#mute` precedent exactly — persistent, source-ordered line objects registered in the preprocessor-line factory, receiving `label_scope`/memory-zone context. `#if`-excluded lines are retained but flagged `compilable = False` (filter them, matching "tracking follows compiled code"); `#define` is a separate textual pre-pass and does not interfere.
* **Diagnostics.** `DiagnosticReporter` + `LineIdentifier` cover error/warn/info with line attribution.

### Small additive changes (low risk)
* **Label-scope origin tags.** `LabelScope.LabelInfo` stores an `int` value; `get_label_value()` returns that int. Adding an optional origin tag (counter name + snapshot) is backward-compatible — existing callers read `.value` unchanged. This realizes "slot snapshots as tagged-origin constants."
* **Expression operators.** The hand-rolled recursive-descent parser (`src/bespokeasm/expression/__init__.py`) implements `LSB(..)` / `BYTE0(..)` as function-style tokens; `COUNTER(..)` / `OFFSET(..)` replicate that pattern (token, regex, parse case, compute case). Add both to the reserved `EXPRESSION_FUNCTIONS_SET` (`keywords.py`) so they cannot collide with user labels.
* **Config parsing.** `flow_counters` classes and the per-instruction `flow_effects`/`flow_terminal`/`flow_transfer` keys are parsed and validated in `AssemblerModel._validate_config()` (config-load consistency checks). The capability-completeness checks (inert class, `flow_transfer` coverage, mode availability — see *Required Metadata: Fail Loud, Never Silently Inert*) run usage-time in the tracking pass, since whether the metadata is sufficient depends on what the source asks of the counter.

### Genuine structural changes (the real work)
* **(A) Retain per-instruction config and operands on the line.** *(M0; M1 consumes effects and M5 consumes operand expressions.)* Today neither is reachable from an `InstructionLine` at analysis time. Store the matched `InstructionVariant` (or just its extracted effect map + transfer classification) and the **parsed operand expression(s)** on the `AssembledInstruction`/`InstructionLine` (per Q10 — retain the expression tree, not just the source string), plus the mnemonic for diagnostics. Additive — it does not change bytecode generation — but it touches the core instruction objects, which is the single most invasive change.
* **(B) A distinct analysis pass on source order.** *(M1, fully required at M5.)* Grows the engine from two passes to three (address assignment → flow analysis → bytecode). The new pass iterates the **source-ordered** line list (see the Tracking-pass anchor) and maintains counter state independent of the address counter. M0 establishes the source-order executable-node index it consumes.
* **(C) Control-flow graph + branch-target resolution.** *(M5.)* Net-new infrastructure: classify transfer instructions via `flow_transfer`, evaluate each branch's target operand expression to an address (depends on (A) retaining that expression), retain label identity where present, resolve it to the next executable CFG node, build edges, and run the worklist propagation. The assembler has nothing like this today. **Build this as an analysis-agnostic framework** — a CFG plus a worklist parameterized by a lattice and a per-instruction transfer function — with flow counters as its first client, not as a bespoke counter-walker. Doing so makes the related analyses below incremental clients rather than new infrastructure (see *Related Static Analyses*).
* **(D) Deliver tracker-resolved `COUNTER()`/`OFFSET()` values to operand evaluation.** *(M1/M2.)* These operators are position-dependent (the same `COUNTER(stack)` differs line to line), but the expression evaluator (`ExpressionNode.get_value()`) currently receives only `(label_scope, active_named_scopes, line_id)` — not the line's counter state (the instruction address is even available one level up in `parts.py` but dropped at the call). Preferred approach, preserving the *Static Analysis Only* guarantee: the tracking pass **pre-resolves each `COUNTER()`/`OFFSET()` occurrence to a literal keyed to its line and deposits it** (as a tagged constant or per-line annotation) for second-pass evaluation to read. Data flows one way (tracker → operand value), so analysis can never perturb addresses. The alternative — threading per-line counter state through every `get_value()` call site — is more invasive and weakens isolation.

### Note on macros
Macros influence counters only in aggregate (no own flow metadata; see *Macros Influence Counters Only in Aggregate*). Macro invocations expand into a `CompositeAssembledInstruction` exposing the constituent `AssembledInstruction`s, so the aggregate is computed by walking the expansion — but each constituent has the same config-retention gap as (A) (it must expose its own effect map and operand values). Aggregation therefore depends on (A) and is available as soon as the constituents' effects are (M1–M3); only constituents using *structural* operand-dependent effects defer to M7.

## Related Static Analyses (out of scope; design the framework to host them)
Building M5 produces three reusable assets: an execution-order **CFG**, a **dataflow propagation engine** over it, and a **config-metadata channel** describing per-instruction semantics. Flow counters are the first *client* of that framework, not the whole of it. The analyses below become incremental clients — a new lattice and transfer function — rather than new infrastructure, if change (C) is built generically. None are part of this feature; this is a forward-looking note so the framework is shaped to host them and so the project is understood as "static analysis for bytecode," of which flow counters are the opening move.

Because ISAs are user-defined, every analysis is **metadata-driven** — there is no hardwired CPU knowledge — so the practical ordering is by how much *new* ISA-config metadata each demands. Execution-dimension analyses (reuse the CFG):

* **Reachability / dead code** — metadata: none beyond `flow_transfer` (already added for M5). Flags instructions no path reaches and labels nothing targets; needs declared entry points (the `#entry` concept) to avoid false positives on interrupt vectors and jump tables.
* **Fall-through-into-data / missing return** — metadata: none beyond `flow_transfer`/`flow_terminal`. Catches a routine whose last path runs off the end into the next routine or into data — a close cousin of the exit-imbalance rule.
* **Indirect-target / jump-table validation** — metadata: an annotation giving an `indirect` jump its target set, which also restores reachability through computed jumps.
* **Register / flag liveness & def-use** — metadata: per-instruction def/use sets, the machine-checked analogue of the existing documentation-only `documentation.modifies` (exactly as `flow_effects` is its analogue for counters). Catches dead stores, use of an uninitialized register or flag, and registers clobbered across a call (caller-saved violations). High value, but the def/use metadata is genuine authoring burden — and it generalizes the cross-region call-verification idea in Open Question 6.
* **Value-range / constant propagation** — metadata: per-instruction value semantics (heaviest). Detects always-taken/never-taken branches and out-of-range computed immediates. The far end of the ambition curve; likely too ISA-specific to be worthwhile.

Layout-dimension checks (do **not** need the CFG; cheap, high-value, some partially existing):

* **Relative-branch range** — does a `relative_address` target fit the signed offset field? A classic assembler check, addresses only.
* **Immediate / operand-field overflow** — warn when a literal is silently masked to fit an operand's bit size (today some masking is silent).
* **Memory-zone access legality** — flag a write into a ROM-typed zone, or an access outside declared zones; reuses the existing memory-zone machinery.
* **Unreferenced labels / unused constants** — pure label-scope lint, no CFG.

Two precedents make this trajectory natural: `flow_effects` establishes "machine-checked per-instruction semantics declared in config," and the existing `documentation.modifies` / `flags` sections are the documentation-only seed of the def/use metadata a liveness pass would consume — the same promotion from documentation to checked data that motivated flow counters in the first place.

## Documentation & Tooling Impact (Collateral)
Beyond the assembler itself, this feature touches every surface that knows the language's vocabulary. The one-time pipeline work begins in **M1** and its per-milestone application follows the **collateral definition-of-done** (see *Implementation Phasing*); this section is the inventory.

**Editor extensions (generated):** the VS Code, Sublime Text, and Vim extension generators (`configgen/{vscode,sublime,vim}/`) build their grammars from the central keyword sets in `keywords.py` and their hover content from `docsgen/directive_docs.py` via `configgen/hover_docs.py`. Adding the new directives/operators to those registries propagates to all three editors; per-editor verification (Sublime hover plugin, Vim semantic/hover) is still required. Because extensions are generated per-ISA, flow-counter tokens are included **only when the source ISA enables the feature** — matching the enablement-gated keyword reservation (Open Question 1).

**Hover / directive documentation:** new entries in `PREPROCESSOR_DIRECTIVE_DOCS` (all eight directives) and `EXPRESSION_FUNCTION_DOCS` (`COUNTER`, `OFFSET`) in `docsgen/directive_docs.py`; `test/test_docsgen/test_directive_docs.py` enforces coverage.

**Release collateral:** `CHANGELOG.md` entries per milestone; the feature-introducing release version becomes the `min_version` floor for configs using the new keys; example programs under `examples/` (the milestone acceptance demos) and at least one example ISA config gaining a `flow_counters` section.

**Wiki:** the project wiki documents *shipped* behavior, so wiki updates are **ship-time work, scoped per milestone** — not to be written while this remains a draft (documenting an unparsed schema would mislead ISA authors). When a milestone lands, it touches two wiki pages:

* **`Instruction-Set-Configuration-File.md`** — a new `flow_counters` top-level section (counter classes: `source`, `operation`, `join`, `min_value`/`max_value`, `unknown_instructions`, `default_init`, `entry_modes`); the per-instruction delta field (the `source` target — `flow_effects.<class>` by default, or a custom field, or `documentation.cycles`), including the operand-expression and edge-dependent `{ taken, fall_through }` delta forms and per-`variants` overrides; and the `flow_terminal` / `flow_transfer` classification keys. Document `documentation.cycles` as a recognized instruction field. Cross-reference the existing `documentation.modifies` precedent.
* **`Assembly-Language-Syntax.md`** — the new preprocessor directives (`#track`, `#endtrack`, `#assert`, `#set`, `#entry`, `#suspend`, `#resume`, `#loop`) alongside the other `#`-directives, and the `COUNTER()` / `OFFSET()` operators in the numeric-expression operator table next to `BYTE0(..)` / `LSB(..)`.

Single-source-of-truth note: a counter's `source` field *is* the single source for its deltas. A cycle counter pointed at `documentation.cycles` reads the same per-instruction integer that documentation/timing output uses — one authored value, two consumers, no duplication and nothing to drift. (Document the new `source`/`operation` class keys, and `documentation.cycles` as a recognized instruction field, when the wiki is updated.)

## Worked Examples
Illustrative only — syntax is the strawman used throughout this draft. Comments show the tracked value after each line and the analyzer's verdict.

### ISA configuration (shared by the examples)
```yaml
flow_counters:
  stack:                          # data-stack depth, in bytes
    source: stack_effect          # per-instruction delta read from this field
    join: require-equal           # every path must agree; divergence is a bug
    min_value: 0
    entry_modes:
      called: { init: 2, exit: 0 }   # `call` leaves a 16-bit return address on entry
      jumped: { init: 0 }
  cycles:                         # worst-case timing
    source: documentation.cycles  # reuse the timing already documented per instruction
    join: interval                # paths may differ; track the [min,max] hull
  ct_cycles:                      # constant-time guard: SAME field, strict join
    source: documentation.cycles
    join: require-equal           # paths must take identical cycles, else timing leak

instructions:
  push: { stack_effect: 1,  documentation: { cycles: 11 } }
  pop:  { stack_effect: -1, documentation: { cycles: 10 } }
  ld:   { documentation: { cycles: 8 } }                      # no stack effect
  nop:  { documentation: { cycles: 4 } }
  add_sp: { stack_effect: -ARG(0), documentation: { cycles: 8 } }   # `add sp, N` frees N
  call: { stack_effect: 2,  flow_transfer: call,        documentation: { cycles: 17 } }
  ret:  { stack_effect: -2, flow_terminal: [stack],     documentation: { cycles: 10 } }
  jmp:  { flow_transfer: unconditional,                 documentation: { cycles: 10 } }
  jz:   { flow_transfer: conditional, documentation: { cycles: { taken: 12, fall_through: 7 } } }
  jnz:  { flow_transfer: conditional, documentation: { cycles: { taken: 12, fall_through: 7 } } }
```

### Example A — stack slot labels (issue #18; straight-line, M2)
```asm
#track stack                       ; region opens, stack = 0
build_record:
    push a                         ; stack 0 -> 1
.field_x = COUNTER(stack)          ; name this slot  (snapshot = 1)
    push b                         ; stack 1 -> 2
.field_y = COUNTER(stack)          ; snapshot = 2
    ld a, [sp + OFFSET(field_x)]   ; OFFSET = COUNTER(stack) - field_x = 2 - 1 = 1  -> [sp+1]
    pop b                          ; stack 2 -> 1
    pop a                          ; stack 1 -> 0
#endtrack stack                    ; exit check 0 == 0  ✓
```
The payoff: insert `push c` right after `field_y` and the `[sp + OFFSET(field_x)]` line is **untouched** — its offset recomputes from 1 to 2 automatically. That is exactly the manual bookkeeping issue #18 asked to eliminate.

### Example B — subroutine taking a stack argument (M3)
```asm
; multiply(n): caller pushes n, then `call`s; result returned in A
#track stack mode=called           ; init = 2 (return address), exit = 0
multiply:
.arg = 0                           ; caller's argument, baseline slot
    push b                         ; stack 2 -> 3
    ld a, [sp + OFFSET(arg)]       ; OFFSET = 3 - 0 = 3  -> reaches the argument past b + retaddr
    ; ... compute, result in A ...
    pop b                          ; stack 3 -> 2
    ret                            ; stack_effect -2: 2 -> 0  -> exit check 0 == 0  ✓
```

### Example C — push leak caught on one path (M5)
```asm
#track stack mode=called           ; init = 2 (return address), exit = 0
safe_divide:
    push b                         ; stack 2 -> 3
    cmp a, 0
    jz .by_zero                    ; conditional: both edges explored
    ; --- normal path ---
    pop b                          ; stack 3 -> 2
    ret                            ; flow_terminal: applies -2 (2 -> 0); exit check 0 == 0  ✓
.by_zero:
    ld a, 0xff
    ret                            ; flow_terminal: applies -2 (3 -> 1); exit check 1 != 0
                                   ; ERROR(flow): `push b` is never popped on the .by_zero path
```
Both `ret`s are `flow_terminal` instructions, not `#endtrack` directives: each ends the *path* reaching it and is exit-checked independently (after applying its own −2). No `#endtrack` is needed because every path terminates at a `ret`; the region is closed once all paths have.

### Example D — runtime-length loop, acknowledged (M5)
```asm
#track stack
push_string:                       ; HL -> NUL-terminated string of unknown length
.saved = COUNTER(stack)            ; depth before the variable region (= 0)
#suspend stack                     ; depth is now runtime-dependent; tracking pauses
.loop:
    ld a, [hl]
    cmp 0
    jz .done
    push a                         ; not tracked while suspended (count unknown)
    inc hl
    jmp .loop
.done:
    ; ... consumer pops exactly as many bytes as were pushed ...
#resume stack = .saved             ; programmer asserts we are back to the pre-loop depth (0)
#endtrack stack                    ; exit 0 == 0  ✓
```
Without the `#suspend`/`#resume`, `.loop` would be reached at `stack = 0` (fall-in) and `stack = 1` (back-edge) → join-mismatch error: the analyzer refuses to guess the loop count.

### Example E — worst-case timing with a bounded loop (M6 + M7)
```asm
#track cycles init=0               ; interval counter (join: interval)
delay:
#loop count=100                    ; the following loop body executes 100 times
.spin:
    nop                            ; cycles += 4
    dec a
    jnz .spin                      ; taken 12 / fall_through 7 (edge-keyed cost)
#assert COUNTER(cycles).max <= 1700  ; whole routine must fit the budget
#endtrack cycles
```
The interval counter accumulates `body × 100` (the `#loop` count makes it finite instead of widening to ∞), uses the *taken* edge cost inside the loop and the *fall_through* cost on exit, and the `#assert` fails if the computed worst case exceeds the budget.

### Example F — constant-time check catches a timing leak (M6)
```asm
#track ct_cycles init=0            ; join: require-equal — both paths must cost the same
ct_compare:
    cmp a, b
    jz .equal                      ; conditional
    ld a, 0                        ; unequal path:  ld(8)
    jmp .end                       ;               + jmp(10)  = 18 cycles
.equal:
    ld a, 1                        ; equal path:    ld(8)               =  8 cycles
.end:                              ; ERROR(flow): paths reach .end with ct_cycles 18 vs 8
                                   ;   -> timing leak; the `jmp` makes the unequal path slower
#endtrack ct_cycles
```
The fix is to balance the paths (e.g. structure both arms to identical cost); the same `require-equal` join that flags a stack imbalance flags a timing side-channel here — same machinery, opposite intent.

The label `.end` is the *site* of the error, not its cause: it is a **join** because two CFG edges arrive there — the fall-through from `ld a, 1` and the branch edge from `jmp .end` — carrying different `ct_cycles` values. The label is load-bearing only as the named target the `jmp` needs; the error itself is "two edges converge with disagreeing values." Tellingly, `.equal` is *also* a local label but is **not** a join: its only predecessor is the `jz` taken-edge (the preceding `jmp` is unconditional and does not fall through), so no check fires there. The label's *local* scope is irrelevant to the join check — locality only affects the separate mid-region external-entry warning.

### Example G — two independent counters at once (M4)
```asm
#track stack                       ; data-stack depth
#track cycles init=0               ; timing, simultaneously
isr:
    push a                         ; stack 0 -> 1 ; cycles += 11
    push b                         ; stack 1 -> 2 ; cycles += 11
    ld a, [hl]                     ;             ; cycles += 8   (no stack effect)
    pop b                          ; stack 2 -> 1 ; cycles += 10
    pop a                          ; stack 1 -> 0 ; cycles += 10
#assert COUNTER(cycles).max <= 60  ; ISR latency budget
#endtrack stack                    ; exit 0 == 0  ✓
#endtrack cycles
```
Each instruction updates every active counter from its own `source` field; the two counters are checked independently against their own rules (`stack` balance, `cycles` budget).

## Open Questions
1. **Expression operator names:** *resolved.* `COUNTER(..)` and `OFFSET(..)` are the operators (sigil prefixes are non-viable — `^` is bitwise XOR, `$` hex, `%` binary, `@` operand labels, `#` preprocessor), following the `BYTE0(..)`/`LSB(..)` function-style precedent. They are reserved words **only in ISAs that enable the feature** (declare a `flow_counters` section), so source for non-feature ISAs is unaffected and collision risk falls only on authors who opt in and control their own namespace.
2. **Slot typing:** *resolved.* Slot snapshots become constants in the existing label scope with an optional origin tag added to `LabelScope.LabelInfo` (backward-compatible, since callers read `.value`). The dead-slot rule and `OFFSET()` both consult that tag (which counter + snapshot value). Position-dependent bare `COUNTER()`/`OFFSET()` values are delivered per Q9.
3. **Region/directive interaction:** *resolved.* A `.org` / memory-zone change while a region is open **auto-closes the region** (applying its exit-value check) and emits a **warning** — escalatable to a hard error via `-W` (warnings-as-errors). This avoids silently spanning a relocation while not forcing a hard error on every relocate. (Labels inside a region continue the region, with label-scope-aware entry-point warnings.)
4. **Conditional terminals:** *resolved.* A conditional `ret` (an instruction carrying both `flow_terminal` and `flow_transfer: conditional`) ends one path but not the fall-through. M5 join analysis handles this naturally as a two-edge node. Earlier milestones (M1–M4, no CFG) treat a conditional terminal as **non-terminating, with a warning** that its terminal effect is deferred until path analysis — conservative and honest, never silently dropping the fall-through path.
5. **Counter name namespace & scoping:** *resolved — counters get label-style scope, two levels (global + file).* Counter names are their **own namespace, separate from labels** (a counter `stack` and a label `stack` never collide — counter names appear only in `COUNTER()`/`OFFSET()` argument position and the flow directives). The name carries a **scope prefix mirroring labels**, and the prefix sets the boundary the tracking region is confined to:
   * **Global** (no prefix, e.g. `#track stack`): program-wide; the region **may span `#include`** (inline included code is tracked, and included code referencing `COUNTER(stack)` binds to the same counter).
   * **File** (`_` prefix, e.g. `#track _stack`): confined to the file; **does not project into `#include`**, so an included library's `_stack` is a distinct counter from the caller's — collision-free, exactly like file-scope labels.
   * *Local* (`.`) and *named* (`#create-scope`-style) scopes are **not** adopted: the tracking region itself already provides local-like lifetime, and `as=` plus the global/file split cover the rest. (Named counter scopes remain a possible future addition only if cross-file counter sharing becomes a real need.)
   The prefix attaches to the effective instance name (the class name, or the `as=` name — `#track cycles as=_sync` is a file-scoped instance `_sync`). A region must open and close within its scope's boundary; if execution would carry an open file-scoped region across an `#include` (or any boundary), that is the auto-close-with-warning of Q3, never a silent untracked gap. Non-overlapping regions reuse a name freely; concurrent instances need distinct `as=` names.
6. **Cross-region call verification:** *resolved — staged.* M5/M6 do not inline callees. Stack-style counters use the existing immediately resolvable call/terminal convention; every other class carries an unresolved `CallEffect(callee, class)` summary, which prevents a false precise operand value or timing claim after the call. The later post-M7 interprocedural phase resolves those summaries by recording each region's verified entry/exit effect and declared argument slots per entry-point label, then checking call sites against the named callee's convention.
7. **`#include` interaction:** *resolved by counter scope (Q5).* `#include` is textually inline and a counter tracks execution (not layout — distinct from memzone/named-scope, which are layout/visibility context and correctly reset per-file). So whether a region spans an `#include` is the programmer's choice, expressed by scope: a **global** counter's region spans the include (included instructions tracked, name shared); a **file** (`_`) counter's region is confined to the file and may not cross the include — if execution would carry an open file-scoped region into an `#include`, it auto-closes with a warning (Q3). This gives both the inline-fragment case (global) and library isolation (file) without a special-case `#include` rule.
8. **Return-address size sugar / entry mode names:** *resolved.* The return-address size is stated once in the ISA configuration (`entry_modes.<mode>.init`) and source names the convention (`#track stack mode=called`). Mode names stay **fully author-defined** (flexibility for unusual ISAs), but documentation **recommends conventional names** — `called`, `jumped`, `interrupt` — so tooling and cross-ISA readers see consistency. No reservation or enforcement.
9. **`COUNTER()`/`OFFSET()` value delivery:** *resolved.* The tracking pass pre-resolves each occurrence to a per-line literal that second-pass evaluation reads, keeping data flow one-way (tracker → value) and isolation intact, so analysis can never perturb addresses. (Architecture change D.)
10. **Operand-expression retention:** *resolved.* The **parsed operand expression is retained on the `InstructionLine`** (architecture change A), so the M5 CFG evaluates branch targets directly — no re-parsing at analysis time and no divergence risk. Costs some memory per line, but is robust and handles complex target expressions. (Re-parsing from the retained operand string and storing only the resolved address were the rejected alternatives.)
