# Flow Counters (Assembly-Time Tracked Counters)

Status: **DRAFT — M0–M5.1 are the committed normative scope; M6–M7 are provisional design sketches**

Addresses GitHub issue [#18 — Stack Position Labels](https://github.com/michaelkamprath/bespokeasm/issues/18).

## Overview
The original request in issue #18 is for symbolic stack-slot labels: give a value pushed onto the stack a name, and let the assembler compute its current stack-pointer-relative offset at any later point in the code. That only works if the assembler tracks how each instruction moves the stack pointer.

The generalized mechanism is the **flow counter**: a named integer value that the assembler advances line-by-line through the source code according to per-instruction effects declared in the ISA configuration. Flow counters:

* exist only at assembly time and add no instructions or layout footprint — metadata, directives, and counter-coordinate declarations are emission-inert, while `COUNTER()` and counter-coordinate references emit exactly the same operand/data values as the equivalent hand-written numeric literals (see *Guiding Requirement* below),
* are usable in operand expressions through current values and explicitly declared counter-coordinate symbols,
* are checked for consistency, with ambiguous or out-of-bounds usage reported as errors,
* are instances of **counter classes** declared in the ISA configuration — instructions declare effects against classes, source code instantiates counters, and any number of counters may be active simultaneously, each tracked independently,
* verify programs by default; `--no-flow-checks` suppresses optional flow
  verification and listing annotations, while emitted `COUNTER()` and
  counter-coordinate values still trigger the minimum analysis needed to resolve them.

Stack depth is the flagship use case, but the mechanism is deliberately general. Because BespokeASM ISAs are user-defined, what a counter *means* is entirely the configuration author's choice — the assembler only does bookkeeping and consistency checking.

## Motivating Use Cases
1. **Stack slot labels** (issue #18): name pushed values; compute `sp`-relative offsets automatically so inserting a new `push` does not require manually updating every offset below it.
2. **Hardware call-stack depth limits**: many small CPUs have tiny fixed call stacks (e.g., PIC's 8-level hardware stack). A counter where `call` is +1 and `ret` is −1 with a configured maximum turns a silent runtime crash into an assembly error.
3. **Two-stack machines**: Forth-style CPUs track the data stack and return stack independently — two simultaneous counters.
4. **Cycle counting**: each instruction declares its cycle cost as a delta. For a scalar `require-equal` cycle counter, `.start := COORDINATE(cycles, 0)` followed later by a bare `.start` reference gives exact elapsed cycles. An `interval` counter has no single coordinate and therefore cannot use `:=` declarations or coordinate references; it instead opens a measurement window at zero and checks `COUNTER(cycles).min` / `.max` before closing it. The interval form yields **worst-case execution timing** across branches — assert that any path through a region fits a cycle budget. Cycle counting stresses two design features not needed by stack-style counters: per-class **join semantics** and **edge-dependent deltas** (see those sections).
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
| an address label (`foo:`) snapshots its current value | a counter-coordinate declaration (`.var := COORDINATE(stack, 0)`) names a position relative to its current value |
| the snapshot feeds address operand values | the snapshot feeds coordinate-reference operand values |
| bounded by memory zone start/end | bounded by `min_value` / `max_value` |
| resolved in the first address-assignment pass | resolved in a separate post-layout analysis pass, using source and execution order |

In other words, the address counter is essentially one hardwired flow counter: a single always-on instance whose per-line delta happens to be forced by emission rather than declared in configuration, re-anchored by `.org`, and snapshotted by labels. **The implementation should reuse the existing line objects, source-order relationships, and symbol-scope machinery while keeping flow evaluation in its own post-layout pass** — a counter-coordinate symbol is, mechanically, an address-label-like value whose source is a counter instead of the address counter.

The generalization is not total, and the one axis where it breaks is the most important design fact about the feature:

* **The address counter lives in the *layout* dimension; flow counters live in the *execution* dimension.** The address counter tracks where bytes land in memory, and physical layout is linear and monotonic — a given source position has exactly one address by construction, so the address counter never branches and never has to ask whether its value is consistent. Flow counters track quantities as the CPU *executes*, where the same instruction may be reached by multiple control-flow paths. That is the entire reason the join-consistency and push-leak analysis (milestone M5) exists; the address counter has no analogue because addresses have no "paths."
* **Direction:** the address counter is monotonic (only `.org` moves it backward, and that is a re-anchor, not a delta); flow counters are bidirectional by nature.
* **Emission vs. execution order:** the address counter advances in emission order; a flow counter advances in execution order. Normally the same source walk, but `#mute` and conditional assembly are exactly where the two diverge — which is why tracking follows compiled code, not emitted bytes.

So flow counters generalize the *counter-with-snapshots mechanism* the assembler already uses for addresses, and add one dimension — control flow — that the address counter never had to model. The address counter is the degenerate case: single instance, monotonic, layout-space, no branches.

### How Much Should They Share?
The parallel above is a guide to *reuse*, not a mandate to *unify*. The intended relationship:

* **Share the paradigm.** The two should feel like the same idea: a counter advanced during an assembly pass, re-anchored by a directive, snapshotted into a named compile-time value. Directive and expression design should deliberately echo the address-counter vocabulary (`#track`/`init=` mirroring `.org`/`origin`; counter-coordinate symbols mirroring address labels) so the feature reads as an extension of what users already know.
* **Share one primitive: the symbol-scope value sink.** The deepest commonality is not "two counters" but that both produce *named values captured at a source position* into the symbol-scope system. The address pass already does this for `current_address`; the later flow-analysis pass becomes a **second producer** into the same scoped-symbol machinery. A `:=` declaration creates an address-label-like value whose source and counter identity are recorded explicitly. Reuse flows in one direction: flow counters borrow the existing scoped-symbol primitives; the address counter is **not** re-expressed on top of a flow-counter engine.
* **Do not unify them under a common Counter base.** A shared base class would be lopsided — the address counter carries memory zones, overlap detection, `.fill`/`.align`, and monotonicity that no flow counter uses, while flow counters carry signed deltas, bounds, suspend/resume, and control-flow analysis that the address counter never uses. The shared bookkeeping is a small fraction of either; a common base would mostly be two disjoint sets of special cases.
* **Isolation is a hard constraint, not a preference.** The *Static Analysis Only* guarantee forbids flow-counter logic from perturbing address assignment or byte code. Sharing mutable state or a common advance path between the two would create exactly the channel through which an analysis bug could shift an address. Keeping the implementations separate — touching only the scoped-symbol primitive — is what makes the byte-identical guarantee structurally enforceable rather than merely intended. The address counter is also load-bearing and predates this feature; there is no functional upside to refactoring it.

### The Symmetric Case: Layout Counters (out of scope, noted for coherence)
The layout/execution duality is symmetric, and recognizing this keeps the feature boundary sharp. The address counter is the first member of a **layout-counter family** (monotonic, single-valued per position, snapshot = physical location, *produces real addresses that byte code depends on*); flow counters are the **execution-counter family** (bidirectional, multi-path, snapshot = a convenience value, *never owns byte code*). They share the paradigm — counter, re-anchor, snapshot-into-a-label — but sit in different dimensions and obey opposite rules about byte code.

The motivating example is a **microcode compiler**, where an instruction's control-store entry begins at a base sub-address and each microstep occupies the next word:

* **Labeling microcode steps relative to the instruction start is a *layout* concern, not a flow counter.** A step label is the target of a microcode branch, so it must equal the physical control-store sub-address where the step is stored — single-valued, fixed by layout, and required to be a real address other byte code depends on. Modeling it with a flow counter would be the wrong dimension: a flow-counter snapshot only equals the sub-address if it advances in lockstep with the address counter, at which point it is merely `current_address − instruction_base` (a derived view of the address counter), and it would forfeit the layout guarantees (overlap detection, bounds) that make branch targets correct by construction. This belongs to a *sibling* generalization — a sub-address counter that resets per instruction and is bounded by the step-field width — which would live on the addressing side, **not** in this feature. (It can be approximated today with `.org (opcode << step_bits)` per instruction plus ordinary address labels and subtraction, with `word_size` set to the microcode word width.)
* **Flow counters fit microcode only for *execution* consistency across microcode branches:** verifying a T-state / microstep budget is met on every path through an instruction's microcode, or that a control signal asserted on one microcode path is deasserted before the instruction ends. These are bidirectional, multi-path, byte-code-neutral checks — squarely the flow-counter family.

The lesson for scope: when a counter's snapshot must *be* an address that byte code depends on, it is layout-family and does not belong here; when the snapshot is a convenience value and the interesting question is consistency across execution paths, it is a flow counter.

## Requirements

### Guiding Requirement: Static Analysis Only
Flow counters are an assembly-time analysis and constant-computation feature. **Flow metadata, directives, and `:=` declarations must not change layout or emission; analysis-derived values must be byte-identical to replacing them with their resolved numeric literals.** Apart from those explicitly requested literal values, the feature's only observable effects are diagnostics (and assembly failure when those diagnostics are errors). Specifically:

* Flow counter directives (`#track`, `#endtrack`, `#set`, `#entry`, `#suspend`, `#resume`, `#loop`) and the general, flow-aware `#assert` directive emit no byte code and occupy no address space, like all other preprocessor directives.
* Counter-coordinate declarations (`name := <counter-coordinate expression>`) emit no byte code and occupy no address space. They are distinct from BespokeASM's ordinary `=` / `EQU` constant assignments.
* The analysis never alters code generation: no instruction insertion, removal, reordering, padding, or operand rewriting based on analysis results. Tracking state has no influence on instruction encoding, address assignment, or memory zone behavior.
* `COUNTER()` and counter-coordinate references resolve to compile-time numeric values determined solely by the declared instruction effects and the source's structure — the emitted byte code is bit-identical to what hand-writing the resolved values would produce. They are conveniences for computing values the programmer would otherwise compute (and today does compute) by hand.
* Equivalence invariant, suitable for a conformance test: take any program that assembles cleanly with flow counters in use; strip every flow counter directive and `:=` declaration, then replace every emitted `COUNTER()` reference and every counter-coordinate reference with its resolved numeric value. The assembled output must be byte-identical.
* Adding `flow_counters` and per-instruction effect metadata to an ISA configuration must not change the assembly of any existing source file that does not use the feature.
* `__FLOW_COUNTERS_AVAILABLE__` is an ordinary preprocessor capability symbol, not an analysis-derived value. Source that explicitly selects code with this symbol is using the feature-detection interface and may intentionally emit different code for flow-capable and non-flow ISAs. Its value is fixed from ISA configuration before conditional preprocessing and never changes with `--flow-checks` / `--no-flow-checks`, so the verification switch cannot alter source selection or emitted bytecode.

### Flow-Check Control (Command Line)
The `compile` command provides a Click-style dual boolean option:

```text
--flow-checks / --no-flow-checks
```

Flow checks are **enabled by default**. The equivalent single-letter forms are
`-a` and `-A`. Supplying `--flow-checks` selects the default explicitly;
`--no-flow-checks` suppresses optional flow verification and pretty-listing
annotations. It does not disable resolution of flow values required by emitted
bytecode.

With `--no-flow-checks`:

* the ISA's flow metadata is still parsed and validated. A switch that affects
  source verification cannot make an invalid ISA configuration valid;
* malformed flow directives, invalid directive values, unsupported parameters,
  and uses against an ISA without `flow_counters` remain errors;
* flow-dependent `#assert` checks, instance/class bounds checks, exit-balance
  checks, external-entry warnings, and other verification-only diagnostics are
  suppressed. General `#assert` directives remain active;
* if no emitted value depends on flow state, the graph propagation pass is not
  run. Flow-only annotations remain zero-width and emission-inert;
* if an instruction operand or fixed-size data value contains `COUNTER()` or
  a reference to a declared counter coordinate, the graph pass runs
  automatically and pre-resolves those values.
  Structural errors that make a requested value unsafe or ambiguous still
  fail; the assembler never substitutes zero, stale state, or a guess;
* rich per-instruction analysis records remain available for a flow-capable
  ISA because the need for value resolution is discovered from the compiled
  source. ISAs without `flow_counters` retain no such records;
* ordinary address labels and `=` / `EQU` constants are unchanged;
* `__FLOW_COUNTERS_AVAILABLE__` retains its ISA-capability value and is
  independent of this switch;
* listing pretty-print output omits the flow column entirely.

Thus stack-position labels remain convenient in normal source regardless of
whether verification output is wanted: `-A` means “resolve what the emitted
program needs, but do not audit or annotate the rest.”

### Feature Enablement (ISA Configuration)
Flow counters are **off unless the instruction set explicitly enables them**,
independent of the flow-check switch:

* The presence of a `flow_counters` section in the ISA configuration *is* the explicit enablement, and the counter classes it declares *are* the enabled types — an ISA enables exactly the counter types it lists, nothing more. There is no implicit or global "all counters" set to enable, because counter classes are author-defined; the section is the enumeration.
* An ISA with **no `flow_counters` section** has the feature disabled entirely. It assembles exactly as today, and none of the metadata-completeness or soundness checks ever run.
* Flow-specific directives and operators join the assembler's reserved namespace only when the selected ISA has a `flow_counters` section. A non-flow ISA may continue to use `track`, `endtrack`, `set`, `suspend`, `resume`, `COUNTER` or `COORDINATE` as ordinary symbols or configured mnemonics. `assert` is a base preprocessor keyword in every ISA because general `#assert` does not require flow analysis. The capability probe `__FLOW_COUNTERS_AVAILABLE__` is the deliberate exception: it is a built-in constant, reserved and highlighted for every ISA so source can test whether the gated syntax is available. Generated editor extensions follow the same distinction.
* Using any flow-counter construct (`#track` and the other flow directives, a flow-dependent `#assert`, `:= COORDINATE()`, or `COUNTER()`) in source compiled against an ISA that does not enable the feature is an **error** — "this instruction set does not enable flow counters" — and that error fires **only because the construct was used**. A general `#assert` remains valid without flow counters.
* `--no-flow-checks` does not waive capability gating: flow syntax still
  requires an ISA with a `flow_counters` section.
* Likewise, every requirement in *Required Metadata: Fail Loud, Never Silently Inert* is usage-gated: a metadata gap for counter class `X` is an error only when source actually tracks or references `X`. An enabled-but-unused class imposes no obligations and raises no diagnostics.

The always-defined numeric preprocessor symbol `__FLOW_COUNTERS_AVAILABLE__` exposes this ISA capability to ordinary conditional compilation: it is `1` exactly when the selected ISA configuration contains a `flow_counters` section and `0` otherwise. Source uses it with `#if` / `#elif`, not `#ifdef`, because the symbol exists in both cases. It supports one source tree shared by flow-aware and legacy/non-flow ISA configurations:

```asm
#if __FLOW_COUNTERS_AVAILABLE__
#track stack mode=called
#endif

routine:
    ; routine body

#if __FLOW_COUNTERS_AVAILABLE__
#endtrack stack
#endif
```

The symbol reports configuration capability only. It remains `1` for a
flow-capable ISA compiled with `--no-flow-checks`. This deliberately prevents
the verification switch from changing conditional compilation. `COUNTER()`,
coordinates, and all other analysis results remain forbidden in
`#if` / `#elif`; a bare coordinate name there is just an undefined
preprocessor identifier, exactly like any other label.

This keeps the *Static Analysis Only* guarantee intact from both directions: enabling the feature on an ISA changes nothing for source that does not use it, and source cannot accidentally invoke it against an ISA that did not opt in.

### Counter Classes (ISA Configuration)
The configuration declares counter **classes**; source code creates counter **instances** of those classes with `#track`. This split separates two concerns: the ISA author knows what instructions *do* (a `push` deepens any stack-depth tracker by 1), while only the programmer knows how many trackers they want running and over what code (one stack tracker; or two overlapping cycle-measurement windows). An instruction's declared effect applies to **every active instance** of the affected class.

In the common case the distinction is invisible: `#track stack` creates an instance whose name defaults to its class name, and everything reads as if "stack" were simply a counter.

#### There Is No Fixed Taxonomy of Counter "Types"
A counter has no built-in kind. Its behavior is **emergent from the combination of two things**: the class-declaration knobs (`join`, `min_value`/`max_value`, `coordinate_offsets`, `allow_zero_offset`, `entry_modes`, `exit_policy`, `unknown_instructions`, `invalidate_on_write`) and how each instruction declares it interacts with the class (`flow_effects`, `flow_terminal`, `flow_transfer`, `flow_call_effects`, `flow_invalidates`, `flow_write_operands`). "Stack depth," "cycle counter," "constant-time counter," and "hardware-call-stack limit" are *recognizable configurations* of those knobs, not enumerated types the assembler knows about. The use cases listed earlier are therefore presets/patterns, not a closed set — an ISA author can compose new ones (e.g., a bank-nesting balance counter) purely by choosing knobs and per-instruction effects, with no assembler change. Wherever this document says "a cycle counter" or "a stack counter," read it as shorthand for "a counter configured this way," not a distinct mechanism.

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
    invalidate_on_write: [0xffff]  # memory-mapped SP writes make depth unknown
    coordinate_offsets: positive  # declarations may name current+N positions
    unknown_instructions: error   # require an explicit stack_effect, including zero
    default_init: 0           # init value when #track gives neither init= nor mode=
    exit_policy: balanced     # default: implicit exit value equals initial value
    entry_modes:              # named entry conventions, usable as #track mode=<name>
      called:                 # routine-owned stack movement starts balanced
        init: 0
        exit: 0
      jumped:                 # entered via `jmp` or fall-through
        init: 0
      interrupt:              # ISR-owned stack movement also starts balanced
        init: 0
        exit: 0
  cycles:                     # a worst-case-timing counter: paths may differ, track the hull
    source: documentation.cycles  # reuse the per-instruction timing already in documentation
    operation: add
    join: interval
    unknown_instructions: error
    exit_policy: none         # assertions/bounds define the contract; closing alone does not
  ct_cycles:                  # a constant-time counter: paths MUST agree
    source: documentation.cycles  # same source field, different join policy
    join: require-equal
    unknown_instructions: error
    exit_policy: none
```

The section is a dictionary keyed by class name, matching the `operand_sets`/`instructions` convention. The `stack` class above reads each instruction's delta from a purpose-defined `stack_effect` field; the `cycles` class reads the per-instruction timing straight out of `documentation.cycles`, so the cycle count is authored once and serves both documentation and the counter.

| Option Key | Value Type | Description |
|:-:|:-:|:--|
| `documentation` | dictionary | _(Optional)_ `title` and `description`, per the documentation convention used by other config entities (and available to editor hover tooling the same way). Consumed by `bespokeasm docs` (M5.1) as the class's heading and prose in the generated Flow Counters section; absence falls back to the class name silently, while a non-dict value is a config-load error. |
| `source` | string | _(Optional)_ Dotted path into each instruction's configuration giving this counter's per-instruction delta — e.g., `documentation.cycles`, or a top-level instruction key like `stack_effect`. Lets a counter **reuse an existing integer field** (single source of truth) or bind to a field defined just for it. Defaults to `flow_effects.<class-name>` (the conventional per-instruction map) when omitted. Multiple classes may read the same field. |
| `operation` | string | _(Optional)_ How each instruction's source value combines into the counter. `add` — signed accumulation — is the default and the primary operation; the field is reserved for future combinators. |
| `join` | string | _(Optional)_ How values from multiple control-flow paths are reconciled at a join (committed `require-equal` path analysis in M5; provisional `interval` analysis in M6). `require-equal` (default): paths must carry the same value or a join-mismatch error is raised — correct for stack depth, hardware-stack limits, and constant-time checks. `interval`: the value becomes a `[min,max]` hull unioned across paths, never an error at the join — correct for worst-case timing and other budgets where paths legitimately differ. An `interval`-class counter has no single scalar value, so bare `COUNTER(cycles)` and coordinate references are invalid as operand values; its bounds are read only through `COUNTER(cycles).min` / `.max` in a flow assertion. |
| `min_value` | integer | Optional lower bound. Tracking below this value is an error. A `#track` instance may tighten (never loosen) class bounds with its `min=`/`max=` parameters — the per-program complement for machines whose real limit depends on the memory map rather than the hardware. |
| `max_value` | integer | Optional upper bound. Tracking above this value is an error. |
| `coordinate_offsets` | string | _(Optional)_ Which nonzero signed offsets `COORDINATE(counter, offset)` may name relative to the counter's current physical reference: `positive` permits positive offsets, `negative` permits negative offsets, and `both` permits either sign. Defaults to `both`. This lets an ISA reject physically meaningless addresses such as `sp-5` on a descending stack whose live memory is addressed at `sp+N`. Zero is controlled independently by `allow_zero_offset`. |
| `allow_zero_offset` | boolean | _(Optional)_ Whether `COORDINATE(counter, 0)` and a previously declared coordinate currently resolving to offset zero are valid. Defaults to `true`. Set it to `false` when the counter points immediately outside the live region, as with an ISA where `sp+1` is the first valid stack position. |
| `unknown_instructions` | string | Behavior when an instruction with no declared effect for this class appears inside an active tracking region: `ignore`, `warn`, or `error`. Default `warn`. |
| `invalidate_on_write` | list of integers | _(Optional)_ Memory addresses whose contents anchor this counter, such as a memory-mapped stack-pointer register. When an instruction's configured `flow_write_operands` may write one of these addresses, every active instance of the class becomes indeterminate, its coordinates are permanently invalidated, and precise tracking requires `#resume`. Values must be unique addresses within the ISA's configured address width. |
| `default_init` | integer | _(Optional)_ Initial value used when `#track` provides neither `init=` nor `mode=`. Defaults to 0. |
| `exit_policy` | string | _(Optional)_ Default exit contract when neither an entry mode nor `#track` supplies `exit=`. `balanced` (default) sets the expected exit value equal to the initial value. `none` gives the region no implicit equality check; bounds and explicit `#assert` directives still apply, and an explicit `exit=` creates an exact exit contract. `none` is appropriate for accumulating measurement windows such as cycle counters. |
| `entry_modes` | dictionary | _(Optional)_ Named entry conventions. Each key is an author-defined mode name usable in source as `#track ... mode=<name>`; each value is a dictionary with `init` (required), `exit` (optional), and `description` (optional; consumed by `bespokeasm docs` in the M5.1 entry-modes table). If `exit` is absent, the class's `exit_policy` supplies the default (`init` for `balanced`, no implicit contract for `none`). Modes describe the counter state owned by that routine or region; caller/control-flow state outside that ownership boundary—such as a return address later removed by a pre-effect terminal—is not folded into `init`. |

These are class-level properties, inherited by every instance.

The whole feature is opt-in by the presence of this section (see *Feature Enablement* above): configurations without a `flow_counters` section have it disabled and behave exactly as today.

### Instruction Effects (ISA Configuration)
An instruction's effect on a counter is its **delta value, read from the field the counter class names in `source`** (defaulting to `flow_effects.<class>`), combined per the class's `operation`. Separately, two classification keys — `flow_terminal` and `flow_transfer` — describe path termination and control flow; these are not deltas and are always their own keys.

```yaml
instructions:
  push:
    stack_effect: 1           # read by the `stack` class (source: stack_effect)
    flow_transfer: none
    documentation:
      cycles: 11              # read by the `cycles`/`ct_cycles` classes (source: documentation.cycles)
  pop:
    stack_effect: -1
    flow_transfer: none
    documentation:
      cycles: 10
  ret:
    stack_effect: -2          # physical return-address pull
    documentation:
      cycles: 10
    flow_terminal:
      stack: before_effect    # reconcile routine-owned stack movement first
    flow_transfer: return     # no executable successor
  jmp:
    stack_effect: 0
    documentation: { cycles: 8 }
    flow_transfer: unconditional
    flow_target_operand: 0
  jz:
    stack_effect: 0
    documentation: { cycles: { taken: 12, fall_through: 7 } }
    flow_transfer: conditional
    flow_target_operand: 0
  call:
    stack_effect: 2
    documentation: { cycles: 17 }
    flow_transfer: call
    flow_target_operand: 0
    flow_call_effects: { stack: 0 }  # declared caller-visible net effect
  jmp_hl:                     # computed/indirect jump
    stack_effect: 0
    flow_transfer: indirect
  mov_reg:
    flow_effects: { scratch: 1 }   # default source field, for a class that omits `source`
    flow_transfer: none
  store_immediate:
    stack_effect: 0
    flow_transfer: none
    flow_write_operands: [1]  # zero-based source operand containing write address
  replace_stack_pointer:
    flow_invalidates: [stack]  # SP is replaced rather than adjusted
    flow_transfer: none
```

The delta read from `source` is an integer in the common case, but may also be an operand expression or an edge-map (see *Operand-Dependent Effects* and *Edge-Dependent Deltas*); `operation` governs how it accumulates regardless of form. A counter reading `documentation.cycles` simply finds an integer there. `flow_terminal`/`flow_transfer` are independent of `source` and apply to whichever classes they name (terminal) or to the CFG (transfer).

#### Counter-Anchor Invalidation

Some architectures expose state that anchors a counter through a memory-mapped address. A Minimal 64x4 stack pointer, for example, is stored at `0xffff`; `mib 0xfe,0xffff` replaces the physical stack anchor rather than applying a relative push/pop delta. The counter class declares such addresses with `invalidate_on_write`, while each real instruction that writes memory declares the zero-based source operands containing its possible write targets with `flow_write_operands`.

For a compile-time target, only an address equal to a watched address invalidates the counter. Watch matching is exact-address: a multi-word write that begins below a watched address (e.g., a 16-bit write to `0xfffe` that also covers `0xffff`) is not detected — declare such writer instructions with `flow_invalidates`, or handle the span with `#suspend`/`#resume`. A runtime or otherwise unresolved write target is conservatively treated as possibly aliasing every watched address. A match puts the counter into the same indeterminate state as `#suspend`, permanently invalidates its existing coordinates, and renders `?` as the outgoing listing value. A watched write encountered during an explicit `#suspend` span still permanently invalidates the counter's existing coordinates. `COUNTER()`, coordinate references, coordinate declarations, assertions, and terminals remain unavailable until `#resume <counter> = <known value>` explicitly establishes the new anchor. Macro definitions may not declare instruction flow metadata; this behavior composes naturally through macros because analysis consumes each expanded real instruction and its `flow_write_operands`.

An instruction may instead replace a counter anchor directly, without writing
a memory-mapped address. For example, Intel 8085 `LXI SP, value` and `SPHL`
replace the stack-pointer register wholesale. Such an instruction declares
`flow_invalidates: [stack]`, a list of counter classes whose active instances
unconditionally become indeterminate after the instruction. This uses the
same listing, coordinate invalidation, and `#resume` rules as watched-write
invalidation. The metadata belongs to the real instruction or selected
variant, never to a macro; a macro inherits it from its expansion.

> **Modeling note:** physical `call`/`ret` stack deltas remain truthful instruction metadata,
> but a callee's stack counter normally measures only movement the callee owns. A return
> instruction therefore uses `flow_terminal.stack: before_effect`: the callee must reconcile
> its local movement to the exit value before the instruction removes caller/control-flow
> state such as a return address. The terminal then ends that counter's path, so its physical
> stack delta is not propagated or bounds-checked within the ended region. Caller-visible
> behavior remains expressed by `flow_call_effects`, while `COORDINATE(stack, N)` directly
> records the physical `sp+N` location of caller-owned parameters.

1. **Delta** — each counter class reads its per-instruction delta from the field named by its `source` (default `flow_effects.<class>`), applied to *every active instance* of that class when the instruction is encountered. `flow_effects` is thus the *default* source field — a map of class → delta — but a class may instead point `source` at any integer field (e.g., `documentation.cycles`) to reuse existing data. A delta may be a constant integer or, optionally, an operand expression or edge-map (see *Operand-Dependent Effects* and *Edge-Dependent Deltas*).
2. **`flow_terminal`** — dictionary of counter class → reconciliation order for which this instruction terminates the reaching execution path. Each value is required to be `before_effect` or `after_effect`. `before_effect` checks the incoming value against the exit contract and then ends that counter's path without applying its delta inside the region. This is the normal stack policy for an instruction that returns control to its caller by restoring an execution address saved on the stack: the instruction's physical stack effect consumes caller-owned control-flow state rather than routine-owned stack content. `after_effect` applies the class's delta, bounds, and coordinate invalidation first, then checks the resulting value; it is available for counters whose terminal instruction effect belongs inside the region's contract. The choice is per class, so the same instruction can reconcile `stack` before its stack effect while reconciling `cycles` after its cycle cost. A terminal ends the path for every active instance of its mapped class but does not end lexical extent. An exact exit check is applied only when an instance has an exit contract. **Every live counter must have a way across the region boundary the return creates** (clarified 2026-07): a return has no fall-through successor, so a live instance of an *unmapped* class reaching the terminal is an error — the same rule as a bare return with no terminal — and must either be mapped on the instruction (use `after_effect` when the return's own cost belongs in the counter, e.g. a cycles counter counting the return) or be closed with `#endtrack` before it. The unmapped counter is *unaffected by the reconciliation* in the sense that no exit contract of the mapped class applies to it; it does not silently absorb the instruction's effect and continue into unreachable code.
3. **`flow_transfer`** — exhaustively classifies instruction control flow so the consistency analysis (see below) knows where execution can flow. Every selected instruction variant encountered while any counter is actively tracked must declare one of these values; ordinary instructions explicitly declare `none`. This completeness rule is usage-gated — an ISA/source combination that never uses flow counters is unaffected:
   * `none` — ordinary execution proceeds to the physical fall-through successor.
   * `conditional` — execution may continue at the branch target *or* fall through.
   * `unconditional` — execution continues only at the branch target; the following line is not a fall-through successor.
   * `call` — execution transfers to a named callee and returns to the fall-through successor. A direct call may supply a caller-visible per-class net effect through `flow_call_effects`; without a usable declared summary, the state after the call remains an unresolved `CallEffect` (see *Path Analysis*). The callee need not be in the assembled program: a target address holding no program content at all is an **external callee** (a ROM routine named by a predefined constant, for example) whose body is not the analyzer's to verify — the declared summary governs, consistent with its taken-on-faith contract. A call target that lands on emitted *data* remains an error. Known permissive blind spot (recorded 2026-08): program content is keyed by instruction *start* addresses, so a hard-coded target landing *mid-instruction* finds no node and is silently treated as external rather than flagged; tightening this requires a per-address instruction-span map and is a candidate M6/M7 hardening item.
   * `return` — execution returns to a caller and has no intraprocedural successor. It normally appears together with `flow_terminal`.
   * `indirect` — a computed or register-indirect transfer whose target is unknowable at assembly time. Inside an active region this is an error because suspension makes the counter value indeterminate but does not make the control-flow target knowable.
   * `multiway` — execution continues at one of a finite, explicitly declared target set. The target-set representation is activated with the M7 richer-effects work; until then such a transfer is treated as `indirect`.

   Direct `conditional`, `unconditional`, and `call` variants also declare `flow_target_operand`, the zero-based index of the operand containing the control-flow target. The analyzer must not guess from operand type: a customizable instruction may contain multiple address-like operands, and loads/stores also use addresses. `flow_target_operand` must identify an operand that resolves to a direct code target. `indirect` has no direct target operand; `multiway` will use its explicit target-set metadata.

Referencing an undeclared counter class in `flow_effects`, `flow_terminal`, or `flow_call_effects` is a configuration error (validated in `AssemblerModel._validate_config()`). A terminal reconciliation order other than `before_effect` or `after_effect` is likewise a configuration error. `flow_transfer` and `flow_target_operand` describe the CFG globally and do not name counter classes. A missing/invalid target operand, a target operand on an incompatible transfer kind, or `flow_call_effects` on a non-`call` variant is also a configuration error.

Placement follows existing instruction-config structure: the keys may be declared at the instruction level and overridden per `variants` entry. The semantic metadata seen by analysis is the explicit merge of instruction-level values with the selected variant's overrides; M0 retains that merged, immutable record. Instruction `aliases` share the root mnemonic's configuration, so effects apply to aliases automatically. Configurations using these keys must declare a `min_version` of at least the release introducing them.

Note the precedent of the existing `documentation.modifies` metadata, where instructions already declare which registers/flags/memory they touch — but only for documentation output. `flow_effects` is the machine-checked analogue for counter state, and **M5.1** surfaces it back into documentation: generated Counter rows appear alongside `modifies` in each instruction's documentation, derived from the same metadata the analyzer enforces rather than hand-authored prose.

#### Operand-Dependent Effects
An instruction's effect on a counter may depend on its operand(s), not just its mnemonic. The canonical case is stack-frame adjustment — `add sp, N` / `sub sp, N` moves the stack pointer by an operand-supplied amount — which is a *core* stack-tracking idiom on many ISAs, not an exotic case. The delta value in a counter's `source` field may therefore be an expression referencing the matched operands' resolved argument values (notation strawman, reusing the macro-token vocabulary already in the config language; shown here in the `stack` class's `stack_effect` source field):

```yaml
  add_sp:                       # `add sp, N`
    stack_effect: -ARG(0)       # delta is minus the first operand's argument value
  pushm:                        # push a register set, e.g. `pushm {r0-r3}`
    stack_effect: COUNT(0)      # delta is the count of registers in operand 0
```

Determinism is the governing rule, and it follows directly from the *Static Analysis Only* guarantee:

* If the operand exposes a **compile-time semantic value** (`add sp, 4`, or `add sp, FRAME_SIZE` where `FRAME_SIZE` is a constant), the delta is fully determined and tracking proceeds normally. This is the common stack-frame case and is needed for basic stack tracking — so operand-dependent *constant* deltas are scheduled early (M3, with the subroutine-frame work), not deferred to M7.
* An emitted operand encoding is not automatically a semantic value. A register operand may encode register `a` as an integer field, but that integer is the register selector, not the value held in `a`; `ARG(n)` must therefore see the retained operand's semantic kind and treat such an operand as runtime-valued rather than reading its opcode bits.
* `ARG(n)` uses a zero-based index into the actual source-written operand list matched by the selected instruction variant. It returns that operand's typed semantic value, not its emitted selector/encoding bits. An index outside the selected variant's operand list is a configuration error. For a macro expansion, each constituent instruction evaluates `ARG(n)` against that constituent's post-expansion operand list.
* If the operand resolves to a **runtime value** the assembler cannot know (`add sp, a` where `a` is a register, or a value computed at runtime), the delta is unknowable; the counter enters the indeterminate state exactly as a runtime-variable push loop does (handled per `#suspend`, or an error if used while not suspended). The analysis never guesses.
* Structural operand quantities (register-set cardinality, page-cross penalties, repeat counts) are the richer cases and remain **M7**.

Operand-dependent deltas depend on the line retaining its resolved operand argument values (architecture change A), which the assembler currently discards.

#### Macros Influence Counters Only in Aggregate
A macro carries **no independent flow metadata** — `flow_effects`, `flow_terminal`, `flow_transfer`, `flow_target_operand`, and `flow_call_effects` are not accepted on a macro definition (declaring them is a configuration error). A macro's entire influence on every counter and on control flow is **the aggregate of the instructions it expands to**, computed by the analysis seeing through to the expansion (each constituent instruction contributes its own effect, classification, target, and operand-dependent values evaluated against the macro's actual arguments). This is definitional, so a macro's counter effect can never drift from what it actually assembles — there is no separately declared macro effect that can disagree with the expansion. Consequently a macro may contain a `flow_terminal` instruction or a control transfer; these participate exactly as if written inline. The one asymmetry is operand observation: constituent *effects* apply sequentially, while flow values in the invocation's operand expressions all observe the invocation-entry state (see *Expressions*). Macro expansion already produces the constituent instructions (`CompositeAssembledInstruction`), so the aggregate falls out of walking the expansion rather than requiring separately-declared macro metadata.

#### Required Metadata: Fail Loud, Never Silently Inert
A flow counter is only as trustworthy as the configuration behind it. The feature **must error when the ISA configuration lacks the metadata a requested capability depends on**, rather than silently tracking nothing or analyzing unsoundly. A counter that quietly stays at its initial value because no instruction declares an effect on it would give false confidence — "the stack is balanced" about an analysis that never ran — which is worse than not offering the feature. The required-metadata checks, by capability:

* **Tracking a class at all.** `#track X` requires class `X` to be declared in `flow_counters` (else error) **and** at least one instruction in the ISA to populate `X`'s `source` field, map `X` in `flow_terminal` or `flow_invalidates`, or declare `flow_write_operands` while `X` has watched addresses. A *declared-but-inert* class is an error: the configuration cannot actually track or invalidate it. Validation also checks that `source` is a well-formed config path and that the values found there are deltas (integer or a supported delta expression), not arbitrary data — a `source` pointing at a non-numeric field is a configuration error.
* **Entry modes.** `#track X mode=M` requires class `X` to declare `entry_modes.M` (else error).
* **Control-flow coverage.** Every selected instruction variant encountered while a counter is active must explicitly declare `flow_transfer`, including `flow_transfer: none` for ordinary instructions. Absence is therefore mechanically detectable and is an error naming the unclassified instruction. Direct transfers also require a valid `flow_target_operand`. Earlier linear milestones reject any variant classified other than `none` (apart from the specifically supported unconditional terminal in M3); M5 consumes the same exhaustive metadata to build the CFG. The analyzer never infers "ordinary instruction" from missing metadata and never guesses a branch target from an address-like operand.
* **Terminal-based path ending.** A region whose execution paths rely on `flow_terminal` rather than reachable `#endtrack` requires the ISA to map that class in `flow_terminal` on at least one instruction. Without one, every path must reach `#endtrack`; otherwise the no-clear-execution-end diagnostic names the missing-terminal cause. The lexical region still ends only at `#endtrack`, an automatic boundary, or EOF.
* **Interval timing (M6).** Using `join: interval` across conditional branches that declare only scalar cycle deltas is permitted (scalar = same cost on both edges) and is not an error, only less precise.

Two error timings: **config-load checks** run in `AssemblerModel._validate_config()` independent of any source (internal consistency — an undeclared class named in `flow_effects`, `flow_terminal`, or `flow_call_effects`; malformed `entry_modes`; invalid transfer/target combinations); **usage-time checks** run when a counter is instantiated or used, because what counts as "sufficient metadata" depends on what the source actually invokes (inert class, exhaustive `flow_transfer` coverage within an active region, mode availability, and usable call summaries). Both report in the `flow` diagnostic category.

#### Edge-Dependent Deltas (configuring a branch with two-or-more relevant values)
A scalar delta assumes the effect is the same however control proceeds. That holds for stack operations but breaks for **conditional-branch cycle costs**: real CPUs charge different cycles for a branch taken vs. not taken (6502: 2 not-taken / 3 taken / 4 taken-across-page; Z80 conditional `RET`: 5 vs 11; `JR cc`: 7 vs 12). The cost belongs to the *edge*, not the instruction.

So the value found in a counter's `source` field may be an **edge-keyed map** instead of a scalar, for instructions classified `flow_transfer: conditional` (two edges: `taken`, `fall_through`) or `call`:

```yaml
  jr_cc:                          # `cycles` class has source: documentation.cycles
    flow_transfer: conditional
    flow_target_operand: 0
    documentation:
      cycles: { taken: 12, fall_through: 7 }   # edge-keyed; documentable as "12/7"
    stack_effect: 0               # scalar: a branch cannot change stack depth by outcome
```

This is how "two or more relevant integer values" on one branch are configured, and it composes along two independent axes:

* **Across edges** — the source value is a map keyed by edge; the analysis applies `taken` on the branch-target edge and `fall_through` on the fall-through edge. A scalar is shorthand for "same on every out-edge." Edge maps are legal for both `require-equal` and `interval` classes: delta representation and join policy are orthogonal. A path-dependent stack effect is unusual, but legal; a later `require-equal` join reports a mismatch unless subsequent path effects reconcile the values.
* **Across counters** — each counter reads its *own* source field independently, so one branch can carry an edge-map for `cycles` and a scalar (or nothing) for `stack` at the same time. The full effect of a branch is the cross-product {tracked counters} × {out-edges}, each cell declared independently.
* **Multi-way branches** (a jump table / dispatch with a declared target set — otherwise `indirect`): N out-edges. A scalar applies to all N (the usual case — a table dispatch costs the same regardless of which entry is taken); per-edge maps for >2 edges are permitted but rarely needed.

Edge-keyed cycle costs are an M6 feature (meaningless without the edge-aware CFG of M5) and the natural companion to `join: interval`: together they give correct worst-case timing across asymmetric branches. Page-crossing and operand-count-dependent costs (6502 indexed `+1 if page crossed`, Z80 `LDIR`) are *operand-dependent* deltas (M7); until then they are modeled conservatively (worst case) or the region is `#suspend`ed.

### Source Notation

#### Tracking Regions
Subroutine boundaries cannot be reliably inferred from assembly source, and subroutines may have multiple entry points (multiple labels). Therefore region starts are **declared, not inferred**:

```asm
#track stack mode=called        ; routine-owned movement: init 0, exit 0
multiply:                       ; any number of labels may follow the directive —
multiply_alt_entry:             ;   all are entry points, all see the same counter state
    push a                      ; stack: 0 -> 1
.var_x := COORDINATE(stack, 1)  ; name the slot currently at sp+1
    push b                      ; stack: 1 -> 2
.var_y := COORDINATE(stack, 1)
    ld a, [sp + .var_x]         ; assembler computes current offset to .var_x (= 2)
    pop b                       ; stack: 2 -> 1
    pop a                       ; stack: 1 -> 0
    ret                         ; pre-effect exit check: 0 == 0; then path ends
```

Like every `#`-introduced preprocessor directive, the flow directives are lowercase and case-sensitive: `#TRACK` is not recognized as a directive and falls through to the ordinary unknown-instruction error (clarified 2026-07; applies to all preprocessor directives uniformly).

Flow constructs distinguish two kinds of operand (clarified 2026-07), and the distinction is **context-universal** — it applies identically in flow directives, instruction operands, data values, and `:=` declarations:

* **Name operands** are literal identifiers naming flow entities and are *never* preprocessor-substituted, wherever they appear: the counter/class operand of every directive, the `as=` and `mode=` parameter values, the argument of `COUNTER()` and the first (counter) argument of `COORDINATE()`. With `#define stack 5` in effect, `COUNTER(stack)` in an instruction operand still reads the counter named `stack`, and `#track cycles as=source` creates an instance literally named `source` even if `source` is `#define`d. A bare counter-coordinate reference lives in the ordinary symbol namespace and receives no such protection: it is macro-resolvable text like any label reference, so coordinate names must simply not collide with `#define` macros.
* **Value operands** are ordinary compile-time numeric expressions and accept every compile-time constant kind uniformly: assembler `=`/`EQU` constants, address labels, `#define` preprocessor macros, and ISA-configuration predefined constants — plus the explicitly permitted flow forms per context. The value contexts are the `init=`/`exit=` parameter values, the right-hand sides of `#set` and `#resume`, both `#assert` operands, and the second (offset) argument of `COORDINATE()`.
* **Flow operator calls must be written whole.** A macro value may *be* a complete flow expression (`COUNTER(stack)`), but a flow operator call may not be assembled from separate expansion fragments — the name from a macro value and the parenthesis from the referencing context (`#define FLOW_FN COUNTER` … `FLOW_FN(stack)`), or the reverse. The split form defeats positional argument protection and is rejected at its point of use with a dedicated diagnostic. The rule is strictly about *call position*: a flow keyword used as a plain value (`#assert FLAVOR == COUNTER` with `#define FLAVOR COUNTER`) is an ordinary identifier — significant for ISAs that do not enable flow counters, where these words are not reserved. For classification purposes a call-position reference whose expansion ends in an operator name counts as flow dependence; a flow-dependent assertion is skipped under `--no-flow-checks`, while an emitted use still requests value resolution.

* `#track <class> [as=<counter name>] [mode=<entry mode>] [init=<initial value>] [exit=<exit value>] [min=<lower bound>] [max=<upper bound>]` — creates a counter instance of the named class and opens its tracking region (keyword parameters follow the `#create-scope prefix="..."` convention). The counter's name defaults to the class name, so `#track stack` creates a counter named `stack`. `mode=` selects one of the class's configured `entry_modes`; explicit `init=`/`exit=` override values supplied by the mode. With no explicit or mode-provided initial value, the initial value is the class's `default_init` (0 unless configured). With no explicit or mode-provided exit value, `exit_policy: balanced` creates an exit contract equal to the resolved initial value, while `exit_policy: none` creates no implicit equality contract. Opening a counter whose name is already active is an error (the prior region had no clear end point); multiple *concurrent* instances of the same class are allowed with distinct `as=` names. `min=`/`max=` declare **instance bounds** (M5): they exist because on RAM-stack machines the depth limit is a property of the *program's* memory map, not the ISA — the class author cannot know it. They are value operands, so they accept every compile-time constant kind including address labels, letting the bound derive from the program's own memory-map symbols (`max=STACK_TOP - heap_end`) and stay correct as the layout changes. Instance bounds are enforced exactly where class bounds are — every delta application, `#set`, `#resume`, `#entry` roots, and the resolved initial value — independently per instance. The effective bound is the **more restrictive** of class and instance (tighten-only): an instance bound looser than the class's declared bound is an error on the `#track` line, since a program must not claim more than the hardware provides. Instance bounds are per-program facts and are not rendered in generated ISA documentation.
* Flow-control directives (`#set`, `#suspend`, `#resume`, `#endtrack`, `#entry`), the flow shorthand form of `#assert`, the first argument of `COORDINATE()`, and `COUNTER()` reference counter *instances* by name. A counter-coordinate reference instead names the coordinate symbol itself, which records the instance from which it was derived.
* A tracking region has both a **lexical extent** and execution paths. Its lexical extent starts at `#track` and ends only at the matching `#endtrack`, an automatic scope boundary described in Open Question 3, or EOF. A `flow_terminal` never ends the lexical extent: it reconciles the counter before or after its configured effect according to that class's `flow_terminal` value, then closes only the execution path that reaches it.
* `#endtrack <counter> [exit=<expected value>]` — explicitly ends the lexical region; needed for counters with no natural terminal instruction (e.g., a cycle counter) and useful as a delimiter before unrelated source that follows terminal-closed paths. With flow checks enabled, an explicit `exit=` creates an exact check; without it, the instance's existing exit contract is checked if one exists. Under `exit_policy: none`, or under `--no-flow-checks`, the directive simply closes the region. In CFG terms it is an exit node for every reachable edge arriving at it. When every path has already ended at a `flow_terminal`, an unreachable `#endtrack` is legal as a lexical-only delimiter and performs no additional exit check. No live edge may bypass `#endtrack`; an edge entering after it or otherwise leaving the region is a region-boundary error when verification or requested value resolution requires that region to be analyzed.
* If all discovered paths have terminated but the lexical region continues, unreachable instructions receive no counter state and are not subjected to effect/transfer completeness checks until declared as an entry. A global, file, or named-scope label in that terminal-closed remainder receives a `flow` warning: it may be an externally entered routine that is silently inside the still-open region. Insert a lexical-only `#endtrack`, or declare a new entry with an explicit value. Local labels remain exempt from the external-entry warning, but `COUNTER()`/coordinate-reference use on any unreachable line remains an error.
* `#entry <counter> [value=<expr>]` — declares an intentional alternate entry at the next compilable label and adds it as an independent CFG root. Blank and comment-only lines may appear between declarations and that label. A consecutive group of `#entry` directives may declare values for multiple counters on the same label; no instruction, data, other directive, or intervening label may separate the group from its target, and repeating the same counter in one group is an error. When the label already has a unique incoming counter state, `value=` may be omitted and that state becomes the entry contract. An otherwise unreachable label has no current value, so `value=` is required. Every ordinary incoming edge must reconcile with the declared root value under the class's join policy.
* `#loop count=<N>` / `#loop max=<N>` — attaches to the next compilable line, which must be a label, and declares the number of **loop iterations** for the natural loop headed by that label (see *Loops*; provisional M7). Blank/comment lines may intervene; an instruction, data line, non-loop directive, or another label may not. The label must resolve to an executable CFG node, dominate the annotated loop body, and be the target of at least one validated back-edge in the same tracking region. Thus `count=1` executes the body once and takes its back-edge zero times. `<N>` must be a compile-time constant.
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

* `COUNTER(<counter>)` — the counter's current tracked scalar value at this program point. It is invalid for an `interval` class.
* `COUNTER(<counter>).min` / `COUNTER(<counter>).max` — the lower / upper bound of an `interval` counter at this line. These selectors are valid only in flow assertions, never as ordinary numeric operands. Scalar counters have no `.min` / `.max` selectors.
* `<symbol> := COORDINATE(<counter>, <offset-expression>)` declares an immutable **counter-coordinate symbol**, distinct from an ordinary `=` / `EQU` constant. The offset names the physical position currently addressed as `counter + offset`: for example, `.slot := COORDINATE(stack, 0)` names the current top of stack, while `.arg := COORDINATE(stack, 3)` names the location currently addressed as `sp+3`. Its fully spelled name follows the existing symbol-scope and namespace rules: `.var_x` and `var_x` are different symbols, so a reference must preserve the dot. The declaration emits no bytes and does not move the address counter.
* The `COORDINATE()` offset must be an ordinary compile-time scalar expression containing no flow-derived value or coordinate symbol, and its sign must satisfy the counter class's `coordinate_offsets` policy. Zero is accepted only when `allow_zero_offset` is true. The named instance must be an active scalar counter. A right-hand side with no `COORDINATE()` call (`.x := 4`), an interval counter, a second counter, or flow-derived offset arithmetic is an error. The former affine spelling `.arg := COUNTER(stack) - 3` is intentionally rejected: `COORDINATE(stack, 3)` directly states the programmer's `sp+3` address instead of exposing the analyzer's internal saved-coordinate arithmetic. Ordinary constants may not be assigned a flow-derived value with `=` or `EQU`.
* A **bare reference to a counter-coordinate symbol** (revised 2026-07; this replaces the removed `OFFSET()` operator) evaluates to the current value of the symbol's associated scalar counter minus the symbol's saved coordinate — the position's current offset at that program point. This is the feature issue #18 asks for. `ld a, [sp + .arg_x]` therefore reads exactly like the hand-maintained constant it replaces, and converting existing code means editing only the declaration line (`=` to `:= COORDINATE(...)`), never the reference sites. Coordinate references share the ordinary symbol namespace: a name that resolves as an ordinary label or constant keeps that meaning (labels outrank coordinates), and a token that parses as a numeral in the default base keeps its numeric fallback. Because a bare reference is lexically indistinguishable from a label, coordinate resolution happens during the analysis pass by scope lookup rather than in the parser; mirroring the address-label paradigm, no wrapper operator marks the use site — editor tooling (hover, definition color) and the `:=` declaration carry the visibility burden.

Flow-derived values are deliberately restricted to contexts that cannot affect layout or instruction selection:

* **Allowed:** `COUNTER()` and counter-coordinate references in fixed-width instruction operand values, fixed-size data element values, and flow-aware directives such as `#assert`, `#set`, and `#resume`; `COORDINATE()` only as the complete right-hand side of a `:=` counter-coordinate declaration.
* **Rejected:** `.org`, memory-zone selection, alignment expressions, repetition/fill counts, conditional-preprocessor expressions, expressions used to select an instruction variant or operand form, and any other context that affects address assignment, emitted word count, or which instruction is selected.

The parser reports a flow diagnostic when `COUNTER()` or `COORDINATE()` appears in a rejected context. A bare coordinate reference cannot be recognized lexically, so its rejection moves to resolution time: a rejected context is never visited by the analysis pass, and evaluating an unresolved coordinate there raises the flow diagnostic instead. This context rule is what permits the tracking pass to run after address assignment without creating a dependency from analysis back into layout.

At an instruction, `COUNTER()` and coordinate-reference operand expressions observe the **entry value before that instruction's own delta**. A source-level macro invocation is one instruction for this purpose (revised 2026-08): flow values in its operand expressions observe the invocation-entry state for **every** expanded constituent, not the state between the constituents' own effects. This keeps macros whose spelled operand arithmetic pre-compensates for their internal counter motion (a stack-copy macro that pushes between its reads, e.g. the Minimal 64x4 `phs4s`) emitting identical bytes for constant and coordinate arguments alike. The instruction's delta then produces the state on its outgoing edge(s). A `:=` declaration or flow directive between instructions observes the state after all preceding instructions on that source line and before the following instruction. A `flow_terminal` reconciles each mapped class in its explicitly configured order: `before_effect` checks the entry value and ends that class's path without applying its delta inside the region; `after_effect` applies the delta and checks the resulting value.

#### Assertions and Re-anchoring
* `#if` / `#elif` retain their existing compilation-selection role and may use only ordinary preprocessor inputs, including the configuration-derived `__FLOW_COUNTERS_AVAILABLE__` capability symbol. They must never accept `COUNTER()`, counter coordinates, or any other static-analysis result: analysis runs only after the source to compile has been selected, and an analysis result must not control source inclusion, instruction selection, layout, or emitted word count.
* `#assert` is a general preprocessor assertion with the same *ordinary condition grammar and preprocessor-value resolution* as `#if`, but it observes rather than selects: `#assert <expr>` implies `!= 0`, while the comparison form accepts `==`, `!=`, `<`, `<=`, `>`, and `>=` with numeric or string operands resolved from preprocessor macros and built-in symbols. A failed assertion may append `"message"` or `<color> "message"`; the custom message becomes the diagnostic text, and `<color>` may be `black`, `red`, `green`, `yellow`, `blue`, `magenta`, `cyan`, or `white`, matching `#print`. Assertions have no verbosity operand because failure always terminates assembly.
* `#require` remains the domain-specific compatibility declaration. Its non-quoted form is restricted to a built-in language/BespokeASM version symbol by itself or one comparison with another built-in version symbol or literal; user-defined macros and general arithmetic are rejected. Complete versions use semantic-version ordering. Its legacy quoted form names the required ISA language and optionally constrains its semantic version, and its diagnostics describe a compatibility failure. `#assert` instead accepts arbitrary preprocessor invariants, supplies optional user-controlled diagnostic text/color, and—when flow analysis is enabled—may act as a deferred flow checkpoint. The two intentionally overlap for simple built-in version comparisons, but `#require` communicates an external compatibility contract while `#assert` checks an internal source invariant.
* In a flow-enabled ISA, either side may also contain `COUNTER()` or a counter-coordinate reference. `#assert <counter> <comparison> <expr>` remains shorthand for `#assert COUNTER(<counter>) <comparison> <expr>` when the otherwise-undefined left name denotes a scalar flow-counter instance; when it instead denotes a coordinate, the assertion compares the coordinate's current offset. Because a coordinate is indistinguishable from an undefined name at parse time, an assertion operand containing any name the preprocessor cannot settle is classified flow-dependent and deferred to the analysis pass (and is therefore skipped under `--no-flow-checks`). An explicit `COUNTER(name)` is preferred where the shorthand would be ambiguous with a preprocessor macro. A flow assertion is purely a checkpoint: assembly errors when the comparison is false and otherwise forwards the incoming state unchanged. It does **not** collapse a join, discard an infeasible path, or re-anchor a value.
* `#set <counter> = <expr>` — re-anchors a **scalar** tracked value when the programmer knows better than the assembler (e.g., after a stack-pointer manipulation the effect model cannot express). This is a programmer assertion and is taken on faith. In the CFG it transforms each incoming scalar state into the asserted scalar outgoing state; paths that bypass it remain unchanged and reconcile normally at a later join. With flow checks enabled, the asserted value is checked against the class's `min_value`/`max_value` bounds — a programmer asserting a value the class declares impossible is most likely a mistake — and, per the dead-coordinate rule, `#set` permanently invalidates the counter's prior coordinates. `#set`, `#suspend`, and `#resume` are scalar-only through the committed M0–M5 scope; applying them to an `interval` counter is an explicit unsupported-operation error. Their interval behavior, if any, is deferred to the provisional M6 design rather than implicitly collapsing a hull.

#### Subroutine Arguments and the Return Address
On many 8-bit ISAs, `call` pushes a 16-bit return address and `ret` pops it. A subroutine that addresses caller-pushed arguments through the stack pointer must account for that return address sitting between its own frame and the caller's slots. Flow counters keep two concerns separate: the region counter begins at zero and tracks only stack movement owned by the routine, while each `COORDINATE(stack, N)` directly states the physical `sp+N` position dictated by the calling convention. A return instruction configured with `flow_terminal.stack: before_effect` requires the routine-owned counter to be back at zero before its physical return-address pop occurs.

```asm
; ---- caller ----
#track stack mode=called    ; routine-owned movement: init=0, exit=0
    push a                  ; argument: stack 0 -> 1
    call my_func            ; declared flow_call_effects.stack = 0 at caller fall-through
    pop a                   ; reclaim argument: stack 1 -> 0
    ret                     ; pre-effect exit check passes at 0

; ---- callee (possibly in another file) ----
#track stack mode=called    ; from ISA config: init=0, exit=0
my_func:
.arg_x := COORDINATE(stack, 3)  ; this ISA addresses the argument as sp+3
    push b                      ; routine-owned stack: 0 -> 1
    ld a, [sp + .arg_x]         ; offset changes from 3 to 4
    pop b                       ; routine-owned stack: 1 -> 0
    ret                         ; checks 0 == exit 0 before physical stack effect
```

(The `.arg_x` counter-coordinate symbol is declared after `my_func:` because local-scope symbols cannot precede their parent non-local label; it lands in `my_func`'s local scope, which is where it belongs.)

Points of note:

* The `called` entry mode uses `init: 0, exit: 0`: the counter measures the callee's own net stack movement, not the caller-owned return address. The return-address size remains truthful in the physical `call`/`ret` instruction effects and in the calling convention's `COORDINATE()` offsets; it is not added to the region baseline.
* Caller-side argument slots cannot be inherited automatically — a subroutine may be called from many sites at many depths. The callee instead *declares its calling convention* directly in stack-pointer-relative terms with expressions such as `.arg_x := COORDINATE(stack, 3)`, meaning “this argument is at `sp+3` on entry.” The declaration records both the physical position and its stack-counter association. Inserting a new `push` inside the callee still updates every argument offset automatically, which is the core promise of issue #18.
* The caller's and callee's declarations are independent conventions; the analyzer cannot yet verify they agree (a caller pushing one argument where the callee expects two). That is the cross-region verification problem noted in Open Questions.
* `.arg_x = 0` would be an ordinary constant with no counter association: referencing it emits the frozen `0`, never a tracked offset. The `:=` spelling makes the counter association explicit in the declaration rather than inferring it from an arbitrary number.

#### Entry Modes: Called vs. Jumped-To Routines
How a routine is *entered* is not inferable from its code — it is a calling-convention fact that lives in the heads of the routine's callers. A routine entered via `call` begins life with a return address on the stack; the same instructions entered via `jmp` (a dispatcher target, a coroutine, a tail-call destination) begin with nothing extra. The programmer declares which applies with `mode=`:

* **`mode=called`** — normally enters at 0 and ends at a `flow_terminal` instruction (`ret`). A pre-effect terminal requires the routine-owned counter to be reconciled to its exit value before the physical return-address effect.
* **`mode=jumped`** — enters at 0 with no terminal instruction available: there is no `ret` to end the path, so the routine uses a reachable `#endtrack` (exit check and lexical closure) immediately before the unconditional transfer out:

```asm
#track stack mode=jumped
dispatch_handler:               ; reached via jmp from the dispatcher — no return address
    push a
    ...
    pop a
#endtrack stack                 ; exit check: balanced back to 0
    jmp dispatch_loop           ; transfer out — sanctioned, the region is already closed
```

* **Tail calls** mix the two: a routine entered via `call` that exits via `jmp` to another subroutine, leaving the original return address on the stack for the tail-callee's `ret` to consume. Because caller/control-flow state is outside the routine-owned counter, the tail path closes balanced at zero:

```asm
#track stack mode=called
process_fast:
    ...                         ; balanced body, back to 0
#endtrack stack exit=0          ; routine-owned movement is reconciled
    jmp process_common          ; tail call; process_common's ret returns to our caller
```

* A routine entered via `call` from some sites and `jmp` from others may still have different physical parameter coordinates and terminal conventions even when both region counters start at zero. The code must pick one declared convention (or be restructured, e.g., a thin called wrapper that falls into the jumped body); equal numeric baselines do not make incompatible calling conventions interchangeable.

### Tracking Semantics
* Tracking runs in the separate analysis pass after address assignment. It retains the original source-ordered line collection for directives and lexical regions, and uses the address index/CFG when execution order diverges from source order.
* Every reachable label inside an active region records the counter value at its position; an unreachable label has no value unless `#entry ... value=` establishes a root.
* `COUNTER()` values and counter-coordinate symbols are fully determined during the analysis pass for straight-line constant deltas, so they resolve during second-pass expression evaluation exactly like other compile-time values — no new fixed-point iteration is required.
* Lines that emit no instructions (data directives, labels, comments) have no effect unless explicitly configured.

### Path Analysis and Ambiguity Rules
The analyzer is deliberately conservative: if it cannot prove the counter value at a line is unique, that is an error, not a guess.

#### The analysis model
Within a tracking region's explicitly determined lexical extent, the analyzer builds a control-flow graph from exhaustive `flow_transfer` metadata and the operands selected by `flow_target_operand`, then propagates counter values forward from the region entry and every `#entry` root with a worklist algorithm. No CFG edge may enter after `#track`, leave before a `flow_terminal` or `#endtrack`, or jump across `#endtrack`; such an edge is an error because it would create an untracked execution path. Directives are zero-bytecode CFG nodes: a flow-dependent `#assert` checks and forwards its incoming state; scalar `#set` re-anchors it; scalar `#suspend` changes it to suspended; scalar `#resume` restores it; and a reachable `#endtrack` is an exit node. A `#endtrack` with no reachable predecessor remains a valid lexical delimiter after all paths have already terminated.

* Each line in the region gets *one* counter value per program point (not per path), reconciled across incoming edges per the class's `join` policy. Under `require-equal` (default) the first edge assigns the value and any later edge arriving with a *different* value is a join-mismatch error. Under `interval` the value is a `[min,max]` hull and a join unions the incoming hulls (never an error).
* A `conditional` transfer propagates to both the explicitly identified branch target and the physical fall-through successor; an `unconditional` transfer propagates only to its target; a `call` applies a declared caller-visible summary when available or propagates an unresolved named-callee summary to the physical fall-through successor. For an emitted instruction, physical fall-through begins at `instruction.address + instruction.word_count`, not at the next instruction in source order. Labels and zero-width analysis directives at that address may lead to the instruction node there, but the resolver must not skip emitted data, an address gap, an ambiguous same-address group, or a region boundary. Each propagated edge applies that edge's delta — which for branch instructions may differ between the taken and fall-through edges (see *Edge-Dependent Deltas*).

* Every path must terminate at a `flow_terminal` instruction or `#endtrack`. An exit-value equality check applies when the instance has an exit contract; termination remains structurally required when it does not. `#suspend` / `#resume` must also be structurally balanced on every path: paths may not join in active and suspended states, bypass a `#resume`, or reach a terminal while suspended.
* Lines not reachable from any entry point have no counter value. Their instructions do not participate in effect/transfer completeness checks unless a `#entry` makes them reachable. Referencing `COUNTER()` or a counter coordinate on an unreachable line is an error, and an externally visible label in a terminal-closed but lexically open remainder receives the warning defined below.

The *Loops* and *Consecutive Branches and Path Count* subsections below explain how this per-point model handles cyclic and heavily-branched control flow.

Because each path is checked independently, **per-path imbalances ("push leaks") are detected even when only one path is wrong**:

```asm
#track stack mode=called
divide:
    push b                  ; stack: 0 -> 1
    cmp a, 0
    jz .div_by_zero
    ; ... normal path ...
    pop b                   ; stack: 1 -> 0
    ret                     ; pre-effect exit check passes at 0
.div_by_zero:
    ld a, 0xff
    ret                     ; pre-effect exit check sees 1
                            ; ERROR: counter 'stack' is 1, expected 0
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

  `#loop count=N` (exact) or `#loop max=N` (upper bound) lets an `interval` counter compute a finite contribution for **N body executions**, including the fall-through cost on the final iteration, instead of widening to `∞`; it lets a `require-equal` counter that accumulates a *known* amount per iteration treat the post-loop value as deterministic (`entry + N × body`). The trip count must be a compile-time constant; otherwise the loop stays unbounded/indeterminate. Inside such a loop, `COUNTER()`/coordinate references remain indeterminate (the value differs per iteration) — the annotation makes the *post-loop* value knowable, not the interior.

#### Consecutive Branches and Path Count
A sequence of *k* branches creates up to 2ᵏ distinct execution paths, but the analysis **does not enumerate paths** — and this is the key to why it scales. The worklist computes one lattice value per *program point* and merges incoming edges there per the `join` policy, so cost is **O(nodes + edges), not O(2ᵏ paths)**. Consecutive branches simply add more nodes and merge points; nothing about them is exponential.

The deliberate trade is that the analysis is **path-insensitive**: merging at joins discards correlations between branches (it cannot know that "if branch A took the taken edge then branch B must too"), so it treats all 2ᵏ edge combinations as possible even when some are dynamically infeasible. Both join policies stay *sound* in the safe direction:

* `require-equal` never misses a real imbalance, but may report a mismatch on a path that cannot actually occur (a false positive).
* `interval` never under-estimates, but may report a WCET higher than any real execution reaches (a conservative over-approximation).

Where path-insensitivity costs precision, `#assert` can document and verify what the analysis already proves, but it cannot make a conflicting incoming path disappear. The programmer may explicitly re-anchor with `#set` on the relevant predecessor path(s), accepting responsibility for that override; a future predicate-aware `#assume` construct would be needed to prune dynamically infeasible paths soundly enough for the counter lattice. Consecutive branches are therefore accounted for in linear time, with imprecision surfaced as a safe error/over-estimate rather than a silent wrong answer. Nested and consecutive branches compose freely as long as each branch reconverges to a consistent value (for `require-equal`) before the next merge.

#### Label-Scope Awareness (mid-region entry points)
The analysis only follows control flow it can see; it cannot know about a `jmp` or `call` elsewhere in the program targeting a label inside the region. Whether such an outside transfer is *possible* is determined by the label's scope, which the assembler already tracks:

* **Local labels (`.` prefix)** cannot be referenced from outside the local scope bounded by their parent label. They pose no external-entry risk and are exempt from this check.
* **Global, file (`_` prefix), and named-scope labels** are reachable from code the analyzer is not looking at. Each one inside a region is a *potential entry point* — and outside code transferring there will, by convention, assume the region's entry-time counter value.

Therefore: a global, file, or named-scope label inside a lexically active region receives a **warning** when either (a) its tracked value differs from the region's initial value, or (b) it is unreachable and therefore has no tracked value. The latter is the terminal-closed-region case: the label may begin an externally entered routine that accidentally sits inside a region whose execution paths ended but whose lexical extent did not. Both warnings are escalatable via warnings-as-errors. A reachable label at the region's entry value produces no diagnostic, which is what makes several entry labels at the top of a region work without ceremony.

For an intentional alternate entry, one or more consecutive `#entry <counter> [value=<expr>]` directives acknowledge the next compilable label. Each warning is suppressed and the label is added as an independent CFG root for that counter. A reachable label may omit `value=` and reuse its unique incoming value; an unreachable label must provide it. Resolution is ordered deterministically: first propagate from the region entry and every `#entry` having an explicit `value=`; then resolve all value-less declarations from the unique incoming values computed in that pass. A value-less declaration whose label is unreachable or has conflicting incoming values errors instead of becoming a root. Thus two value-less entry labels reachable only from each other both fail with “unreachable — `value=` required.” A successfully resolved value-less declaration is then recorded as an independent root with that already-computed value; because its label was already reachable, doing so cannot create new reachability that changes another declaration's eligibility. Multiple counters compose explicitly:

```asm
#entry stack value=2
#entry cycles value=0
alternate_entry:
```

This verifies each declared entry path to its terminal now; a future cross-region verification phase can additionally check that outside call sites honor the convention.

This analysis needs surprisingly little knowledge of instruction behavior: exhaustive transfer classification, explicitly identified direct targets, and declared deltas. It does *not* model registers, memory, or flags — which is why `conditional` branches are treated as "either way is possible" and both paths must independently check out. The analysis can therefore flag a path that is dynamically impossible (e.g., a branch guarded by a condition that always holds); an explicit `#set` on the affected predecessor path is the available override. `#suspend` acknowledges an indeterminate counter value but does not alter or excuse unknown control flow.

**Calls compose rather than inline:** when the analyzer encounters a `call`, it does not descend into the callee. Its fall-through value carries an abstract per-class summary, `CallEffect(<resolved callee label>, <counter class>)`. The summary records the callee identity instead of silently assuming that every class has the same callee behavior. A possible later interprocedural phase would resolve it from the named callee's verified region.

M5 supports the conventional balanced-call case only through an **explicit caller-visible summary** declared on the call instruction:

```yaml
call:
  stack_effect: 2                    # what entry into the callee does to true depth
  flow_transfer: call
  flow_target_operand: 0
  flow_call_effects: { stack: 0 }    # caller-visible net after the callee returns
```

The `stack_effect: 2` is used when checking the callee's own called-entry region; the caller applies the declared net `0` to its fall-through state. This declaration is an ISA calling-convention contract, not a value inferred from whichever `ret` variants happen to exist.

Each `flow_call_effects` value is a target-independent ISA calling-convention contract and may be any supported compile-time scalar, including a nonzero net delta. The analyzer takes that declaration on faith for every target selected by the instruction variant; it does not infer or verify the value from callee bodies. A convention whose net effect varies by callee therefore cannot be represented by one call variant's summary.

If a class has no `flow_call_effects` entry — notably cycles, whose callee cost commonly depends on the named callee — its summary remains unresolved in M5 and in the provisional M6 design. The analyzer must not turn it into a scalar, interval bound, or operand literal: a value after such a call cannot be used by `COUNTER()`, coordinate references, bounds checks, or precise timing assertions unless a future interprocedural phase resolves the named callee. Counting only the call instruction and omitting the callee body would make WCET and constant-time claims unsound. Unresolved summaries come in two kinds that future milestones must treat differently: a callee *inside the program* is interprocedurally resolvable in principle, while an **external callee** (a target address with no program content, such as a ROM routine) can never be — its body is not in the compilation, so only a programmer-declared summary can ever describe it. The provisional M6 design's target-keyed call summaries exist for exactly the external case.

The callee's own balance is verified independently by its own tracking region. M5 does not claim to verify that a particular call target honors the declared caller-visible summary. A uniform callee-pops convention can therefore be represented as a nonzero target-independent ISA contract, while body-based or target-varying caller-visible changes remain unresolved unless the source is re-anchored explicitly after the call. A possible future interprocedural phase could record each named callee's verified entry/exit summary, check it against call sites, and support target-specific effects (see Open Questions), but that phase is outside the committed scope.

#### Error and warning rules
1. **No clear execution end point** — any live path that reaches EOF, the lexical `#endtrack`, the start of another region for the same counter, or an unconditional transfer out of the region without first reaching a `flow_terminal` or reachable `#endtrack` → error. EOF is otherwise a valid lexical end when all paths terminated. Starting another region for the same counter before a lexical `#endtrack` remains an error even if prior paths terminated. In that terminal-closed case, the diagnostic must explain that the prior region is still lexically open and name the corrective action, for example: “add a lexical `#endtrack stack` after the previous routine's last terminal before starting another `stack` region.”
2. **Join mismatch** (`require-equal` classes only) — a line reachable along multiple paths carrying different counter values → error reporting both values and their source lines. Backward branches (loops) are the common case: a branch back to a loop head errors unless the loop body is net-zero for the counter — precisely the class of bug this feature should catch. See *Runtime-Variable Counter Changes* for loops that are intentionally not net-zero. For `interval` classes this is not an error; paths simply union into the hull, and divergence is surfaced only if a `#assert` bound is violated.
3. **Exit imbalance (push leak)** — for an instance with an exit contract, any path reaching a `flow_terminal` instruction or `#endtrack` with a different value → error identifying the path's distinguishing branch. An instance with `exit_policy: none` and no explicit/mode-provided exit has no equality check at closure.
4. **Bounds violation** — counter exceeds `max_value` or drops below `min_value` (e.g., more pops than pushes) on any path → error.
5. **Dead coordinate reference** — a counter-coordinate symbol has a monotonic validity bit in addition to its numeric counter value. For a positive-side declaration, it is permanently invalidated on every path that crosses its saved coordinate; for a negative-side declaration, the direction is reversed. Equality remains live only when `allow_zero_offset` is true. In either orientation, leaving the configured live side means that slot no longer exists, and later returning to the same value creates a different slot rather than resurrecting it. A zero-offset declaration — possible only when `allow_zero_offset` is true — has no inherent orientation; it is treated as a *positive-side* coordinate for invalidation purposes (the counter dropping below the saved position kills it, rising above it does not). At a join, a coordinate invalid on any incoming path is invalid thereafter. Referencing an invalid coordinate → error. This is distinct from a `min_value`/`max_value` violation: crossing a slot can be normal even when the counter remains within its configured bounds. `#set`, `#resume`, and an `#entry` root at a non-initial depth also invalidate prior coordinates unless a future explicit preservation contract says otherwise.
6. **Unknown instruction effect** — an instruction with no declared effect for an actively tracked counter, handled per the counter's `unknown_instructions` setting.
7. **Indirect transfer** — an `indirect` jump inside an active region → error because the analysis cannot follow it. Suspending the counter does not waive this structural error; close the region before the transfer or, in the future, declare a finite target set.
8. **Region-boundary crossing** — a branch targeting a label outside the active region for the counter, entering a region after its `#track`, or jumping across an `#endtrack` → error. Unlike a `.org` auto-close warning, this is an actual execution path that would otherwise be silently untracked.
9. **Mid-region external entry point** — a global, file-scope, or named-scope label inside a lexical region where the tracked value differs from the region's initial value, or where no tracked value exists because all known paths already terminated → warning by default, escalatable to an error via warnings-as-errors; suppressed by a valid preceding `#entry` declaration. Local-scope (`.`) labels are exempt (see *Label-Scope Awareness*).

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
.before_push := COORDINATE(stack, 0)  ; snapshot the known position
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
  * any reference to `COUNTER()`, and any reference to one of its coordinates, is an **error** — there is no value to resolve;
  * creating new counter-coordinate symbols against it is an error;
  * encountering a `flow_terminal` instruction for the counter (e.g., `ret`) while suspended is an error: that path's balance cannot be verified, so the programmer must `#resume` (asserting a value) or `#endtrack` explicitly first;
  * `#endtrack` without `exit=` closes the region silently: the explicit suspension is the programmer's deliberate acknowledgement that the exit contract cannot be checked (`exit=` there remains an error). When the indeterminacy was instead caused by counter-anchor invalidation, that acknowledgement was never given, so the unchecked exit contract is reported as a `flow` warning naming the invalidation provenance.
* `#resume <counter> = <expr>` re-anchors the scalar counter to a known value, typically a snapshot taken before suspension. Like `#set`, it is an unverifiable programmer assertion. `#suspend`/`#resume` on an interval counter is unsupported through M5 and deferred to the provisional M6 design.
* Counter-coordinate symbols declared *before* suspension retain their numeric coordinate values, but `#suspend` / `#resume` does not prove that the run-time slots survived the indeterminate interval. Therefore `#resume` permanently invalidates every coordinate for that counter unless the directive explicitly names a future, stronger slot-preservation contract. An invalid coordinate may never be referenced for its offset. `#resume <counter> = <coordinate>` naming a coordinate that was *already* invalidated re-anchors on faith like any other `#resume` value, but receives a `flow` warning: the analysis proved that saved position was crossed.

Note the deliberate parallel with run-time reality: when the stack pointer moves by a runtime-determined amount, `sp`-relative addressing of older slots is invalid *at run time* too — the standard assembly idiom is to save the stack pointer into a frame-pointer register first. The indeterminate state mirrors exactly the window in which the programmer cannot use `sp`-relative offsets anyway, and the pre-suspension snapshot mirrors the frame pointer.

A possible refinement for *bounded* runtime variability (e.g., "this loop pushes at most 16 items") would be a suspended-with-bounds mode that keeps `min_value`/`max_value` checking alive using an interval instead of a point value (M7, alongside bounded-loop iteration counts). Out of scope for earlier milestones. A shipped example now motivates it concretely: `cstr_reverse` in the Minimal 64x4 stringlib suspends across push/pop loops whose depth is runtime-dependent but bounded (at most one push per character of a sub-256-byte string) — with this refinement, that span could keep an enforced `[0, 255]` bound instead of going fully dark, and `#loop` cannot cover it because the trip count is runtime data.

### Diagnostics
All violations are reported through the existing `DiagnosticReporter` with a new `flow` category. The reporter must add `flow` to the categories elevated by `--warnings-as-errors` (its current default set contains only `user`) and preserve the category for tests/tooling; this is small plumbing work, not behavior that comes automatically from naming the category.

## Key Acceptance Test Cases
Organized by what each group proves. "Error/warning" expectations include asserting the diagnostic's category (`flow`), file, and line number — a diagnostic on the wrong line is a failing test.

### Static-analysis-only invariant (the load-bearing guarantee)
1. **Strip-equivalence golden test:** at each milestone, assemble a program exercising every **shipped** directive, `:=` declaration form, and expression operator; assemble its hand-stripped twin (directives and coordinate declarations removed, all emitted analysis-derived references replaced with resolved literals); outputs are byte-identical.
2. **Config inertness:** the same source assembles to identical bytes under an ISA config with and without `flow_counters`/`flow_effects` metadata, when the source uses no flow counter features.
3. **Zero address footprint:** label addresses and `.org`-relative layout are identical with and without flow counter directives interleaved in the source.

### Configuration validation
4. `flow_effects`, `flow_terminal`, or `flow_call_effects` naming an undeclared counter → config error. (`flow_transfer` is a global CFG classification and does not name a counter.)
5. Invalid `flow_transfer` value; missing/incompatible `flow_target_operand`; invalid `flow_terminal` reconciliation order; or `flow_call_effects` on a non-`call` variant → config error.
6. Invalid `unknown_instructions`/`exit_policy`/`coordinate_offsets` value, non-boolean `allow_zero_offset`, or non-integer delta → config error.

### Linear tracking and expressions (M1; slot/coordinate-reference cases in M2; control/multi-counter cases in M4)
7. `COUNTER(stack)` reflects declared deltas through a push/pop sequence; verified via emitted operand bytes.
8. **Issue #18 scenario and scalar elapsed-coordinate behavior:** `:= COORDINATE()` declaration + a bare coordinate reference; inserting a new `push` between declaration and use changes the emitted offset byte by exactly one — no source edits to the reference line. Independently, a scalar `require-equal` cycle counter with `.start := COORDINATE(cycles, 0)` produces a `.start` reference equal to the hand-summed elapsed cost.
9. A coordinate reference inside an indirect-register operand (`[sp + .x]`) emits the same bytes as the hand-written literal.
10. `min_value` underflow (one pop too many) and `max_value` overflow → errors on the offending instruction's line.
11. General `#assert` accepts every `#if` comparison and the implied-nonzero form, works without flow counters, resolves preprocessor and built-in symbols, and accepts an optional plain or colored user error message. A flow assertion passing is silent; without a custom message, failure reports expected vs. actual.
12. `#set` re-anchors and downstream values reflect it.
13. A balanced path ending at a `flow_terminal` is silent and may use EOF or a later unreachable `#endtrack` as its lexical delimiter; a straight-line push leak → exit-imbalance error.
14. Under `exit_policy: balanced`, plain `#endtrack` checks against the initial value; under `exit_policy: none`, plain `#endtrack` closes without an equality check; explicit `exit=` checks exactly under either policy. A mismatch → error.
15. A live path reaching EOF without a terminal or `#endtrack` → error. EOF after every path has terminated is a valid lexical close. A second `#track` for the same lexically active counter before `#endtrack` → error even if all earlier paths terminated; the diagnostic identifies the still-open prior region and recommends inserting a lexical `#endtrack <counter>` after its last terminal.
16. Two counters (`stack`, `cycles`) advance independently from one instruction stream; each reports its own violations.
17. `unknown_instructions: ignore | warn | error` each behave as configured for an effect-less instruction inside a region.

### Label-scope awareness
18. Global label mid-region at non-entry value → warning; escalated to error under warnings-as-errors; file-scope (`_`) and named-scope labels likewise.
19. Global label at the entry value (multi-entry pattern) → silent.
20. Local (`.`) label at any tracked value → silent.
21. Propagation begins from the region entry and explicitly valued roots. A reachable label preceded by `#entry stack` then reuses its unique incoming value and becomes an independent root. An unreachable label requires `#entry stack value=N`; two value-less entry labels reachable only from each other both fail as unreachable. Consecutive `#entry stack value=2` / `#entry cycles value=0` directives attach to the same next compilable label and create roots for both counters. Missing `value=` on an unreachable label, conflicting incoming values for a value-less entry, duplicate entries for one counter, an intervening non-entry construct, or no following label → error.

### Path analysis (M5)
22. Diverge/rejoin with both paths balanced → silent.
23. One branch missing its pop, paths rejoin → join-mismatch error naming both values and both source lines.
24. One branch missing its pop, paths return separately (the spec's `divide` example) → exit-imbalance error on that path's `ret` only. A slot popped on one path and not another is invalid after the join; pushing a replacement slot to the same depth does not make a reference to it valid again.
25. Net-zero loop body → silent; net-positive loop body → join mismatch at the loop head.
26. Code after an unconditional `jmp` is not treated as fall-through; an unreachable line using `COUNTER()` → error.
27. Call composition: `call` with `stack_effect: +2` and explicit `flow_call_effects: {stack: 0}` leaves the caller's stack counter unchanged at fall-through; verified via a subsequent coordinate-reference operand byte. A second call variant with a target-independent nonzero summary such as `flow_call_effects: {stack: -1}` applies that declared net delta. Without a summary for the active class, the post-call value is unresolved. A convention whose effect varies by target remains unresolved until target-specific interprocedural summaries exist.
28. `indirect` jump inside an active region → error whether the counter is active or suspended; explicitly ending the region before the jump → accepted.
29. A branch targeting a label outside the region, entering after `#track`, or jumping across `#endtrack` → region-boundary error. A call into another region is accepted only at that region's initial entry or a label declared with `#entry`; targeting an interior label → error.

### Cycle counting, join policy, and edge deltas
30. An `interval` cycle counter rejects `:=` declarations and coordinate references because it has no scalar coordinate; interval timing instead uses a zero-based tracking window and `.min`/`.max` assertions.
31. `join: interval` class: an `if/else` whose arms differ in cycles is **silent** (no join-mismatch error); `#assert COUNTER(cycles).max <= N` passes when both arms fit and fails when one exceeds.
32. `join: require-equal` cycle class (constant-time): two paths with equal cost → silent; arms differing by one cycle → join-mismatch error naming both totals (the constant-time-violation case).
33. Edge-dependent delta: a conditional branch with `cycles: { taken, fall_through }` contributes the correct cost on each edge; the interval hull at the rejoin reflects both.
34. Using an `interval`-class counter's bare `COUNTER()` as an operand value → error; using `COUNTER(cycles).min` / `.max` in a range `#assert` → accepted. Until a promoted M6 specification defines explicit hull semantics, `#set`, `#suspend`, or `#resume` on an interval counter → unsupported-operation error. A timing counter with an unresolved named-callee summary cannot be used in an operand, bound check, or precise timing assertion.

### Indeterminate state
35. Runtime-length push loop with no acknowledgement → join-mismatch error (the default catches it).
36. `#suspend` silences tracking; `COUNTER()` or coordinate reference, new `:=` coordinate declaration, or `flow_terminal` instruction while suspended → errors.
37. `#resume` to a pre-suspension coordinate restores tracking but invalidates pre-suspension coordinates; referencing one of those symbols → error. A slot popped below its coordinate and then replaced by a new push at the same depth remains invalid (it is not resurrected).

### Subroutine arguments across the return address
38. Callee with `init=0 exit=0` and `.arg := COORDINATE(stack, 3)`: a `.arg` reference starts at 3 and accounts for callee pushes. A `ret` configured with `flow_terminal.stack: before_effect` requires the callee-owned counter to equal 0 before its physical −2 return-address effect; omitting a local pop fails at the terminal. Replacing the declaration with ordinary `.arg = 3` makes a `.arg` reference resolve to the frozen constant 3 — ordinary symbols outrank nothing here; there is simply no coordinate — so the flow-tracked adjustment is silently absent. The `:=` declaration is what opts a symbol into offset tracking.

### Entry modes
39. `#track stack mode=called` applies the class's configured `init`/`exit`; explicit `init=`/`exit=` on the same directive override the mode's values; `#track` with neither uses `default_init`.
40. Jumped-to routine: `#endtrack` (exit check passing) immediately before the unconditional `jmp` out → silent; the same `jmp` with the region still open → no-clear-end error.
41. Tail call: `mode=called` routine closing with `#endtrack exit=0` before a `jmp` to another subroutine → silent; the same tail `jmp` with an unbalanced frame → exit-mismatch error.
42. `#track mode=` naming a mode not declared in the class's `entry_modes` → error.

### Counter classes and instances
43. `#track stack` with no `as=` creates a counter named after its class; all references by class name work (the common-case ergonomics test).
44. Two concurrent instances of one class (the overlapping cycle-windows example): one instruction's declared cost accrues to both; each `#endtrack exit=` is checked independently.
45. Opening a counter whose name is already active → error; two concurrent instances with distinct `as=` names → accepted.
46. A `flow_terminal` instruction reconciles every active instance of each mapped class in that class's configured `before_effect` or `after_effect` order, then terminates those reaching paths without ending lexical extent. An active instance of a *different* class is not reconciled by it — but it cannot cross the return either: a live unmapped instance at the terminal is an error naming the counter and recommending `#endtrack` before the transfer, and mapping that class `after_effect` on the return counts the return's own cost while ending its path (clarified 2026-07).
47. `#track` naming an undeclared class, or `COUNTER()` naming an inactive instance → errors.

### Interaction with existing features
48. Flow counter directives inside an inactive `#if` block are ignored entirely (no region opened).
49. `#mute` does not affect tracking (analysis follows compiled code, not emitted code).
50. Multiple instructions on one source line apply their effects in order.
51. Instruction macro inside a region contributes the aggregate effect and CFG behavior of its expansion (e.g., a macro expanding to two `push`es moves `stack` by +2); a constituent `flow_terminal` ends only the reaching path. Declaring instruction-level flow metadata (`flow_effects`, `flow_terminal`, `flow_transfer`, `flow_target_operand`, or `flow_call_effects`) on a macro definition → configuration error.
52. A global counter remains available through an `#include`; a file-scoped counter does not project into included-file lines and auto-closes with a warning at the file boundary; `.org` or a memory-zone change likewise auto-closes an active region with a warning. Any live path reaching the automatic boundary receives its applicable exit check; paths already closed by terminals are not checked twice.

### Required configuration metadata (fail loud)
53. `#track X` where `X` is declared in `flow_counters` but no instruction populates `X`'s `source` field (and no `flow_terminal` maps `X`) → error (declared-but-inert class); the counter is never silently tracked as a no-op. A `source` path pointing at a non-numeric field → configuration error.
54. Any reachable selected instruction variant lacking an explicit `flow_transfer` (including `none` for ordinary instructions) while a counter is active → error naming the instruction; missing metadata is never interpreted as straight-line. Lexically enclosed but unreachable instructions do not trigger completeness checks unless made reachable by `#entry`.
55. Error timing: malformed `entry_modes` and internally invalid transfer/target metadata error at config load; inert-class, exhaustive `flow_transfer` coverage within an active region, and unavailable call-summary errors are usage-time.

### Feature enablement (usage-gated)
56. ISA with **no** `flow_counters` section + source using a flow-counter construct (`#track`, `:=`, `COUNTER()`, etc.) → error ("instruction set does not enable flow counters"), regardless of the flow-check switch; the error fires only because the construct was used.
57. ISA with no `flow_counters` section + source using no flow-counter construct → assembles byte-identically to the same source/ISA pre-feature (feature fully dormant).
58. ISA enabling classes `A` and `B`; source tracks only `A` → no diagnostic about `B`, even if `B` is inert or never used (enabled-but-unused class imposes no obligation).

### Operand-dependent and macro-aggregate effects
59. `add sp, 4` with `flow_effects: { stack: -ARG(0) }` → `stack` decreases by 4; a subsequent coordinate-reference/`COUNTER()` value reflects it. `add sp, FRAME_SIZE` resolves identically. `ARG(0)` indexes the selected variant's first source-written operand; a register selector is runtime-valued rather than its encoded integer, an out-of-range index is a config error, and a macro constituent indexes its own post-expansion operands.
60. `add sp, a` (runtime register operand) inside a region tracking `stack` → counter indeterminate: error if `COUNTER()` or a coordinate reference is used while not suspended; accepted under `#suspend`.
61. Macro expanding to `push`/`push` contributes net `stack` +2 (aggregate of expansion); a macro constituent that is `flow_terminal` ends only its reaching path. A macro definition declaring any instruction-level flow metadata → configuration error.

### Source field binding
62. A counter reading `source: documentation.cycles` accumulates each instruction's `documentation.cycles` integer; a class omitting `source` reads `flow_effects.<class>`; two classes (`cycles`, `ct_cycles`) reading the same `source` field both track it, differing only by `join`.
63. An instruction missing the `source` field of an actively-tracked class is handled per that class's `unknown_instructions` (so `error` enforces complete data, e.g. every instruction must carry `documentation.cycles`).

### Branches, loops, and path count
64. Edge-keyed delta: a `conditional` branch with `cycles: {taken, fall_through}` contributes the right cost on each edge; the interval hull at the rejoin reflects both. The same edge-map representation is legal for a `require-equal` class and produces a join mismatch unless later effects reconcile the paths; a scalar applies equally to all outgoing edges.
65. Multi-counter branch: one branch carrying an edge-map for `cycles` and a scalar for `stack` updates each counter from its own source field independently.
66. Net-zero loop body (`require-equal`) → silent; net-nonzero loop body → join-mismatch at the loop head; runtime-length accumulating loop under `#suspend` → accepted.
67. `interval` counter across an unbounded loop → WCET reported as unbounded (widening terminates the worklist); the same natural loop with `#loop count=N` immediately before its next compilable header label → finite `body × N` contribution. A non-label attachment, a label that is not a same-region back-edge target/natural-loop header, an intervening non-comment construct, or `count=<runtime expr>` → error.
68. `k` consecutive balanced branches assemble in time linear in lines (no 2ᵏ blow-up); `#assert` does not silence a join mismatch, while an explicit `#set` on the relevant predecessor state can re-anchor at the programmer's responsibility; interior `COUNTER()` inside a `#loop`-counted nonzero loop → indeterminate error.

### Tooling collateral (M1 and per-milestone)
69. At **each milestone**, extensions generated from a flow-enabled ISA include every **then-shipped** flow directive, declaration, and expression form in all three grammars (VS Code, Sublime, Vim), with hover docs present; extensions generated from a non-enabled ISA contain none of the capability-gated flow directives, declarations, or operators. The always-present `__FLOW_COUNTERS_AVAILABLE__` built-in constant and its hover documentation are the sole flow-named exception. General `#assert` highlighting and hover documentation appear for every ISA, while its flow operands use flow-specific captures only in enabled grammars. Every shipped directive/operator/declaration has a `directive_docs.py` entry (enforced by the existing docsgen test). The flow fixture matrix grows as syntax ships: M1 (`#track`, `#endtrack`, `COUNTER()`); M2 (`:=`, `COORDINATE()`, bare coordinate references); M4 (flow-aware `#assert`, `#set`, `#suspend`, `#resume`); M5 (`#entry`); M6 (`COUNTER(x).min` / `.max` assertion forms); M7 (`#loop`).
70. **Analysis-record preservation and gating (M0):** an ISA declaring `flow_counters` preserves the complete immutable record for every selected constituent, including under `--no-flow-checks`, because an emitted flow-value dependency may require graph analysis after source parsing. A compile against an ISA with no analysis feature retains zero analysis records and performs no flow-usage traversal. Both modes produce baseline-identical output for source that does not request a flow-derived value. A register's emitted selector is never exposed as a semantic `ARG()` value.
71. **Straight-line coordinate invalidation (M2):** after a positive-offset slot coordinate is declared, a pop across its saved coordinate followed by a replacement push to the same counter value leaves a `slot` reference invalid; a negative-offset coordinate receives the mirrored test. With `allow_zero_offset: false`, reaching the saved coordinate itself invalidates the slot; with it enabled, only crossing beyond does. The original slot is never resurrected in either orientation.
72. **Expression-context isolation (M1):** `COUNTER()` in a fixed-width operand or fixed-size data value is accepted; the same operator in `.org`, alignment, fill count, conditional preprocessing, or instruction/operand-form selection → flow error before it can influence layout.
73. **Physical fall-through resolution (M5):** a non-transfer instruction's fall-through successor is resolved at `address + word_count`, even when that instruction appears earlier in source; emitted data, an address gap, an ambiguous same-address group, or a region boundary at that address is diagnosed rather than skipped to the next source/executable instruction.
74. **Coordinate declaration and symbol identity (M2):** within a valid local-label region, `.x := COORDINATE(stack, 1)` is accepted and a `.x` reference resolves that local slot. A distinct global `x` does not collide with it, and writing bare `x` does not silently resolve `.x`. A dot-prefixed coordinate before the first non-local label, or after `.org` but before the next non-local label, remains invalid under the existing local-scope rules. `.x := 4`, `.x := COUNTER(stack)`, `.x := 2 * COUNTER(stack)`, and `.x := COORDINATE(stack, COUNTER(other))` are rejected; `.arg := COORDINATE(stack, 2)` is accepted. A class configured with `coordinate_offsets: positive` rejects a negative declaration offset, `negative` rejects a positive one, and `both` accepts either nonzero sign. Zero is accepted by default and rejected when `allow_zero_offset: false`. `.x = COUNTER(stack)` remains invalid as an ordinary-constant assignment of a flow value.

### Command-line flow-check control
75. With no flag and with explicit `--flow-checks`, the same flow-enabled source produces identical bytes and identical diagnostics; enabled is the default.
76. Under `--no-flow-checks`, annotation-only flow source produces byte-identical output without bounds, exit-contract, flow-assertion, or warning diagnostics. General assertions still execute. Malformed flow source and any flow syntax used against an ISA without `flow_counters` remain errors.
77. Under `--no-flow-checks`, an instruction operand or fixed-size data value containing `COUNTER()` or a declared-coordinate reference automatically triggers flow propagation and resolves to the same emitted value as the default checked compilation. A requested value that is structurally ambiguous, indeterminate, inactive, or otherwise unsafe still errors; no numeric fallback is emitted.
78. Under `--no-flow-checks`, a coordinate declaration required by an emitted coordinate reference is created and resolved normally. Unused declarations remain zero-width and do not force graph propagation.
79. Under `--no-flow-checks`, flow configuration validation remains active. Verification-only usage checks are suppressed, while structural checks required to resolve an emitted value remain active. Listing output omits the flow column.
80. **Terminal paths versus lexical extent (M5):** two balanced `ret` paths followed by EOF succeed without `#endtrack`. If another global/file/named label follows before `#endtrack`, that unreachable label receives a flow warning; placing an unreachable `#endtrack` after the last terminal suppresses it and delimits the region without a second exit check. A live path falling through to that delimiter still receives its normal exit check. Starting another same-name `#track` instead of inserting the delimiter errors with the actionable `#endtrack <counter>` guidance required by rule 1.
81. **Inspectable listing transitions and coordinates (M5):** listing-format pretty print adds a `flow` column whenever analysis produces at least one counter transition or coordinate observation. A changing row shows its input and output values (`stack=0 → 1`). When one instruction changes multiple counters, the first appears on the source row and each additional counter appears in name order on a continuation row. Source fields are blank on that continuation row, but when the machine-code bytes also require continuation, the next byte chunk and next flow annotation share the same physical row rather than creating redundant rows. A source-level instruction macro shows the aggregate transition of all its constituents on its invocation row (`stack=0 → 3` for three pushes). Opening and closing use the symmetric forms `stack=entry → 0` and `stack=0 → exit`, while suspension and resumption are transitions as well. A successful coordinate declaration shows its resolved declared offset (`.arg=3`), and each `.arg` reference shows its current resolved offset (`.arg=4` after one push). Other rows whose flow state does not change leave the column blank. Source with no transitions or coordinate observations retains the pre-feature listing layout.

### Instance bounds (`#track min=`/`max=`, M5)
90. `#track stack max=<N>` errors on the offending instruction's line the moment any state exceeds `N`, exactly as a class `max_value` would; `min=` is symmetric. The bound values accept every compile-time constant kind, including a memory-map-derived label expression such as `max=STACK_TOP - heap_end`, resolved once at the `#track`.
91. **Tighten-only:** with a class `max_value` of 254, `#track stack max=64` enforces 64; `#track stack max=1000` → error on the `#track` line stating the instance bound exceeds the class bound; symmetric for `min=` below the class `min_value`. On a class with no declared bound, the instance bound is simply enforced.
92. Instance bounds are enforced at every state-producing point — instruction deltas, `#set`, `#resume`, `#entry` root values, and the resolved `init=` — and independently per concurrent instance: two instances of one class with different `max=` values each report against their own bound.
93. Under `--no-flow-checks` instance bounds are parsed but not enforced; they never appear in generated ISA documentation; the `#track` hover/directive documentation and wiki syntax page document the parameters (collateral definition-of-done).
94. Contradictory effective instance bounds (`min > max`, including after merging with class bounds) → a direct error on the `#track` line naming both effective limits.

### Counter-anchor invalidation (M5)
95. A class with `invalidate_on_write: [A]` and an instruction with `flow_write_operands: [N]` becomes indeterminate when source operand `N` resolves to `A`; the listing shows `<counter>=value → ?`, precise reads fail until `#resume` — and every diagnostic issued because the counter is indeterminate through invalidation (rather than an explicit `#suspend`) identifies the invalidating write or instruction and its source line — and all prior coordinates remain invalid afterward.
96. A compile-time write target proven different from every watched address leaves the counter precise. A runtime or otherwise unresolved target is conservatively treated as possibly matching and invalidates it.
97. Invalidation composes through instruction macros: a macro carrying no flow metadata but expanding to a watched write has the same result as writing the real instruction directly. The annotated and hand-stripped sources remain byte-identical.
98. A non-list/duplicate/out-of-range `invalidate_on_write` address, or a non-list/duplicate/out-of-range `flow_write_operands` source index, → config-load error regardless of the flow-check switch.
99. An instruction or selected variant with `flow_invalidates: [stack]` unconditionally makes every active `stack` instance indeterminate, invalidates its coordinates, and requires `#resume` before precise use. The behavior composes through macros. A non-list value, duplicate class, or undeclared class → config-load error regardless of the flow-check switch.
100. `__FLOW_COUNTERS_AVAILABLE__` is always defined during an ISA-backed compilation: it is numeric `1` when the ISA configuration contains `flow_counters` and numeric `0` otherwise, works in both `#if` and `#elif`, and is included in generated editor syntax as a built-in constant. A flow-capable ISA produces the same selected branch with default/explicit `--flow-checks` and `--no-flow-checks`; only changing ISA capability changes the symbol. Because it is always defined, `#ifdef __FLOW_COUNTERS_AVAILABLE__` is true in both capability states and is not the supported availability test.

### Generated ISA documentation (M5.1)
82. **Top-level section:** `bespokeasm docs` output for a flow-enabled ISA contains a Flow Counters section, after Operand Sets and before Instructions, with one subsection per declared class in declaration order showing title/description, the derived properties table (including the defaulted `flow_effects.<class>` source field spelled out), the entry-modes table with descriptions, and the derived terminal-instruction list with reconciliation order.
83. **Docs inertness:** documentation generated from an ISA without a `flow_counters` section is character-identical to pre-feature output, apart from the single terminating newline the generator appends to non-empty output (the POSIX text-file convention); adding a `flow_counters` section plus per-instruction effects changes only the new section and Counter rows, nothing else.
84. **Delta rows:** an instruction with a `+1` stack effect gains a `Counter | stack | +1` row; a declared-zero delta and an undeclared class produce no row; a class with `source: documentation.cycles` produces per-instruction rows from that shared field; an instruction with no hand-authored `modifies` but a nonzero delta still renders a Modifies section containing only Counter rows, placed after any hand-authored rows. A config-valid edge map has an intentional declaration-ordered presentation such as `taken +3 / fall-through +2`, with underscores in edge names rendered as hyphens; it never leaks a host-language dictionary representation.
85. **Terminal and call rows:** a `before_effect` return renders both its physical delta row and a terminal row stating pre-effect reconciliation and path termination; a `call` with `flow_call_effects` renders the caller-visible summary row, including a nonzero (callee-pops contract) declaration.
86. **Variant merge:** where a selected variant overrides flow metadata, per-version Modifies rows reflect the deep-merged effective semantics; an alias renders identically to its root mnemonic.
87. **Non-scalar delta presentation:** operand-dependent deltas render the configured source expression (`−ARG(0)`), not a computed number; edge maps render the stable named-edge presentation specified by case 84.
88. **Config documentation:** `documentation.title`/`description` on a class and `description` on an entry mode appear in the output; a class without `documentation` falls back to its name silently; a non-dict `documentation` value errors at config load.
89. **Hover parity:** per-instruction hover markdown for a flow-enabled ISA includes the same Counter rows through the shared rendering path; hover output generated from a non-flow ISA contains none (extending the case-69 fixture matrix).

## Implementation Phasing
The work splits into small vertical slices ordered by dependency. **M0–M5.1 are the committed, normative specification**: each is independently shippable and gated by its listed acceptance tests. **M6–M7 are provisional design sketches**, retained to show how timing intervals and richer effects may extend the core but explicitly revisited after M5.1 ships; their listed acceptance cases are design targets, not release commitments, until the milestone is promoted to normative status. The coarse stages map as: **analysis substrate = M0**, **linear tracking = M1–M4**, **committed path analysis = M5**, **generated ISA documentation = M5.1**, **provisional timing/interval analysis = M6**, **provisional richer effects = M7**.

Each milestone names an **acceptance demo**: a concrete, runnable scenario with an observable outcome that proves the milestone's goal. Development-only milestone harnesses live under `dev/flow-counters-mN/`, not `examples/`; the latter is reserved for bona fide instruction sets and their programs. The harnesses double as end-to-end integration tests — a durable, re-runnable artifact per milestone, not just a green unit-test suite.

1. **M0 — Analysis substrate + inertness proof.** When the ISA declares `flow_counters`, retain an immutable analysis record for every selected instruction variant and macro constituent: merged instruction/variant semantics, source and canonical mnemonics, typed parsed/matched operands (distinguishing compile-time semantic values from register encodings), parsed operand expressions, and stable source identity including an ordinal for multiple instructions on one source line and macro-constituent identity. Retain these records under either flow-check setting because dependency-driven value resolution is decided after parsing; retain none for an ISA with no analysis feature. Add deferred flow-expression recognition plus context tagging, a source-order executable-node index, and the `flow` diagnostic category. *Delivers:* the data needed by later milestones while leaving non-flow ISAs dormant. *Gated by:* 2, 4–6, 70. **Demo:** inspect complete records for a flow-enabled program containing a variant, symbolic target, two same-line instructions, and a macro; verify byte identity with checks on and off. Re-run with a non-flow ISA; verify records are absent and bytes remain identical.
2. **M1 — Single-counter linear core + tooling pipeline.** Ship `#track` / `#endtrack`, scalar `COUNTER()` in allowed fixed-width/fixed-size value contexts, constant deltas, `min`/`max` bounds, `exit_policy`, applicable exit checks for straight-line regions, the always-defined `__FLOW_COUNTERS_AVAILABLE__` ISA-capability symbol, and the compile options `-a`/`--flow-checks` and `-A`/`--no-flow-checks` (checks enabled by default). Disabled-check mode suppresses verification but automatically runs the value-resolution pass when emitted bytecode depends on `COUNTER()`; it does not change the capability symbol. Every instruction in an active region must explicitly declare `flow_transfer`; a variant other than `none` is a hard "path analysis not yet available" error until its behavior is shipped (M3 permits the specifically supported unconditional terminal, M5 handles general CFG transfers). Ship the editor/documentation pipeline with this first visible syntax: central keyword entries, hover docs, per-ISA grammar gating, generated-extension verification, CLI help, wiki, and changelog. *Delivers:* controllable straight-line depth/cycle tracking that changes no layout. *Gated by:* 1, 3, 7, 10, 14, 15, 17, 48–50, 54, 56–58, 69, 72, 75–77, 79, 100. **Demo:** assemble a straight-line routine using `COUNTER(stack)` in a fixed-width operand; its byte and hand-stripped twin are identical, while an explicit `#endtrack` mismatch, a `min_value` underflow, and a layout-affecting `COUNTER()` use each fail on the relevant line. Re-run with `--no-flow-checks`; observe the same operand value with no verification diagnostics or flow listing column. Generate an extension from the same flow-enabled ISA and verify `#track`, `#endtrack`, `COUNTER()`, and `__FLOW_COUNTERS_AVAILABLE__` are highlighted with hover documentation.
3. **M2 — Stack slot labels (closes issue #18 for straight-line code).** Add scoped counter-coordinate declarations (`.x := COORDINATE(stack, 1)` and `.arg := COORDINATE(stack, 3)`), the per-class `coordinate_offsets: positive | negative | both` and `allow_zero_offset` policies, bare coordinate-reference resolution, and direction-aware straight-line permanent dead-coordinate invalidation. The `:=` parser is distinct from ordinary `=` / `EQU` constant assignment and preserves normal symbol-scope identity. *Delivers:* the headline issue-#18 capability without waiting for CFG analysis. *Gated by:* 8, 9, 71, 74, 78. **Demo:** a Minimal 64x4-style subroutine declares caller-owned parameters directly at `sp+3` and `sp+7`, then accesses them with `LDS <coordinate>` / `STS <coordinate>`; inserting one local four-byte push changes those emitted offsets to 7 and 11 without editing either access. Its stack policy also rejects `sp+0`. Popping a named slot and pushing a replacement at the same depth still makes a `.x` reference fail. A scalar cycle-counter variant confirms that a `.start` reference equals hand-summed elapsed cycles. Under `--no-flow-checks`, the same coordinate operands resolve and emit identical values without optional verification output.
4. **M3 — Linear subroutine and frame ergonomics.** Add unconditional `flow_terminal` processing with mandatory per-class `before_effect` / `after_effect` reconciliation order, entry modes, called-entry argument slots, and compile-time-constant operand-dependent deltas (`add sp, N`). For a `before_effect` terminal that returns control by restoring a stack-saved execution address, the region begins at zero, must return to zero before the terminal instruction, and then ends without propagating the instruction's caller-owned stack effect inside the callee-owned counter. Calls, jumps, tail calls, and conditional terminals remain transfer-containing regions until M5. *Delivers:* straight-line called routines with direct physical parameter coordinates and routine-owned stack-balance checks. *Gated by:* 5, 13, 38–40, 42, 59. **Demo:** assemble a straight-line called routine that (1) selects an entry mode with a routine-owned `init=0 exit=0` contract, (2) declares caller-owned parameter coordinates beyond a physically present return address, (3) allocates a local stack frame and accesses those parameters through unchanged `LDS`/`STS` coordinate-reference expressions, (4) tears down the frame with an `add sp, N` instruction whose delta is derived from its compile-time operand, and (5) ends at an instruction configured to reconcile before returning control through a stack-saved execution address. Verify byte identity with a hand-resolved twin, and verify that a wrong frame adjustment fails at the terminal.
5. **M4 — Manual linear control + concurrent counters.** Add general-purpose `#assert` with `#if`-equivalent conditions and optional colored user messages, make it flow-aware for scalar checkpoints, add scalar `#set`, scalar `#suspend` / `#resume` for straight-line indeterminate spans, and add concurrent instances/classes with `as=` naming. Interval re-anchoring/suspension is explicitly unsupported; full path-sensitive scalar suspended-state checking waits for M5. Parse-time flow-expression context validation becomes directive-aware: it accepts flow expressions in `#assert`/`#set`/`#resume`, continues to reject `#if`-family and other layout/selection contexts, and ignores all flow syntax inside inactive conditional blocks as required by acceptance case 48. General assertions remain active when flow checks are disabled. *Delivers:* reusable compile-time invariants, explicit programmer control, and overlapping measurement windows. *Gated by:* 11, 12, 16, 36, 37 (straight-line invalidation), 43–47. **Demo:** one routine tracks `stack` and two overlapping scalar measurement windows; each instruction updates active instances independently, an assertion and re-anchor affect only the named counter, and a suspended straight-line span rejects `COUNTER()` until resumed.
6. **M5 — CFG and path-consistency core.** Build an analysis-neutral structural CFG from exhaustive `flow_transfer` metadata and explicit `flow_target_operand`, resolve physical fall-through at `address + word_count`, and implement a clean but concrete `require-equal` flow-counter worklist over it. Add lexical-region delimiting, label→executable-node resolution, region-boundary validation, grouped/explicit-value `#entry` roots, declared target-independent call summaries, tail-call handling, complete scalar suspended-state analysis, per-path terminal checks, join mismatches, net-zero loop checks, fall-through-into-data/gap/ambiguity errors, indirect-transfer errors, label-scope/unreachable-entry warnings, path-aware slot invalidation, listing-format flow-transition and coordinate-value annotations, per-instance `#track min=`/`max=` bounds (the memory-map complement to class bounds; see the *Tracking Regions* `#track` bullet), watched memory-write invalidation through `invalidate_on_write` plus per-instruction `flow_write_operands`, and unconditional anchor replacement through `flow_invalidates`. Target-specific call effects remain unresolved; a future interprocedural phase is not part of this commitment. *Delivers:* branchy stack routines are genuinely verified without prematurely generalizing the propagation engine. *Gated by:* 18–29, 35, 37 (path-sensitive portion), 41, 54, 66, 68, 73, 80, 81, 90–99. **Demo:** Example C reports the leaked push; after fixing it, its terminal paths are closed and a trailing lexical-only `#endtrack` cleanly delimits the next routine. Omitting that delimiter warns on the next externally visible label. The listing exposes each instruction that changes the stack, each coordinate declaration/use value, and leaves other unchanged rows blank. The demo also covers explicit unreachable `#entry` values, a runtime-length loop, an indirect jump, physical fall-through into data, a balanced tail call, a macro whose expanded memory write invalidates a watched stack-pointer anchor until `#resume`, and a macro whose expanded instruction directly invalidates the anchor.
7. **M5.1 — Flow-counter documentation generation (first public release, with M5).** Extend `bespokeasm docs` (and the shared per-instruction hover rendering) to surface the ISA's flow-counter contract. This milestone adds no source syntax and no assembler behavior; its guiding principle inverts the `documentation.modifies` precedent — `modifies` is hand-authored prose the assembler never checks, while the flow rows are **derived from the machine-checked metadata** (`flow_effects`/`source`, `flow_terminal`, `flow_call_effects`, and both invalidation forms), so generated documentation can never drift from what the analyzer enforces. Ship: (1) a top-level **Flow Counters** section, placed after Operand Sets and before Instructions, with one subsection per declared class in declaration order showing `documentation.title` (fallback: class name) and `documentation.description`, a derived properties table (source field with the `flow_effects.<class>` default spelled out, `min_value`/`max_value`, `default_init`, `exit_policy`, `coordinate_offsets`/`allow_zero_offset`, `unknown_instructions`, `invalidate_on_write`, `join`), an entry-modes table (mode | init | exit | description) when declared, and the derived list of `flow_terminal` instructions with reconciliation order; the section documents ISA-specific facts only, with one boilerplate sentence linking the general feature documentation. (2) Generated **Counter rows** in each documented instruction's Modifies table (Type `Counter`, Target = class name, description derived from metadata): a *delta row* per class whose effective source-field value is nonzero — signed value, the operand-dependent source expression verbatim (`−ARG(0)`), or a declaration-ordered edge map such as `taken +3 / fall-through +2`; a *terminal row* per class mapped in `flow_terminal`, stating path termination and before/after-effect reconciliation; a *call-summary row* when `flow_call_effects` is declared, stating the caller-visible net effect; a *direct-invalidation row* for each class in `flow_invalidates`; and a *watched-write invalidation row* for `flow_write_operands` paired with a class's watched addresses. Declared-zero deltas and undeclared classes render no delta row (silence means "no impact": stack tables stay clean while a `source: documentation.cycles` class naturally yields a row per instruction). Counter rows render even when the instruction declares no hand-authored `modifies`, appear after hand-authored rows, reflect the effective merged variant semantics per version wherever variants differ, and apply to aliases via their root. `flow_transfer` is deliberately not rendered. (3) Consume `flow_counters.<class>.documentation` and a new optional per-entry-mode `description` string; malformed `documentation` is a config-load error, absence never is. All output is gated on the `flow_counters` section: documentation from a non-flow ISA is character-identical to pre-feature output apart from the single terminating newline the generator appends to non-empty output (the POSIX text-file convention); the `docs` command needs no static-analysis switch, and flow-metadata config errors fail documentation generation exactly as they fail compilation. *Delivers:* generated ISA documentation and editor hover that state each counter's contract and each instruction's counter impact from the same metadata the analyzer enforces. *Gated by:* 82–89, 95–99. **Demo:** run `bespokeasm docs` against the M5 harness ISA and verify the Flow Counters section, a `+1` and a `−ARG(0)` delta row, the `rts` terminal row, the call-summary row, and both invalidation row forms; run it against a non-flow ISA and diff against pre-feature output — identical apart from the terminating newline.
8. **M6 — Timing and interval analysis (provisional; revisit after M5).** Design target: add `join: interval`, edge-keyed deltas, widening for unbounded loops, range assertions, and constant-time checking. Carry unresolved named-callee summaries so timing claims cannot silently exclude callees, and distinguish the two reasons a summary is unresolved: *interprocedurally resolvable* (the callee body is in the program; a future phase could verify it) versus *permanently external* (the target address holds no program content — a ROM routine — so no future analysis can ever inspect it). The external case motivates **target-keyed call summaries**: a way to declare a per-callee caller-visible effect (for example `flow_call_effects` keyed by callee name or address, `_Print: {cycles: 200}`) distinct from the per-instruction convention, because on ROM-serviced platforms (MinOS, monitor-based systems) *every* OS call is permanently external and would otherwise leave timing unresolved forever. Before promotion, also decide: whether interval `#set`/`#suspend`/`#resume` remain unsupported or receive explicit hull semantics (no implicit point-collapse is assumed), and whether macro-invocation operands observe the entry *hull* — the scalar rule (revised 2026-08) resolves macro operand flow values at invocation entry, and the interval design must state its analogue explicitly rather than inherit per-constituent behavior by accident. *Potential delivery:* sound branch-sensitive WCET/constant-time analysis for regions without unresolved callees. *Candidate gates:* 30–34, 64, 65, 67 (unbounded case). **Candidate demo:** a branchy routine passes or fails `#assert COUNTER(cycles).max <= N`; Example F catches unequal path timing; a timing assertion after an unresolved call is rejected.
9. **M7 — Rich effects and finite loops (provisional; revisit after M5/M6).** Design target: add structural operand-dependent deltas (`COUNT(0)`, page-cross penalties), runtime-operand handling, conditional terminals, validated natural-loop `#loop count=/max=` annotations, and finite post-loop interval results. Two richer *transfer* shapes now have named motivating instructions from the shipped example ISAs: **target-transform expressions** (something like `flow_target_expression`) for transfers whose destination is a function of the operand rather than the operand's value — the 8085 `rst` jumps to `ARG(0) * 8`, and `rstv` conditionally calls fixed `0x0040` — and a **call-with-inline-arguments** declaration for calls whose physical fall-through lands in trailing data that the callee skips by rewriting its return address (the MinOS `jps _Print "text"` idiom, common across retro monitors); today such calls can only live outside a tracked region. The suspended-with-bounds refinement (see *Suspension*) is validated by a shipped example: `cstr_reverse` in the Minimal 64x4 stringlib suspends across push/pop loops whose depth is runtime-dependent but bounded by the 255-character string limit — a bound `#loop` cannot express because the trip count is runtime data. *Potential delivery:* bounded-loop timing and richer ISA-specific effects. *Candidate gates:* 51, 60, 61, 67 (bounded case), and extensions of earlier groups. **Candidate demo:** Example E computes a finite bound for `#loop count=100` and becomes unbounded when the annotation is removed; invalid loop attachments fail; `pushm {r0-r3}` produces expected offsets, and a macro expanding to two pushes emits byte-identical operands for constant and coordinate arguments under the invocation-entry observation rule (constituent effects apply sequentially; operand flow values observe the invocation entry).

**Collateral definition-of-done (every visible milestone from M1 on): new language surface ships with its collateral.** M1 builds the pipeline with its first directives/operators, the `__FLOW_COUNTERS_AVAILABLE__` built-in capability symbol, and the flow-check CLI switch; afterward, any milestone that adds or activates source syntax, an expression form, or a config key must ride it in the same release: keyword-registry entries (`keywords.py`), hover/doc entries (`directive_docs.py`), regenerated-extension verification, wiki section, and CLI documentation where applicable. Concretely: `:=`, `COORDINATE()`, and bare coordinate references land with **M2**; `#assert`/`#set`/`#suspend`/`#resume` with **M4**; `#entry` with **M5**; interval selectors / assertion forms with **M6**; and `#loop` with **M7**. Config-key documentation (`coordinate_offsets`, `allow_zero_offset`, `join`, `entry_modes`, call summaries, edge maps) lands with the milestone that activates each. **M5.1** ships no source syntax, so no keyword/grammar work applies; its collateral is the wiki page describing generated documentation (which gains a Flow Counters subsection) and the config-file wiki page's entries for the now-consumed class `documentation` and entry-mode `description` keys. The `#track` instance-bound parameters `min=`/`max=` land with **M5** (cases 90–93) and ride the existing `#track` collateral: updated hover/directive documentation and wiki syntax text; no new reserved words, but every `#track` parameter keyword (`as=`, `mode=`, `init=`, `exit=`, `min=`, `max=`) receives the same parameter-keyword grammar capture as `as=`, with identifier-valued parameters (`as=`, `mode=`) also capturing their value, so parameter names never fall through to the generic label-usage scope. The changelog records major user-usable flow-counter functionality as it becomes available, without becoming a milestone-by-milestone implementation ledger. A milestone is not done while its syntax is invisible to the editors.

Sequencing notes:
* M0 is deliberately testable even though it adds no source syntax: its byte-identical compile plus gated retained-record integration test permits later milestones to rely on rich records without imposing their memory/time cost on dormant builds.
* M5.1 touches only `docsgen`/hover rendering and consumes metadata that already exists at M5, so it has no assembler-behavior risk and may ship in the same release as M5; the first public release comprises M0–M5.1.
* M4's multi-counter support may prove nearly free atop M1 (a loop over active instances) and could merge earlier; it is kept separate to keep M1 minimal.
* Real verification of branchy code — i.e., every practical subroutine — arrives at committed **M5**; M1–M4 are intentionally linear-only. Issue #18's straight-line request closes at **M2**. M6/M7 do not block completion of the committed stack-analysis feature.

## Architecture Anchors
* **Config parsing/validation:** `AssemblerModel` (`src/bespokeasm/assembler/model/__init__.py`), `_validate_config()`.
* **CLI control:** add `-a`/`--flow-checks` and `-A`/`--no-flow-checks` to the `compile` command in `src/bespokeasm/cli.py`, defaulting checks to enabled, and forward the boolean through `CommandHandlers.compile`, `_compile_handler`, and the `Assembler` constructor. Legacy no-subcommand invocation inherits the same compile option because it is routed to `compile`.
* **Directive parsing:** new preprocessor line types alongside `#create-scope` et al. in `line_object/preprocessor_line/factory.py`.
* **Tracking pass:** a *separate* analysis pass in `Assembler.assemble_bytecode()` (`src/bespokeasm/assembler/engine.py`). It must run after first-pass address assignment (so labels and physical fall-through addresses resolve) but **before mutating the source-ordered collection with the existing `compilable_line_obs.sort(key=address)` step**. The analysis retains source order for directives, lexical region membership, and diagnostics, while CFG fall-through edges use physical address adjacency (`address + word_count`). It must not share mutable state with, or alter, the address-counter / `MemoryZoneManager` advance path (see *How Much Should They Share?* and the *Static Analysis Only* guarantee). The pass runs when checks are enabled and flow syntax is present, or when emitted bytecode requires a flow-derived value. In dependency-only mode it suppresses verification diagnostics and annotations.
* **Diagnostics:** `DiagnosticReporter` (`src/bespokeasm/assembler/diagnostic_reporter.py`) with a new `flow` category added to warnings-as-errors elevation; lines are identified by the existing `LineIdentifier` (filename + line number) every line object already carries.

## Architecture Changes Required
A code-level review of the current assembler establishes that the pass scaffolding, diagnostics, label scope, expression parser, and preprocessor-directive system are all either ready or need only small additive changes — but two structural facts about the codebase drive real work. First, the assembler is a *generate-bytecode-then-discard* pipeline: once an `InstructionLine` produces its `AssembledInstruction` (bytecode parts + word count), it drops the matched `InstructionVariant`, the `isa_model`, the mnemonic, and the operand expression trees. Second, it has **no control-flow awareness whatsoever** — a branch operand is just an expression, with no notion of a target line, successor, or predecessor. The changes below are organized by how much they disturb existing code.

### Ready as-is (no change)
* **Pass insertion.** A third pass slots cleanly between first-pass address assignment and the existing second pass; the two existing passes have no coupling that a read-only analysis pass between them would break.
* **Branch-target / fall-through → CFG-node resolution.** The engine already builds an address→line map (`line_dict`), but that alone is not sufficient: labels, directives, data, and multiple source lines may share one address. For a direct branch, the CFG resolver retains the resolved target label when available and maps it to the executable instruction at that label; an address-only target must resolve uniquely. For ordinary fall-through, it looks specifically at `instruction.address + instruction.word_count`. Labels and zero-width analysis directives may be traversed at that address, but emitted data, a gap, a non-executable target, an ambiguous same-address group, or crossing the lexical region boundary produces a flow diagnostic rather than being skipped.
* **New `#` directives.** `#track` and friends follow the existing `#create-scope` / `#mute` precedent exactly — persistent, source-ordered line objects registered in the preprocessor-line factory, receiving `symbol_scope`/memory-zone context. `#if`-excluded lines are retained but flagged `compilable = False` (filter them, matching "tracking follows compiled code"); `#define` is a separate textual pre-pass and does not interfere.
* **Diagnostics.** `DiagnosticReporter` + `LineIdentifier` cover error/warn/info with line attribution. Adding `flow` requires explicitly including it in the categories elevated by `--warnings-as-errors` and preserving the category for tests/tooling.

### Small additive changes (low risk)
* **Counter-coordinate symbol records.** Extend the scoped-symbol machinery with a distinct `COUNTER_COORDINATE` kind carrying the resolved integer, owning counter instance, declaration site, and validity state. The dependency-driven pass inserts the coordinate when an emitted coordinate reference requires it; an unused declaration remains zero-width and need not trigger propagation.
* **`:=` declaration parsing.** Add a dedicated line form before ordinary address-label matching. The current address-label regex would otherwise read `.slot := ...` as label `.slot:` followed by an instruction beginning `=`, so either `:=` must receive precedence or the colon-label pattern must explicitly exclude `:=`. The declaration accepts all existing symbol-scope spellings, inserts the coordinate record into the same namespace, and does not reuse or change ordinary constant-assignment parsing.
* **Expression operators.** The hand-rolled recursive-descent parser (`src/bespokeasm/expression/__init__.py`) implements `LSB(..)` / `BYTE0(..)` as function-style tokens; `COUNTER(..)` replicates that pattern (token, regex, parse case, compute case) and joins the reserved `EXPRESSION_FUNCTIONS_SET` (`keywords.py`) so it cannot collide with user labels. Bare coordinate references reuse the ordinary label token: the analysis pass resolves label leaves against coordinate scopes and deposits offsets on the matching nodes.
* **Config parsing.** `flow_counters` classes and the per-instruction `flow_effects`/`flow_terminal`/`flow_transfer`/`flow_target_operand`/`flow_call_effects` keys are parsed and validated in `AssemblerModel._validate_config()` (config-load consistency checks), regardless of the flow-check setting. The capability-completeness checks (inert class, exhaustive `flow_transfer` coverage inside active regions, mode availability, usable call summary — see *Required Metadata: Fail Loud, Never Silently Inert*) run usage-time when verification or requested value resolution invokes the tracking pass.

### Genuine structural changes (the real work)
* **(A) Conditionally retain per-instruction config and typed operands on the line.** *(M0; M1 consumes effects and M5 consumes targets.)* When the ISA declares an analysis feature, store an immutable analysis record containing the selected `InstructionVariant`, the explicit merge of root-instruction semantics with selected-variant overrides, source and canonical mnemonics, typed matched operands, and the **parsed operand expression(s)** (per Q10 — retain the expression tree, not just the source string). An operand must distinguish a compile-time semantic value from an emitted encoding: a register's numeric opcode is not its runtime value and cannot satisfy `ARG(n)`. Give each record a stable source identity including line-object ordinal and macro-constituent identity. Retain the records under either flow-check setting because emitted-value dependencies are discovered after source parsing; do not allocate them for an ISA with no analysis feature.
* **(B) A distinct analysis pass retaining source and layout relationships.** *(M1, fully required at M5.)* Grows the engine from two passes to three (address assignment → flow analysis → bytecode). The new pass iterates the **source-ordered** line list for directives and lexical regions while consulting an immutable address index for physical fall-through and direct targets. Counter state remains independent of the address counter. M0 establishes stable source identities; M5 adds the address-indexed executable/occupied-location view.
* **(C) Structural CFG + concrete counter propagation.** *(M5.)* Net-new infrastructure: require exhaustive `flow_transfer` classification, read a direct target from `flow_target_operand`, evaluate it to an address, retain label identity, resolve direct targets and `address + word_count` fall-through to nodes, and build immutable edges/roots/boundaries. The analyzer never guesses a target or substitutes “next source instruction” for physical adjacency. Keep this **structural CFG representation analysis-neutral**, because its nodes and edges are execution facts. Build M5's worklist, state merge, and transfer logic as a clean but concrete `require-equal` flow-counter implementation. Do not introduce a generic lattice-parameterized propagation framework until a second real analysis client demonstrates the correct abstraction boundary.
* **(D) Deliver tracker-resolved `COUNTER()` and coordinate-reference values to allowed value contexts.** *(M1/M2.)* These values are position-dependent (the same `COUNTER(stack)` differs line to line), but the expression evaluator (`ExpressionNode.get_value()`) currently receives only `(symbol_scope, active_named_scopes, line_id)` — not the line's counter state. The parser must first tag the expression's use context and reject layout-affecting/selection-affecting contexts. For allowed fixed-width/fixed-size values, the tracking pass **pre-resolves each `COUNTER()` and coordinate-reference occurrence to a literal keyed to its stable source identity and deposits it** for second-pass evaluation to read. Data flows one way (tracker → value), so analysis cannot perturb addresses, word counts, or variant selection. This value-resolution pass is mandatory whenever emitted words depend on it, independent of the flow-check switch. **Implementation assumption to preserve:** the emitted-expression discovery (`AssembledInstruction.flow_expression_nodes` and its coordinate-candidate companion, also used by the flow-usage gating scan) inspects top-level bytecode parts only. Today that is exhaustive — composite parts wrap only fixed opcode/register-selector bits, while every operand argument expression is retained as a top-level part — but an operand type that nests expression-bearing parts inside a `CompositeByteCodePart` would be invisible to it and must extend the discovery recursively.

### Note on macros
Macros influence counters only in aggregate (no own flow metadata; see *Macros Influence Counters Only in Aggregate*). Macro invocations expand into a `CompositeAssembledInstruction` exposing the constituent `AssembledInstruction`s, so the aggregate is computed by walking the expansion — but each constituent has the same config-retention gap as (A) (it must expose its own effect map and operand values). Aggregation therefore depends on (A) and is available as soon as the constituents' effects are (M1–M3); only constituents using *structural* operand-dependent effects defer to M7.

## Related Static Analyses (out of scope; reuse the structural CFG)
Building M5 produces a reusable execution-order **CFG** and a config-metadata channel describing instruction semantics. Its first propagation client is deliberately counter-specific. A later second client can motivate extraction of shared worklist/lattice machinery from concrete experience; the possibilities below must not dictate M5's propagation abstraction prematurely. None are part of this feature.

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

**Editor extensions (generated):** the VS Code, Sublime Text, and Vim extension generators (`configgen/{vscode,sublime,vim}/`) build their grammars from the central keyword sets in `keywords.py` and their hover content from `docsgen/directive_docs.py` via `configgen/hover_docs.py`. Adding the new directives/operators to those registries propagates to all three editors; per-editor verification (Sublime hover plugin, Vim semantic/hover) is still required.

Flow syntax has its own central `SyntaxElement` roles rather than borrowing constant or generic expression-function styling:

| Source role | Central syntax element | VS Code / Sublime Text scope | Vim group |
|---|---|---|---|
| The default instance name introduced by `#track stack` | `FLOW_COUNTER_NAME` | `variable.other.flow.counter` | `FlowCounterName` |
| A counter instance referenced by `#endtrack stack`, `COUNTER(stack)`, or the first argument of `COORDINATE(stack, 3)` | `FLOW_COUNTER_USAGE` | `variable.other.flow.counter.usage` (with the base `variable.other.flow.counter` scope) | `FlowCounterUsage` |
| The symbol on the left of `.candidate := COORDINATE(...)` | `FLOW_COORDINATE_NAME` plus `FLOW_COORDINATE_DEFINITION` | `variable.other.flow.coordinate` and `variable.other.flow.coordinate.definition` | `FlowCoordinateName` / `FlowCoordinateDefinition` |
| A bare coordinate reference (`lds .candidate`) | `FLOW_COORDINATE_USAGE` — tagged *contextually*, not by the static grammar: the Sublime hover plugin's semantic-region pass and the VS Code extension's semantic-token provider scan `:=` declarations (including includes) and scope matching usages, with ordinary labels/constants taking precedence. Vim has no contextual engine, so usages retain label styling there. | `variable.other.flow.coordinate.usage` (via `add_regions` / the `flowCoordinate` semantic token) | — |
| The function-style flow operators `COORDINATE` and `COUNTER` | `FLOW_OPERATOR` | `keyword.operator.flow` | `FlowOperator` |

`#track` / `#endtrack` remain preprocessor keywords, and `:=` remains an assignment operator; the distinct flow roles apply to the names and function-style operators around them. Colors for every role live in `configgen/color_scheme.py` and are represented in `dev/color-scheme/color_demo.py`, so each role can be themed independently even when two roles initially share a default color.

Because extensions are generated per ISA, the capability-gated flow-counter keywords, specialized captures, and theme rules are included **only when the source ISA enables the feature**. The base `#assert` keyword and the built-in `__FLOW_COUNTERS_AVAILABLE__` constant, together with their hover documentation, remain in every generated extension; only `#assert` operands containing `COUNTER()` receive flow-specific captures. For an ISA without a `flow_counters` section, generators subtract the other flow-specific grammar contexts/repositories and color mappings from the common syntax templates. This matches enablement-gated keyword reservation (Open Question 1) while retaining the one probe source needs to detect that gate, and prevents dormant flow syntax from changing highlighting for existing instruction sets. Generator tests must cover both the enabled captures above and their complete absence from disabled-ISA output, plus the availability symbol's presence in both outputs.

**Hover / directive documentation:** entries in `PREPROCESSOR_DIRECTIVE_DOCS` cover general `#assert` and every flow directive, `EXPRESSION_FUNCTION_DOCS` covers `COUNTER` and `COORDINATE`, and coordinate-declaration documentation lives in `docsgen/directive_docs.py`; `test/test_docsgen/test_directive_docs.py` enforces coverage.

**Generated ISA documentation (`bespokeasm docs`, M5.1):** the `docsgen` documentation model and markdown generator gain the top-level Flow Counters section and the derived per-instruction Counter rows in the Modifies table, per the M5.1 milestone entry and acceptance cases 82–89 and 95–99. Because the per-instruction hover markdown shares the Modifies rendering path, hover output inherits the Counter rows with no separate editor work.

**Release collateral:** one overall `CHANGELOG.md` entry when the feature is complete; the feature-introducing release version becomes the `min_version` floor for configs using the new keys; development acceptance harnesses under `dev/` during implementation; and, at release, at least one bona fide example ISA config and program under `examples/` using `flow_counters`.

**Wiki:** the project wiki documents *shipped* behavior, so wiki updates are **ship-time work, scoped per milestone** — not to be written while this remains a draft (documenting an unparsed schema would mislead ISA authors). When a milestone lands, it touches two wiki pages:

* **`Instruction-Set-Configuration-File.md`** — a new `flow_counters` top-level section (counter classes: `source`, `operation`, `join`, `min_value`/`max_value`, `coordinate_offsets`, `allow_zero_offset`, `unknown_instructions`, `invalidate_on_write`, `default_init`, `exit_policy`, `entry_modes`); the per-instruction delta field (the `source` target — `flow_effects.<class>` by default, or a custom field, or `documentation.cycles`), including the operand-expression and edge-dependent `{ taken, fall_through }` delta forms and per-`variants` overrides; and the exhaustive `flow_transfer`, `flow_target_operand`, `flow_call_effects`, `flow_terminal`, `flow_invalidates`, and `flow_write_operands` keys. Document `flow_terminal` as a counter-to-`before_effect`/`after_effect` mapping, and `documentation.cycles` as a recognized instruction field. Cross-reference the existing `documentation.modifies` precedent.
* **`Assembly-Language-Syntax.md`** — the new preprocessor directives (`#track`, `#endtrack`, `#assert`, `#set`, `#entry`, `#suspend`, `#resume`, `#loop`) alongside the other `#`-directives, including grouped `#entry ... value=` attachment and the next-header-label attachment rule for `#loop`; the distinct `:= COORDINATE(counter, offset)` declaration syntax; and the `COUNTER()` operator plus bare coordinate references in the numeric-expression operator table next to `BYTE0(..)` / `LSB(..)`, including the explicit list of allowed and rejected expression contexts.

**CLI documentation:** `Installation-and-Usage.md`, `bespokeasm compile --help`, and shell-completion fixtures document `-a`/`--flow-checks` and `-A`/`--no-flow-checks`, the enabled default, suppression of optional verification/listing annotations, and automatic resolution of emitted `COUNTER()` / coordinate-reference dependencies.

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
    coordinate_offsets: positive # live positions are addressed as sp+N
    unknown_instructions: error   # every instruction explicitly says how it affects the stack
    exit_policy: balanced
    entry_modes:
      called: { init: 0, exit: 0 }   # track only movement owned by the routine
      jumped: { init: 0 }
  cycles:                         # worst-case timing
    source: documentation.cycles  # reuse the timing already documented per instruction
    join: interval                # paths may differ; track the [min,max] hull
    unknown_instructions: error
    exit_policy: none             # the budget assertion is the contract
  ct_cycles:                      # constant-time guard: SAME field, strict join
    source: documentation.cycles
    join: require-equal           # paths must take identical cycles, else timing leak
    unknown_instructions: error
    exit_policy: none

instructions:
  push: { stack_effect: 1,  flow_transfer: none, documentation: { cycles: 11 } }
  pop:  { stack_effect: -1, flow_transfer: none, documentation: { cycles: 10 } }
  ld:   { stack_effect: 0,  flow_transfer: none, documentation: { cycles: 8 } }
  nop:  { stack_effect: 0,  flow_transfer: none, documentation: { cycles: 4 } }
  cmp:  { stack_effect: 0,  flow_transfer: none, documentation: { cycles: 4 } }
  inc:  { stack_effect: 0,  flow_transfer: none, documentation: { cycles: 4 } }
  dec:  { stack_effect: 0,  flow_transfer: none, documentation: { cycles: 4 } }
  add_sp:
    stack_effect: -ARG(0)          # `add sp, N` frees N
    flow_transfer: none
    documentation: { cycles: 8 }
  call:
    stack_effect: 2
    flow_transfer: call
    flow_target_operand: 0
    flow_call_effects: { stack: 0 }
    documentation: { cycles: 17 }
  ret:
    stack_effect: -2
    flow_terminal: { stack: before_effect }
    flow_transfer: return
    documentation: { cycles: 10 }
  jmp:
    stack_effect: 0
    flow_transfer: unconditional
    flow_target_operand: 0
    documentation: { cycles: 10 }
  jz:
    stack_effect: 0
    flow_transfer: conditional
    flow_target_operand: 0
    documentation: { cycles: { taken: 12, fall_through: 7 } }
  jnz:
    stack_effect: 0
    flow_transfer: conditional
    flow_target_operand: 0
    documentation: { cycles: { taken: 12, fall_through: 7 } }
```

### Example A — stack slot labels (issue #18; straight-line, M2)
```asm
#track stack                       ; region opens, stack = 0
build_record:
    push a                         ; stack 0 -> 1
.field_x := COORDINATE(stack, 0)   ; name the slot currently at sp+0
    push b                         ; stack 1 -> 2
.field_y := COORDINATE(stack, 0)   ; name the new slot currently at sp+0
    ld a, [sp + .field_x]          ; offset = COUNTER(stack) - saved coordinate = 2 - 1 = 1 -> [sp+1]
    pop b                          ; stack 2 -> 1
    pop a                          ; stack 1 -> 0
#endtrack stack                    ; exit check 0 == 0  ✓
```
The payoff: insert `push c` right after `.field_y` and the `[sp + .field_x]` line is **untouched** — its offset recomputes from 1 to 2 automatically. That is exactly the manual bookkeeping issue #18 asked to eliminate.

### Example B — subroutine taking a stack argument (M3)
```asm
; multiply(n): caller pushes n, then `call`s; result returned in A
#track stack mode=called           ; routine-owned movement: init = 0, exit = 0
multiply:
.arg := COORDINATE(stack, 3)       ; calling convention places argument at sp+3
    push b                         ; stack 0 -> 1
    ld a, [sp + .arg]              ; offset changes from 3 to 4
    ; ... compute, result in A ...
    pop b                          ; stack 1 -> 0
    ret                            ; pre-effect terminal check: 0 == 0  ✓
```
The `:=` declaration makes `.arg` a stack coordinate rather than an ordinary constant. Writing `.arg = 0` would create an ordinary constant whose references emit a frozen `0` with no counter association.

### Example C — push leak caught on one path (M5)
```asm
#track stack mode=called           ; routine-owned movement: init = 0, exit = 0
safe_divide:
    push b                         ; stack 0 -> 1
    cmp a, 0
    jz .by_zero                    ; conditional: both edges explored
    ; --- normal path ---
    pop b                          ; stack 1 -> 0
    ret                            ; pre-effect terminal check: 0 == 0  ✓
.by_zero:
    ld a, 0xff
    ret                            ; pre-effect terminal check: 1 != 0
                                   ; ERROR(flow): `push b` is never popped on the .by_zero path
#endtrack stack                    ; unreachable lexical delimiter; no second exit check
```
Both `ret`s are `flow_terminal` instructions configured with `stack: before_effect`: each checks routine-owned stack balance and ends its path before the physical −2 return-address pull is applied within that counter region. The unreachable `#endtrack` does not close either execution path or repeat their exit checks; it ends the region's lexical extent so a following routine is not accidentally enclosed. It may be omitted at EOF, where all paths terminating at `ret` is sufficient.

### Example D — runtime-length loop, acknowledged (M5)
```asm
#track stack
push_string:                       ; HL -> NUL-terminated string of unknown length
.saved := COORDINATE(stack, 0)     ; position before the variable region (= 0)
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

### Example E — worst-case timing with a bounded loop (provisional M6 + M7)
```asm
#track cycles init=0               ; interval counter (join: interval)
delay:
#loop count=100                    ; attaches to next compilable label, .spin
.spin:
    nop                            ; cycles += 4
    dec a
    jnz .spin                      ; taken 12 / fall_through 7 (edge-keyed cost)
#assert COUNTER(cycles).max <= 2000  ; exact total is 1995 cycles
#endtrack cycles                     ; exit_policy:none: close without equality check
```
The interval counter computes `100 × (nop 4 + dec 4) + 99 × jnz-taken 12 + 1 × jnz-fall-through 7 = 1995` cycles. The `#loop` count makes the result finite instead of widening to ∞, and the `#assert` fails if the computed worst case exceeds the budget. Because the class uses `exit_policy: none`, `#endtrack` closes the measurement window without additionally requiring the accumulated value to equal its initial value.

### Example F — constant-time check catches a timing leak (provisional M6)
```asm
#track ct_cycles init=0            ; join: require-equal — both paths must cost the same
ct_compare:
    cmp a, b                       ; common prefix: 4 cycles
    jz .equal                      ; unequal edge 7 / equal edge 12
    ld a, 0                        ; unequal: 4 + 7 + ld(8)
    jmp .end                       ;                 + jmp(10) = 29 cycles
.equal:
    ld a, 1                        ; equal:   4 + 12 + ld(8)            = 24 cycles
.end:                              ; ERROR(flow): paths reach .end with ct_cycles 29 vs 24
                                   ;   -> timing leak; the `jmp` makes the unequal path slower
#endtrack ct_cycles                ; unreachable as a valid join until paths are balanced
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
#assert cycles <= 60               ; scalar ISR latency budget
#endtrack stack                    ; exit 0 == 0  ✓
#endtrack cycles                   ; exit_policy:none: budget above is the contract
```
Each instruction updates every active counter from its own `source` field; the two counters are checked independently against their own rules (`stack` balance, `cycles` budget).

## Open Questions
1. **Expression operator names:** *resolved (revised 2026-07: `OFFSET(..)` removed in favor of bare coordinate references).* `COUNTER(..)` and `COORDINATE(..)` are the operators (sigil prefixes are non-viable — `^` is bitwise XOR, `$` hex, `%` binary, `@` operand labels, `#` preprocessor), following the `BYTE0(..)`/`LSB(..)` function-style precedent. They are reserved words **only in ISAs that enable the feature** (declare a `flow_counters` section), so source for non-feature ISAs is unaffected and collision risk falls only on authors who opt in and control their own namespace.
2. **Counter association for coordinate symbols:** *resolved with `:= COORDINATE()`.* Symbol scope and counter association are separate axes: `.var` and `var` remain different symbols, while `:=` distinguishes a counter coordinate from BespokeASM's ordinary `=` / `EQU` constants. `.var := COORDINATE(stack, 1)` records the position currently addressed as `sp+1` and its owning counter; `.arg := COORDINATE(stack, 3)` similarly records `sp+3`. Internally this saved coordinate is `current counter - declared offset`, which lets a later bare reference resolve to `current counter - saved coordinate`, but that implementation arithmetic is deliberately absent from source syntax. The offset is an ordinary compile-time scalar, the class's `coordinate_offsets` policy determines which nonzero signs are physically meaningful, and `allow_zero_offset` controls zero independently. Only symbols declared with `:=` carry offset semantics. This makes `.arg := 0` (without `COORDINATE()`), the old `.arg := COUNTER(stack) - 3` spelling, flow-derived offset expressions, and interval-counter coordinates invalid rather than guessing an association; `.arg = 0` stays an ordinary constant with ordinary reference semantics.
3. **Region/directive interaction:** *resolved.* A `.org` / memory-zone change while a region is open **auto-closes the region** and emits a **warning** — escalatable to a hard error via `-W` (warnings-as-errors). Each live path reaching that boundary receives its applicable exit-value check; a path already closed by `flow_terminal` is not checked again. This avoids silently spanning a relocation while not forcing a hard error on every relocate. (Labels inside a region continue the region, with label-scope-aware entry-point warnings.)
4. **Conditional terminals:** *resolved.* A conditional `ret` (an instruction carrying both `flow_terminal` and `flow_transfer: conditional`) ends one path but not the fall-through. The M5 CFG infrastructure can represent this naturally as a two-edge node, but activation is a provisional M7 design target as listed in *Implementation Phasing*. Until M7 is promoted and implemented, encountering a conditional terminal in an active region is a hard "conditional terminals not yet supported" error; treating it as a warning would allow analysis to continue with behavior the shipped transfer function does not implement.
5. **Counter name namespace & scoping:** *resolved — counters get label-style scope, two levels (global + file).* Counter names are their **own namespace, separate from labels** (a counter `stack` and a label `stack` never collide — counter names appear in `COUNTER()` / `COORDINATE()` counter-argument position and the flow directives, while coordinate symbols live in the ordinary symbol namespace). The name carries a **scope prefix mirroring labels**, and the prefix sets the boundary the tracking region is confined to:
   * **Global** (no prefix, e.g. `#track stack`): program-wide; the region **may span `#include`** (inline included code is tracked, and included code referencing `COUNTER(stack)` binds to the same counter).
   * **File** (`_` prefix, e.g. `#track _stack`): confined to the file; **does not project into `#include`**, so an included library's `_stack` is a distinct counter from the caller's — collision-free, exactly like file-scope labels.
   * *Local* (`.`) and *named* (`#create-scope`-style) scopes are **not** adopted: the tracking region itself already provides local-like lifetime, and `as=` plus the global/file split cover the rest. (Named counter scopes remain a possible future addition only if cross-file counter sharing becomes a real need.)
   The prefix attaches to the effective instance name (the class name, or the `as=` name — `#track cycles as=_sync` is a file-scoped instance `_sync`). A region must open and close within its scope's boundary; if execution would carry an open file-scoped region across an `#include` (or any boundary), that is the auto-close-with-warning of Q3, never a silent untracked gap. Non-overlapping regions reuse a name freely; concurrent instances need distinct `as=` names.
6. **Cross-region call verification:** *resolved — staged.* M5 and the provisional M6 design do not inline callees or infer caller-visible effects from terminal mnemonics. A direct call may declare a target-independent per-class caller-visible net through `flow_call_effects` (for example, balanced stack calls declare `stack: 0`, while a uniform callee-pops convention may declare a nonzero delta); this is an ISA calling-convention contract taken on faith for every target of that instruction variant, while the callee's own region is checked independently. A class with no declared call summary carries an unresolved `CallEffect(callee, class)`, preventing a false precise operand value, bound check, or timing claim after the call. Effects that vary by target remain unresolved. A possible later interprocedural phase may resolve named summaries by recording each region's verified entry/exit effect and declared argument slots per entry-point label, then checking call sites against the named callee's convention; that phase is not committed by this specification.
7. **`#include` interaction:** *resolved by counter scope (Q5).* `#include` is textually inline and a counter tracks execution (not layout — distinct from memzone/named-scope, which are layout/visibility context and correctly reset per-file). So whether a region spans an `#include` is the programmer's choice, expressed by scope: a **global** counter's region spans the include (included instructions tracked, name shared); a **file** (`_`) counter's region is confined to the file and may not cross the include — if execution would carry an open file-scoped region into an `#include`, it auto-closes with a warning (Q3). This gives both the inline-fragment case (global) and library isolation (file) without a special-case `#include` rule.
8. **Return-address ownership / entry mode names:** *resolved.* A routine-owned stack counter normally starts and exits at zero even for a called routine. The physical return-address size remains in the call/return instruction metadata and in calling-convention coordinate offsets; it is not compensated for through `entry_modes.<mode>.init`. A terminal that returns control by restoring a stack-saved execution address uses `before_effect` reconciliation so the routine must restore its own stack movement before the instruction removes caller/control-flow state. Mode names stay **fully author-defined** (flexibility for unusual ISAs), but documentation **recommends conventional names** — `called`, `jumped`, `interrupt` — so tooling and cross-ISA readers see consistency. No reservation or enforcement.
9. **`COUNTER()`/coordinate-reference value delivery:** *resolved.* After rejecting layout- or selection-affecting contexts, the tracking pass pre-resolves each allowed occurrence to a literal keyed by stable source identity that second-pass evaluation reads. Data flows one way (tracker → fixed-width/fixed-size value), so analysis cannot perturb addresses, word counts, or variant selection. (Architecture change D.)
10. **Operand-expression retention:** *resolved and gated.* When the ISA declares an analysis feature, the selected variant's **typed parsed operands and parsed operand expressions** are retained in an immutable analysis record reachable from the `InstructionLine` (architecture change A), so M5 reads `flow_target_operand` directly without re-parsing. The records remain available under either flow-check setting and are not allocated for an ISA with no analysis feature. This handles complex expressions and distinguishes semantic constants from emitted encodings without imposing their memory/time cost on non-flow configurations.
11. **Terminal paths and lexical extent:** *resolved.* `flow_terminal` closes only the path that executes it; it never infers a lexical endpoint. The region remains lexically open until `#endtrack`, an automatic boundary, or EOF. After all paths terminate, a following externally visible label warns because it has no tracked state; an unreachable `#endtrack` is a legal lexical-only delimiter and performs no second exit check. EOF succeeds without `#endtrack` when no live path remains.
12. **`#assert` unresolved-name deferral (open; recorded 2026-08).** Because a bare coordinate reference is indistinguishable from an undefined name at parse time, an assertion operand containing any name the preprocessor cannot settle is classified flow-dependent and deferred to the analysis pass. Consequence: in a flow-enabled ISA under `--no-flow-checks`, an assertion with a typo'd macro name is *skipped* (flow-dependent assertions are suppressed) instead of failing the old string-comparison way. A sharper classification is possible once parsing has completed — coordinate declarations are lexically identifiable (`:=` lines), so the deferral could be restricted to names matching a declared coordinate — at the cost of a second classification pass. Revisit if the silent-skip proves to be a practical footgun.
13. **Vim contextual highlighting gap (open; recorded 2026-08).** Bare coordinate usages are tagged contextually — Sublime via the hover plugin's semantic-region pass, VS Code via a `flowCoordinate` semantic token — but Vim's generated syntax is static-only, so coordinate usages retain ordinary label styling there. If a language-server or semantic-highlighting layer is ever added, coordinate-usage tagging is its first flow-counter customer.
