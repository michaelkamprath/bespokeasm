# MOS 6502 Example, 6502 Source Conventions and Source Migration

Nov 25, 2026 · @Michael Kamprath

## Summary

Add the MOS 6502 as an example instruction set. Use example programs for Ben Eater's breadboard 6502 computer. The goal is source that 6502 programmers find familiar, with little or no porting from other assemblers. BespokeASM does not need to match any one assembler.

Today a 6502 config can express most of the instruction set: `lda $10,x`, `asl a`, `$`/`%` literals, character ordinals, `.org` and `.byte` all work. Seven conventions need new BespokeASM features. Two more general features, found while planning Intel 8085 migration, are cheap enough to include. Each is general, enabled or shaped by the ISA config, and not specific to the 6502. Conventions that differ between 6502 assemblers, or that BespokeASM spells its own way, are handled by a new `bespokeasm migrate` command. Each ISA config declares how source from other assemblers converts to its language.

Reference assembler: ca65 (cc65 2.18). Where 6502 assemblers disagree, follow ca65, except where noted.

Two of the features, the `<`/`>` low and high operators and `*`, also appear in Carsten Herting's assemblers for the Minimal computers, with different precedence and a different meaning of `*`. Their semantics are therefore per-ISA settings, and the Minimal example configs turn them on with Carsten's meaning.

## Goals and non-goals

Goals:

- A generic NMOS 6502 config (`examples/mos6502/mos6502.yaml`) covering all 151 documented opcodes and 13 addressing modes, with instruction documentation for hovers and `bespokeasm docs`.
- Example programs for the Ben Eater 6502 (ROM `$8000`–`$FFFF`, 65C22 VIA at `$6000`), written in conventional 6502 style.
- Every opcode and addressing mode byte-identical to ca65. Tests compare against bytes captured from ca65 and stored as fixtures. Tests and CI never run ca65.
- A `bespokeasm migrate` command that rewrites source from another assembler into BespokeASM syntax. The rules for each source assembler are declared in the ISA config.
  - The 6502 config declares ca65 and vasm.
  - The four Minimal configs declare Carsten Herting's assemblers.
  - An Intel 8085 dialect is deferred; see [intel-8085-migration-spec.md](intel-8085-migration-spec.md).

Non-goals:

- Native support for these conventions from other assemblers. `bespokeasm migrate` converts what it can and reports the rest:
  - **Source-level macros (`.macro`):** reported. A separate project, planned to follow soon; see [source-macros-notes.md](source-macros-notes.md).
  - **Anonymous labels (`:+`, `-`), labels without a colon, `*=` origin syntax and ca65 `@` cheap locals:** converted.
  - **Forced-width prefixes:**
    - `z:` is dropped, because relaxation already selects zero page for any value that fits, forward references included, and a value that doesn't fit is still a range error.
    - `a:` (force absolute) is reported, because BespokeASM has no way yet to opt an operand out of value selection.
  - **Segments and linker configs:** reported. Relocatable blocks, with addresses resolved at link time or even at run time, are a possible future project.
- The 65C02, 65816 and undocumented NMOS opcodes. The config is built so a 65C02 config can extend it later.
- Platform constants (VIA, LCD, ACIA registers) in the config. Ben Eater's source defines `PORTB = $6000` itself, and a predefined `PORTB` would collide with that definition. They go in an include file next to the programs.

## Gap summary

| # | Convention | Today | Feature |
|:-:|:--|:--|:--|
| 1 | `lda #$10` | `#` is an invalid token | [Immediate prefix](#1-immediate-prefix) |
| 2 | `(zp),y`, `(zp,x)`, `jmp (abs)` | indirect is `[...]` only | [Parenthesized indirect operands](#2-parenthesized-indirect-operands) |
| 3 | `lda $10` vs `lda $1234` | the first syntactic match wins | [Value-selected operands](#3-value-selected-operands-and-pass-1-relaxation) |
| 4 | branch offset from the next instruction | offset from the instruction's last word | [Relative offset base](#4-relative-offset-base) |
| 5 | `#<msg`, `#>msg` | invalid tokens | [Low and high operators](#5-low-and-high-operators) (per-ISA precedence) |
| 6 | `jmp *`, `bne *-3` | `*` is only multiply | [Current address `*`](#6-current-address-) (per-ISA meaning) |
| 7 | `.word`, `.res` | unknown directives | [Directive aliases](#7-directive-aliases) |
| 8 | octal `17Q`, `0o17`; binary `1010B` | no octal literal; binary only as `b0101`/`%0101` | [Octal literals and the binary `B` suffix](#8-octal-literals-and-the-binary-b-suffix) |
| 9 | `~mask` | no complement operator | [Complement operator `~`](#9-complement-operator-) |

## 1. Immediate prefix

A `numeric` operand can require a `#` before its expression:

```yaml
immediate:
  operand_values:
    imm8:
      type: numeric
      prefix: '#'
      argument: {size: 8, word_align: true}
```

- With `prefix: '#'` the operand matches only `#expr`. Without a prefix, a numeric operand never matches text starting with `#`, so `lda $10` cannot select the immediate form.
- `#` is the only allowed prefix value for now. It is a new key, not a decorator: decorators also apply to mnemonics, and a `#` at the start of a line is a preprocessor directive.
- Space after `#` is allowed (`# $10`), as ca65 allows it.
- Editors highlight a `#` inside an operand as part of the operand, not as a preprocessor directive. Generated grammars anchor preprocessor directives to the start of the line. This must be checked in all three editors.

## 2. Parenthesized indirect operands

Each indirect operand chooses what it is written in:

```yaml
izx:
  type: indirect_numeric
  enclosure: parentheses       # default: brackets
```

- `enclosure` is `brackets` (the default), `parentheses` or `braces`, and applies to `indirect_numeric`, `deferred_numeric`, `indirect_indexed_numeric`, `indirect_register` and `indirect_indexed_register` operands. It is per operand, not per ISA (decided Nov 26, 2026), so `[ ]`, `( )`, `{ }` and their doubled forms can all appear in one ISA, with the same meaning or different ones. The Z80 uses parentheses too, so this is not 6502-specific.
- `relative_address` takes `enclosure` too, with no default: without it the operand is bare. The old `use_curly_braces: true` is removed from the documentation but still accepted, as `enclosure: braces` (decided Nov 26, 2026); setting both to different things is a config error. An enclosed relative address counts as an enclosed form of depth 1, so another variant's `{vec}` form doesn't shut out `{label}`.
- **Rule, per instruction:** where an instruction configures an enclosed form at an operand position, in any variant, an operand there that is wrapped wholly in that enclosure is read as that form, and the deepest configured form wins. So `jmp (vec)` is indirect, and `lda ($10)` on the NMOS 6502 is an error, as in ca65 ("Illegal addressing mode"), because `lda` has `($10,x)` and `($10),y`. An instruction with no `( )` form reads the parentheses as grouping: `ldx ($10)` is `ldx $10`. An expression that only starts with a parenthesis, such as `lda ($10+2)*2`, is always a numeric expression, and so is anything after `#`.
- `((x))` is deferred only where a `(( ))` form is configured. Elsewhere it is indirect, with `(x)` inside.
- Under brackets the rule never changes a match, because plain operands already reject `[` and `[ ]` rejects `[[`. Existing configs assemble byte-identically.
- Brackets stay the default.

`(zp),y` is already expressible as two operands: an indirect operand and register `y`. `(zp,x)` needs the register inside the parentheses, so a new operand type, `indirect_indexed_numeric`, takes a value, a separator and an index (decided Nov 26, 2026: a type of its own rather than an option on `indirect_numeric`, configured like `indirect_indexed_register` with `index_operands`):

```yaml
indexed_indirect:
  operand_values:
    zp_x:
      type: indirect_indexed_numeric
      enclosure: parentheses
      bytecode: {value: 0xA1, size: 8}
      argument: {size: 8, word_align: true}    # the value before the comma
      index_operands:                          # matches (expr,x)
        x: {type: register, register: x}       # no bytecode here, so x emits no bits
```

Each index operand's bytecode follows the operand's own, so the 6809's `[n,X]`/`[n,Y]` postbyte bits can come from the index. The index may be any operand type (decided Nov 26, 2026), and an index's own argument follows the value's: with `index_separator: plus` (default `comma`), `[$1234 + [a+6]]` takes an `indirect_register` index with an offset and emits the value, then the offset. With `plus`, the index is the last top-level `+` term that reads as an index, so the value can contain `+` itself.

The operand splitter already keeps commas inside parentheses together, so `($10,x)` arrives as one operand.

## 3. Value-selected operands and pass-1 relaxation

Most 6502 memory instructions have a 2-byte zero-page form and a 3-byte absolute form, written the same way in source. A form can say that it applies only when the operand's value lies in a memory zone:

```yaml
zero_page:
  operand_values:
    zp:
      type: address
      select_by_value: true
      argument: {size: 8, word_align: true, memory_zone: ZERO_PAGE}
absolute:
  operand_values:
    abs:
      type: address
      argument: {size: 16, word_align: true}
```

```yaml
lda:
  variants:
    - {bytecode: {value: 0xA5, size: 8}, operands: {count: 1, operand_sets: {list: [zero_page]}}}
    - {bytecode: {value: 0xAD, size: 8}, operands: {count: 1, operand_sets: {list: [absolute]}}}
```

- With `select_by_value: true`, an `address` operand with `memory_zone` matches only when its value is known and lies in that zone. Otherwise matching moves on to the next form, as if the syntax hadn't matched.
- **Relaxation:**
  1. Pass 1 starts with every value-selected operand unresolved, so those lines take their next matching form (absolute).
  2. Pass 1 assigns addresses, then re-evaluates each value-selected line against the new symbol values.
  3. A line whose value now lies in the zone switches to the selected form, and pass 1 runs again.
  4. This repeats until no line changes.
- **Termination:** a line only ever switches to the selected (shorter) form, never back. Every round moves later addresses down, so the loop ends. A safety cap (64 rounds) reports an internal error if it doesn't.
- **Final check:** if a line's value no longer lies in its zone after relaxation, that is an error. This can happen with expressions such as `0 - label`. It names the line and the value.
- Literals and constants resolve in the first round. So do labels, once pass 1 has placed them: `counter: .res 1` in zero page selects zero page wherever `counter` is defined. Here BespokeASM differs from ca65, which uses absolute for a forward reference and warns.
- The selected form must be no longer than the forms after it. Config validation checks this, because the termination argument needs it.
- Emission inertness: relaxation changes only which form is chosen. Output for ISAs without `select_by_value` must stay byte-identical. Verify this against the existing examples.

## 4. Relative offset base

`relative_address` gains `offset_base`:

| Value | Offset measured from | Used by |
|:--|:--|:--|
| `instruction_start` (default) | the instruction's first byte | |
| `last_word` | the instruction's last word | Mostek 3870 (formerly `offset_from_instruction_end: true`) |
| `next_instruction` | the word after the instruction | 6502 branches |

`offset_from_instruction_end: true` stays as an undocumented alias for `last_word`. Setting both keys is a config error. `here: bne here` then assembles to `D0 FE`, as on the 6502.

## 5. Low and high operators

In expressions, a prefix `<` gives the low word of a value and a prefix `>` the word above it, where a word is the ISA's `word_size`. With 8-bit words these are the low and high byte (`BYTE0` and `BYTE1`), as 6502 and similar assemblers use them. An ISA turns the operators on and chooses their precedence:

```yaml
general:
  low_high_operators: tight        # or whole_expression; absent means not available
```

Assemblers disagree on precedence, and a wrong choice changes ported code's bytes silently, so the config must state it. There is no default.

| Value | `<lab+1` means | Where `<`/`>` may appear | Matches |
|:--|:--|:--|:--|
| `tight` | `(<lab)+1` | before any term: at the start, after an operator, after `(` | ca65 |
| `whole_expression` | `<(lab+1)` | at the start of an expression or parenthesis, optionally after `~` or `-`; applies to the rest of that scope | Carsten Herting's Minimal assemblers (UART CPU, Minimal 64, Minimal 64x4) |

- The two only differ when the low word carries, for example `lab = $12FF` with 8-bit words.
- **Word size** (decided Nov 25, 2026; first planned as 8-bit bytes):
  - `<x` is `x & mask` and `>x` is `(x >> word_size) & mask`, where `mask` is `word_size` bits.
  - With 16-bit words, `<$12345678` is `$5678` and `>$12345678` is `$1234`.
  - With 4-bit words, `<$A7` is `$7`.
  - The setting was first called `byte_operators`. It was renamed before release because the operators split by word, not by byte.
- The 6502 config uses `tight`. The Minimal CPU, Minimal 64, Minimal 64x4 and Redux configs use `whole_expression`, so source written for Carsten's assemblers keeps its meaning. Those four configs then require BespokeASM 0.9.1.
- `<<` and `>>` stay shift operators.
- Preprocessor conditions (`#if`, `#assert`, `#require`) split on comparison operators before evaluating terms. A term starting with `<` or `>` there still parses as a low or high operator; tests cover `#if >ADDR == $12`.

## 6. Current address `*`

`*` where a value is expected is the current address. Elsewhere it is multiply. An ISA turns it on and chooses which address it means in an instruction:

```yaml
general:
  current_address: instruction_start     # or value_address; absent means not available
```

| Value | `*` in an instruction operand | Matches |
|:--|:--|:--|
| `instruction_start` | the instruction's first byte, so `bne *` loops | ca65 |
| `value_address` | the address of the operand's own bytes (after the opcode) | Carsten's Minimal assemblers, which emit the opcode before reading the operand |

- In a data directive, `*` is the address of the value being written under either setting, so `.word *, *` writes two different addresses. This matches both ca65 and Carsten's assemblers.
- `*` is an error in constant definitions (`here = *`) and preprocessor conditions. A constant has no address; use a label.
- `*` is "where a value is expected" at the start of an expression, after a binary operator, after a unary operator, or after `(`. So `* * 2` is the current address times two.
- The 6502 config uses `instruction_start`. The Minimal 64 and Minimal 64x4 configs (both revisions) use `value_address`. The Minimal UART CPU's assembler has no `*`, so its config leaves it off.
- Verification for the Minimal configs: compile Carsten's `asm.cpp` locally and byte-compare `<`, `>` and `*` cases. As with ca65, the captured bytes become test fixtures, and tests never run his assembler.

## 7. Directive aliases

A config can give data and fill directives other names, in `general`:

```yaml
general:
  directive_aliases:
    word: 2byte
    res: fill
    text: byte
```

- Targets are limited to data directives (`.byte` through `.16byte`, `.cstr`, `.asciiz`) and `.fill`, `.zero` and `.zerountil`. An alias for a compiler or preprocessor directive is a config error. Porting `.include` and `.if` is `bespokeasm migrate`'s job (decided Nov 25, 2026).
- `.fill N` with no value fills with zero, so `.res N` (alias of `.fill`) works with or without a fill value, as in ca65.
- An alias name may not be an existing directive name.
- Aliases appear in editor highlighting, hovers (with the target's documentation) and generated docs.
- The 6502 config defines `word`, `res` and `text`. ca65's `.addr` is the same as `.word`, so the config may alias it too. Any further alias needs a stated reason, because each one is surface area.

## 8. Octal literals and the binary `B` suffix

These are new numeric literal forms in every ISA. They come from Intel's 8080/8085 assembler and its descendants, but nothing about them is ISA-specific.

| Form | Example | Value |
|:--|:--|:--|
| `0o` prefix | `0o17` | 15 |
| `Q` or `O` suffix | `17Q`, `17O` | 15 |
| `B` suffix | `1010B` | 10 |

- Suffixes are case-insensitive, like the existing `H` hex suffix.
- `Q` and `O` are not hex digits, so the octal forms are unambiguous under every `default_numeric_base`.
- **`B` suffix exception:** `B` is a hex digit. With `default_numeric_base: hex`, `1010B` keeps its current meaning, a bare hex number, and the `B` suffix is not a binary literal. The GMC-4 example uses hex as its default base, and its source must not change meaning.
- A token starting with a digit is never a label, so none of these forms can collide with a symbol name.
- **Editors:** the generated grammars highlight the new forms as numbers.
- `D` (decimal) suffix is not added: under a hex default base `12D` is hex, and the form is rare.

## 9. Complement operator `~`

A prefix `~` is the bitwise complement, in every ISA.

- **Precedence:** the same as unary minus.
- **Width:** the value is unbounded, as with negation: `~0` is `-1`. The emitting directive or operand masks it to its width, so `.byte ~$0F` is `$F0`.
- **Preprocessor conditions:** `~` is also accepted in `#if` and `#assert`, which use the same expression parser.

## Milestone 1 notes (Nov 25, 2026)

Found while building sections 5, 6, 8 and 9:

- **Unary minus fixed.** Negation used to apply to the whole rest of the expression, so `-1+2` was `-3`. It now applies to one term, like `~` and the tight `<`/`>`. This is a behavior change; every existing example assembles byte-identical.
- **Base threading fixed.** Address, relative-address and numeric-enumeration operands never received `default_numeric_base`, so they read bare numbers as decimal under any base. The base now travels in an `ExpressionSyntax` value with the `low_high_operators` and `current_address` settings. Every parameter that took a base name accepts it.
- **`*` in flow analysis.** `*` in an operand resolves to the instruction's own address in flow analysis too, using a per-operand word offset recorded with the analysis record. So `jpa *+2` gives the right flow target and entry checks.
- **Verified against Carsten's assemblers.** The Minimal 64x4 Rev 1.1 and Redux assemblers (`asm.cpp`, built locally), the Minimal 64 assembler and the Minimal UART CPU assembler (`asm.py`) all produced the same bytes as BespokeASM for the `<`, `>` and `*` probes. The 64x4 Rev 1.1 and UART CPU bytes are test fixtures.
- **Config version.** The four Minimal configs say `min_version: '0.9.1a1'` until 0.9.1 ships; set it to `0.9.1` at release.
- **Highlighting.** Editors give `*` as the current address (`variable.language.current-address`) and `<`/`>` as the low and high operators (`keyword.operator.low-high`) their own scopes and colors, where the ISA turns them on.
  - Grammars can't look back past spaces, so they decide from what follows. `*` is an address unless a value follows; `x*-2` reads as an address.
  - `<`/`>` are the operators when a value follows with no space, which leaves shifts, `<=`/`>=` and `#if` comparisons alone.
  - Checked in VS Code's TextMate engine, Sublime Text and Vim.
- **For milestone 2.** The Sublime hover code colorer treats `#...` as a directive. A 6502 `#$10` operand in hover code examples needs to stay an operand.

## Milestone 2 notes (Nov 25, 2026)

Found while building sections 1 and 7:

- **Aliases live in `general`**, next to the other source-syntax settings (`low_high_operators`, `allow_embedded_strings`).
- **Aliases are resolved before parsing, and listed as written.** The directive factory swaps a leading alias for its directive, then lists the line with the alias. The line factory removes each parsed object's text from the line, so a line object must keep text that appears in the source; without that, the line loops forever.
- **Flow rules follow the target.** `.res COUNTER(stack)` is rejected as a fill count, as `.fill` is. Without resolving the alias first, the flow check missed it and the user saw an internal-sounding error.
- **Messages name the alias.** `.word "hi"` reports `.word data directive used with string value`, and `.word` alone suggests `.word 0x1234`.
- **Upper-case data directives fixed.** `.BYTE 5` failed with a `KeyError`, because the size and mask tables are keyed in lower case. Directive names now ignore case everywhere, as aliases do.
- **`#` diagnostics.** `lda #` says `"#" must be followed by a value`. In an ISA without the prefix, `ldi #5` says `"#" marks an immediate value, which this operand does not take`. A prefixed operand given a bare value expects `a "#" immediate value`.
- **Hover code.** The Sublime colorer treats `#name` as a directive only before a mnemonic, so `lda #$10` colors `#` as punctuation and `$10` as a number.
- **Highlighting.** All three editors anchor preprocessor directives to the start of the line, so `#` inside an operand needed no grammar change. Checked in VS Code's TextMate engine, Sublime Text and Vim, with alias highlighting and hovers.


## Milestone 3 notes (Nov 26, 2026)

Found while building section 2:

- **Per operand, not per ISA.** The first plan was a global `general.indirect_notation`. Making it an operand setting lets `[ ]` and `( )` coexist, so nothing global changes.
- **The rule is per instruction, across variants.** Each instruction collects the `(enclosure, depth)` forms of all its variants and macro variants, by operand count and position, and gives them to every variant's operand parser. A variant whose own forms have no parentheses still refuses `lda ($10)`. Operand sets are shared between instructions, so the rule is passed into matching, not stored on operands.
- **Depth alone decides.** A form is excluded when it has fewer enclosure layers than the operand requires. An enclosed operand takes only its own enclosure, and registers and enumeration keys never match a parenthesized operand (enumeration keys are matched as words), so the enclosure itself needs no check.
- **Inner expressions widened.** `indirect_numeric` matched its inner text with a pattern that allowed only `$ % ( ) + -`, letters, digits and spaces, so `[vec*2]`, `[<vec]` and `['A']` were rejected. It now strips the enclosure and lets the expression parser decide, which also rejects the commas, brackets and braces of other forms. Register forms keep their patterns. `indirect_register` adds a balance check so `(hl+5)+(3)` is not `(hl + "5)+(3")`, because its offset is not parsed until later; `indirect_indexed_register`'s index operands already reject unbalanced text.
- **Enumeration constructor bug.** `EnumerationOperand` passed `True` where the diagnostic reporter goes, so an enumeration without an `argument` failed with `'bool' object has no attribute 'error'`. It now reports that the argument is required, as documented.
- **Index bytecode was dropped without the operand's own.** An operand with no `bytecode` had no bytecode position, so the generator discarded what its index operands emitted: `[hl + a]` lost `a`'s bits. Positions now default to suffix, as documented. No shipped config was affected.
- **Macros pass the argument, not the operand.** `@ARG(0)` of `($10,x)` is `$10`, as it is for brackets, so a macro writes `lda (@ARG(0),x)`.
- **Diagnostics.** `lda ($10)` says parentheses around the whole operand select another form here, and names the enclosed forms. `($10,y)` lists the expected forms, `(address, x)` among them, instead of reporting the comma as a bad token.
- **Braces and relative addresses (added on request).** `braces` joined the enclosures, and `relative_address` gained `enclosure`. Braces never group, so the expression parser rejects a `{` inside, and editors color every operand brace as addressing without a whole-operand check. The mismatch message no longer says "indirect", since the enclosed form may be a relative address.
- **The index can be any operand (added on request).** `ld [$1234 + [a+6]]` is an `indirect_indexed_numeric` whose index is an `indirect_register` with an offset. `index_separator: comma | plus` picks the separator. An index's argument is a trailing argument of the operand, not merged into one composite part, which would byte-swap the pair on little-endian ISAs; `argument` stays the value, so `@ARG`, operand labels and flow analysis are unchanged, and `reverse_argument_order` keeps one operand's arguments together.
- **Bit packing bug.** `compact_parts_to_words` wrote a whole-word part that isn't `word_align`ed straight out, ahead of partial bits still waiting: a 4-bit operand bytecode followed by an 8-bit one gave `ef a9 20` instead of `ef 2a 90`. It now packs after them. No shipped config was affected.
- **Docs tables.** A Value cell listing alternatives, as in `(x | y)`, broke the generated Markdown table row; `|` is now escaped in both operand tables.
- **Highlighting is per ISA.** A grammar can't apply the per-instruction rule, so in an ISA with `( )` forms a parenthesized group that is a whole operand (after whitespace or a comma, followed by a comma, comment or line end) is colored as addressing, `(( ))` as double addressing. `ldx ($10)` is colored as addressing even though it assembles as absolute. Checked in VS Code's TextMate engine, Sublime Text and Vim.

## Milestone 4 notes (Nov 26, 2026)

- **`last_word`, not `last_byte`.** Offsets count in words, so the name doesn't assume 8-bit words, as with `low_high_operators`.
- **Legacy key undocumented.** `offset_from_instruction_end` is gone from the wiki and still accepted as `offset_base: last_word`, as `use_curly_braces` is for `enclosure: braces`. The Mostek 3870 config now says `offset_base: last_word`, with `min_version: '0.9.1a1'` (set to `0.9.1` at release), since an older BespokeASM would ignore the key and measure from the instruction's start.
- **Relative addresses in macros were measured from the macro.** Every part of a macro's expansion was resolved against the macro line's address and total size, so a branch that wasn't the macro's first instruction got the wrong offset, and `offset_from_instruction_end` measured from the macro's end. A macro now tells each relative part where its own instruction is, nested macros included. `*` in a macro's operands still means the macro line's address, as written. No shipped example was affected.

## The 6502 config

- `examples/mos6502/mos6502.yaml`: 16-bit addresses, 8-bit words, little-endian.
- **Registers:** `a`, `x`, `y`, because operands use them (`asl a`, `,x`, `,y`, `(zp,x)`). `s` and `p` are not referenced by any operand, so they are documented with `reserved: false`.
- **Memory zones:** `ZERO_PAGE` (`$0000`–`$00FF`) and `STACK` (`$0100`–`$01FF`) are CPU-defined. Platform zones (RAM, ROM, I/O) belong to the platform include, not the config.
- **Addressing modes:**
  - immediate: `#expr`
  - zero page and zero page indexed: `expr`, `expr,x`, `expr,y`
  - absolute and absolute indexed: `expr`, `expr,x`, `expr,y`
  - indirect: `(expr)`, used by `jmp` only
  - indexed indirect: `(expr,x)`
  - indirect indexed: `(expr),y`
  - relative: branches
  - accumulator: `asl a`. ca65 also accepts a bare `asl`, so the config accepts both.
  - implied
- **Zero page selection:** every mnemonic with both forms lists the zero-page form first, with `select_by_value`.
- `jmp` and `jsr` have no zero-page form.
- `stx abs,y` doesn't exist, so `stx $1234,y` is an error rather than silently becoming zero page.
- **Documentation:** each instruction gets a title, description, flags modified and cycle count, so hovers are useful.
- **Extension:** `.a65`. Generated editor extensions would otherwise claim every `.s` file (decided Nov 25, 2026).

## Ben Eater 6502 example programs

Directory `examples/mos6502/ben-eater/`, with the following files. These are original programs in the style of the platform, not copies of published code.

- `ben-eater.inc`:
  - `#create_memzone` for RAM (`$0000`–`$3FFF`) and ROM (`$8000`–`$FFFF`);
  - the VIA register constants (`PORTB`, `PORTA`, `DDRB`, `DDRA`, `PCR`, `IFR`, `IER`);
  - the LCD control bits.
- `blink.a65`: VIA port B LED pattern, the first program on the platform.
- `hello-lcd.a65`: prints a string on the HD44780 LCD, with a busy-flag wait subroutine.
- `counter-irq.a65`: an interrupt-driven counter. It uses zero-page variables declared as labels in `#mute`d `ZERO_PAGE` code, which exercises relaxation, plus `<`/`>` and `.word` vectors.

Each program builds a 32 KB EEPROM image (a 28C256) for `$8000`–`$FFFF`. File offset 0 is `$8000`, and the NMI, reset and IRQ vectors are the last six bytes, at `$FFFA`–`$FFFF`. The space between the code and the vectors is filled with zeros, as vasm `-Fbin` fills it.

What BespokeASM does today (checked Nov 25, 2026):

- By default the binary starts at address 0 (`-s` defaults to 0). For these programs that gives a 64 KB file whose first 32 KB are zeros, which is wrong for the EEPROM.
- With `-s 32768` the file is exactly 32 KB: code at offset 0, vectors in the last six bytes, zeros between. That matches vasm and ca65 + ld65.
- `#mute`d zero-page variables emit nothing and don't change where the file starts.
- The gap fill is 0 by default. `-f 255` gives `$FF`, the erased state of an EEPROM, if a programmer prefers it.
- `-s`, `-e` and `-f` accept only decimal: `-s 0x8000` is rejected as "not a valid integer".

Changes (milestone 7):

- `-s`, `-e` and `-f` accept the same number forms as source: `0x8000`, `$8000`, `8000H`, and decimal. `$8000` needs shell quoting, which the help text notes.
- The example README gives the exact build command: `bespokeasm compile -c mos6502.yaml -s 0x8000 blink.a65`.

## Migration: `bespokeasm migrate`

A `bespokeasm migrate` command rewrites source written for another assembler into BespokeASM syntax for one ISA (decided Nov 25, 2026):

```
bespokeasm migrate -c mos6502.yaml --from ca65 reset.s -o reset.a65
```

- **What the config declares:** which source assemblers ("dialects") it can migrate from, and the rules for each. The rule kinds are a fixed library implemented in BespokeASM, as output-format generators are, so a config never ships code.
- **Help and docs:** `--from` lists the config's dialects, the way `-t` lists formats. Generated ISA docs list them too.
- **Input and output:** one file per run. It never overwrites its input: it writes to `-o` or to stdout. Includes are reported, not followed, and each file is migrated on its own.
- **Lines it can't convert:** they are kept, prefixed with `; MIGRATE: ` and a reason, so nothing is dropped silently. Search for the marker to find what needs a hand port.
- **Summary:** the command prints counts by rule and every reported line, with file and line. The exit status is 0 when nothing was reported and 1 otherwise.
- **Shell completion:** like the other commands, it stays lightweight at import time; the rule engine loads inside the handler.

### Config

```yaml
migrations:
  ca65:
    description: cc65's ca65 assembler
    rules:
      - rename_directives: {include: '#include', if: '#if', ifdef: '#ifdef', ifndef: '#ifndef', else: '#else', endif: '#endif', define: '#define', addr: '.word'}
      - drop_directives: [setcpu, p02, debuginfo]
      - local_labels: {prefix: '@'}
      - anonymous_labels: {style: ca65}
      - operand_prefixes: {drop: ['z:'], unsupported: ['a:', 'f:']}
      - unsupported: [macro, endmacro, proc, endproc, scope, endscope, segment, import, export]
```

Rules run in the order listed. A rule kind that the config doesn't name never runs.

### Rule kinds

| Kind | Parameters | Converts |
|:--|:--|:--|
| `rename_directives` | map of source name → BespokeASM directive | `.include` → `#include`, `#org` → `.org`. Source names match with or without a leading `.` or `#`, case-insensitively. Arguments are kept. |
| `drop_directives` | list | Removes directives with no BespokeASM meaning (`.setcpu`, `.p02`). The line becomes a comment. |
| `unsupported` | list | Keeps the line as a `; MIGRATE:` comment, reported. |
| `split_statements` | none | Puts each directive, and data that follows an instruction, on its own line (`#mute #org 0x0080`). |
| `bare_data` | `sizing` (`slu4`) | Data written without a directive becomes `.byte`/`.2byte`, sized by the named strategy. |
| `char_literals` | `double_quoted: true` | A single character in double quotes used as a number, `"a"` → `'a'`. |
| `local_labels` | `prefix` | ca65 `@loop` → `.loop`. BespokeASM local labels have the same scope rule. |
| `anonymous_labels` | `style` (`ca65`, `vasm`) | `:` with `:+`/`:-`, or `-`/`+` → generated local labels `.anon_N`. |
| `colonless_labels` | none | A label at column 0 without a colon (vasm) → `label:`. |
| `origin_assignment` | `symbol` | `*= $8000` → `.org $8000`. |
| `operand_prefixes` | `drop` list, `unsupported` list | ca65 `z:` is dropped, since relaxation picks zero page anyway. `a:` and `f:` are reported. |
| `current_address_symbol` | `symbol` | A standalone `$` (Intel, many Z80 assemblers) → `*`. `$7C` stays a hex literal. No dialect in this effort uses it; it is included because it is a simple rewrite that later dialects need. |
| `string_escapes` | `doubled_quotes: true` | `'IT''S'` → `'IT\'S'`. Included for the same reason. |
| `predefined_symbols` | `drop_matching: true` | Removes a definition of a name the config predefines with the same value, such as `#org 0xf003 _Prompt:` in Carsten's programs. A different value is reported. |

A new rule kind needs a stated reason, in the same spirit as directive aliases.

### Dialects

**6502 (`mos6502.yaml`):**

- `ca65`: the rules in the example above.
- `vasm` (oldstyle, Ben Eater's): `colonless_labels`, `origin_assignment: {symbol: '*='}`, `anonymous_labels: {style: vasm}`, and `rename_directives` for its include and conditional directives. Its `.org`, `.word` and `.asciiz` already assemble.

**Minimal CPU, Minimal 64, Minimal 64x4 and Redux: `slu4`, Carsten Herting's assemblers.** Each config's rules match the assembler for that machine and revision. The dialect has these features:

- Elements separated by whitespace, with several statements on a line.
- `#org 0xADDR` sets the origin.
- `#mute` and `#emit` mean the same as in BespokeASM.
- Data has no directive. Its size comes from the element: hex with more than two digits, a symbol or `*` is a word; other numbers and characters are bytes; strings are bytes. Data may follow an instruction on the same line (`JPS 0xf045 "Hello, World!", 0`).
- OS entry points are declared as `#org 0xf003 _Prompt:` under `#mute`, and the configs already predefine those names.

Its rules are `split_statements`, `rename_directives: {org: '.org'}`, `bare_data: {sizing: slu4}`, `char_literals: {double_quoted: true}` and `predefined_symbols: {drop_matching: true}`.

- `<`, `>` and `*` need no rule, because those configs turn them on with Carsten's meaning (sections 5 and 6).
- Carsten's `#mute` doesn't nest and BespokeASM's does. A second `#mute` before an `#emit` is reported.

### Testing and verification

- **Unit tests:** the rule engine and each rule kind are tested in `test/`, with dialect fixtures in `test/config_files/`. Rules are checked on small sources, migrated and then assembled.
- **6502:** migrate sample ca65 and vasm programs, assemble each with ca65 and with BespokeASM, and compare the bytes.
- **Minimal:** migrate Carsten's own programs, such as `stars.asm` and `os.asm` for the Redux. Assemble each with his assembler, built locally, and with BespokeASM, and compare the bytes.
  - This is a manual check; the programs aren't copied into the repository.
  - Small samples with bytes captured from his assembler become test fixtures.

## Errors and diagnostics

| Case | Level | Message |
|:--|:--|:--|
| `lda ($10)` with no single indirect form | error | existing "no valid operands" message, naming indirect as the attempted mode |
| a value-selected line whose value leaves its zone after relaxation | error | `"lda counter": counter is $0100, outside ZERO_PAGE, after its instruction was sized as zero page` |
| relaxation doesn't settle | internal error | `pass 1 did not settle after 64 rounds` |
| `*` in a constant or preprocessor condition | error | `"*" (the current address) is not available here; use a label` |
| `prefix` on a non-numeric operand, or an unsupported prefix | config error | by config path |
| `enclosure` on another operand type or with another value, or contradicting `use_curly_braces`; an `indirect_indexed_numeric` without `index_operands`; `index_separator` on another operand type or with another value | config error | by config path |
| `lda ($10)` where `lda` gives parentheses a meaning but has no `($10)` form | error | `parentheses around the whole operand select another form here; expected (address, x)` |
| an alias targeting a non-data directive, or shadowing a directive | config error | by config path |
| `offset_base` and `offset_from_instruction_end` both set | config error | by config path |
| `--from` names a dialect the config doesn't declare | error | lists the config's dialects |
| a `migrations` rule kind BespokeASM doesn't have, or a bad parameter | config error | by config path |
| a line a migration rule can't convert | reported | `; MIGRATE: <reason>` in the output, plus the summary |

## Suggested implementation order

Each milestone ends with tests, pre-commit, and byte comparison of all existing examples against the previous milestone.

1. Expressions and literals: `low_high_operators` and `current_address`, with both semantics each; octal literals and the `B` suffix; `~`. Turn them on in the Minimal CPU, Minimal 64, Minimal 64x4 and Redux configs, byte-compared against Carsten's assembler.
2. Immediate `prefix` and directive aliases (with `.fill N`).
3. Per-operand `enclosure` and the `indirect_indexed_numeric` type.
4. `offset_base`.
5. `select_by_value` and pass-1 relaxation.
6. The 6502 config, with every opcode byte-compared against ca65 fixtures.
7. Ben Eater programs, platform include, `-s`/`-e`/`-f` number forms, docs, wiki and editor checks.
8. `bespokeasm migrate`: the rule engine and the 6502 `ca65` and `vasm` dialects.
9. The `slu4` dialect in the Minimal CPU, Minimal 64, Minimal 64x4 and Redux configs, byte-compared against Carsten's assemblers.
