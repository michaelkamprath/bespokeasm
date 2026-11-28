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
- A WDC W65C02S config (`examples/mos6502/w65c02.yaml`, extension `.a65c`) covering all 212 opcodes: the 65C02 additions, the Rockwell bit instructions and WDC's `wai` and `stp` (added Nov 26, 2026; the Ben Eater computer's CPU is a W65C02S).
- Example programs for the Ben Eater 6502 (ROM `$8000`–`$FFFF`, 65C22 VIA at `$6000`), written in conventional 6502 style.
- Every opcode and addressing mode byte-identical to ca65. Tests compare against bytes captured from ca65 and stored as fixtures. Tests and CI never run ca65.
- A `bespokeasm migrate` command that rewrites source from another assembler into BespokeASM syntax. The rules for each source assembler are declared in the ISA config.
  - The 6502 and W65C02S configs both declare ca65 and vasm (both, because Ben Eater's code is 65C02 code).
  - The four Minimal configs declare Carsten Herting's assemblers.
  - An Intel 8085 dialect is deferred; see [intel-8085-migration-spec.md](intel-8085-migration-spec.md).

Non-goals:

- Native support for these conventions from other assemblers. `bespokeasm migrate` converts what it can and reports the rest:
  - **Source-level macros (`.macro`):** reported. A separate project, planned to follow soon; see [source-macros-notes.md](source-macros-notes.md).
  - **Anonymous labels (`:`, `:+`, `:-`), labels without a colon, `*=` origin syntax, ca65 `@` cheap locals, vasm `name$` locals and ca65's `:=`:** converted.
  - **Forced-width prefixes:**
    - `z:` is dropped, because relaxation already selects zero page for any value that fits, forward references included, and a value that doesn't fit is still a range error.
    - `a:` (force absolute) is reported, because BespokeASM has no way yet to opt an operand out of value selection.
  - **Segments and linker configs:** reported. placing code the way ld65 places segments is part of [milestone 11](#milestone-11-migrating-microsoft-basic), by extending memory zones; relocatable blocks, with addresses resolved at link time or even at run time, are a possible project after that.
- The 65816 and undocumented NMOS opcodes.
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
- The 6502 config uses `tight`. The Minimal CPU, Minimal 64, Minimal 64x4 and Redux configs use `whole_expression`, so source written for Carsten's assemblers keeps its meaning. Those four configs then require BespokeASM 0.10.0.
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
- **Config version.** The four Minimal configs say `min_version: '0.10.0a1'` until 0.10.0 ships; set it to `0.10.0` at release. (This release was planned as 0.9.1; it became 0.10.0 on Nov 27, 2026.)
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
- **Legacy key undocumented.** `offset_from_instruction_end` is gone from the wiki and still accepted as `offset_base: last_word`, as `use_curly_braces` is for `enclosure: braces`. The Mostek 3870 config now says `offset_base: last_word`, with `min_version: '0.10.0a1'` (set to `0.10.0` at release), since an older BespokeASM would ignore the key and measure from the instruction's start.
- **Relative addresses in macros were measured from the macro.** Every part of a macro's expansion was resolved against the macro line's address and total size, so a branch that wasn't the macro's first instruction got the wrong offset, and `offset_from_instruction_end` measured from the macro's end. A macro now tells each relative part where its own instruction is, nested macros included. `*` in a macro's operands still means the macro line's address, as written. No shipped example was affected.

## Milestone 5 notes (Nov 26, 2026)

- **Matching under a value selection.** A line is first matched with value-selected operands deferred, so it takes its other form. A line with no other form, such as a zero-page-only instruction, takes the value-selected form at once, and pass 2 checks its value. After each pass-1 run, deferred lines are re-matched with their operand values evaluated against the symbols set so far; a line that takes a value-selected form keeps it. The selection is carried in a context variable, so operand types, operand sets and macros need no new parameters; outside line matching, as when explaining a mismatch, value-selected operands match on syntax alone.
- **No fixed cap of 64 rounds.** A round that changes a size switches at least one line for good, so rounds can't exceed the number of deferred lines plus one; that bound is the internal-error guard. A fixed cap could stop a long but valid chain.
- **Size rule checked when a line switches, not in config validation.** Comparing form sizes statically across operand sets, variants and macros is fragile. A value-selected form longer than the form it would replace is reported at the line that would switch.
- **Re-running pass 1.** Zone cursors are reset each round, and a label a line already defined takes its new value (`relocating`) rather than being a duplicate; duplicates still fail in the first round. Pass-1 errors and warnings are reported only for the final layout, since a provisional one can overflow a zone that the final one fits. The analysis source index is built after relaxation, from the final forms.
- **Forward references.** Labels placed in the zone select it wherever they are defined. A pair of lines that would fit only if both shrank at once stays in the longer form, since lines only shrink one round at a time from the longer layout.
- **Final-check message.** `"$1FF - t" is $0101, outside memory zone ZERO_PAGE, after its instruction was sized for that zone`.

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

## Milestone 6 notes (Nov 26, 2026)

- **Two configs.** `mos6502.yaml` (`.a65`) and `w65c02.yaml` (`.a65c`); different extensions so both editor extensions can be installed. There is no config include mechanism, so the W65C02S config repeats the NMOS instructions; both are generated from the same data, and the NMOS test program assembles identically on both.
- **Sources.** Opcodes from ca65 2.18 itself: every mnemonic assembled in every addressing-mode syntax, keeping only what ca65 accepts at the mode's natural size (`lda $12,y` is ca65 promoting to absolute,y, not a mode). This agrees with masswerk's table for all 151 NMOS opcodes. NMOS flags and cycles from masswerk; W65C02S additions and retimings from Bruce Clark's 65C02 opcodes tutorial on 6502.org. Obelisk's 65C02 page has gaps (no `lda (zp)` cycle count, `bbr` as 2 cycles) and wasn't used for cycles.
- **Fixtures.** `test/config_files/mos6502/` holds copies of both configs, every opcode with ca65's bytes, and one program per CPU with ca65 + ld65's bytes. Tests never run ca65.
- **ca65's `*` in `bbr`/`bbs`.** Inside a `bbr`/`bbs` operand, ca65's `*` is the address of the offset byte, two bytes into the instruction; everywhere else it is the instruction's start. The fixtures use label targets there, where both assemblers agree. BespokeASM keeps `*` as the instruction's start throughout.
- **One variant per addressing mode.** Each instruction's root holds its documentation (category, title, description, flags) and shared flow metadata; each addressing mode is a variant titled with the mode and carrying its cycle count, so generated docs name every form ("Version 2 : Zero Page"). `jmp`'s variants each carry their own flow metadata, since an indirect jump has no direct target.
- **Cycles as flow-counter data.** `documentation.cycles` is an integer, or `{taken, fall_through}` for conditional branches, so a `cycles` flow counter can read it. Extra cycles for crossing a page (and, on the 65C02, decimal-mode `adc`/`sbc`) can't be known statically; the addressing-mode and instruction descriptions say so. The analyzer doesn't evaluate edge-map effects yet, so tracking `cycles` across a conditional branch is an error until it does; stack tracking works everywhere.
- **Flow metadata.** `stack` counter: pushes +1, pulls −1, `jsr` call (+2, net 0), `rts` return (−2), `rti` return (−3), `brk` indirect (+3), `txs` invalidates. Entry modes `called`, `interrupt` and `jumped`.
- **Zero page.** Forms with a zero-page variant select it by value. The bit instructions (`rmbN`, `smbN`, `bbrN`, `bbsN`) have only a zero-page form, so their address is checked rather than selected; so is `stx address,y`, which has no absolute form, so `stx $1234,y` is an error.
- **`ina`/`dea` not aliased.** ca65 accepts them on the 65C02, but an alias applies to every form of `inc`/`dec`; `inc a` and `inc` alone are supported, and `bespokeasm migrate` can convert the rest.
- **Diagnostics.** A mismatch explanation now merges the candidates of every variant that fails at the same operand, so `sta #$10` lists `an address, or (address, x)` rather than only the first variant's form.

## Ben Eater 6502 example programs

Directory `examples/mos6502/ben-eater-6502/`, with the following files. The platform's CPU is the W65C02S, so the programs use `w65c02.yaml` and the `.a65c` extension. These are original programs in the style of the platform, not copies of published code.

- `ben-eater.a65c`:
  - `#create_memzone` for RAM (`$0000`–`$3FFF`) and ROM (`$8000`–`$FFFF`);
  - the VIA register constants (`PORTB`, `PORTA`, `DDRB`, `DDRA`, `PCR`, `IFR`, `IER`);
  - the LCD control bits.
- `blink.a65c`: VIA port B LED pattern, the first program on the platform.
- `hello-lcd.a65c`: prints a string on the HD44780 LCD, with a busy-flag wait subroutine.
- `counter-irq.a65c`: an interrupt-driven counter. It uses zero-page variables declared as labels in `#mute`d `ZERO_PAGE` code, which exercises relaxation, plus `<`/`>` and `.word` vectors.

Each program builds a 32 KB EEPROM image (a 28C256) for `$8000`–`$FFFF`. File offset 0 is `$8000`, and the NMI, reset and IRQ vectors are the last six bytes, at `$FFFA`–`$FFFF`. The space between the code and the vectors is filled with zeros, as vasm `-Fbin` fills it.

What BespokeASM does today (checked Nov 25, 2026):

- By default the binary starts at address 0 (`-s` defaults to 0). For these programs that gives a 64 KB file whose first 32 KB are zeros, which is wrong for the EEPROM.
- With `-s 32768` the file is exactly 32 KB: code at offset 0, vectors in the last six bytes, zeros between. That matches vasm and ca65 + ld65.
- `#mute`d zero-page variables emit nothing and don't change where the file starts.
- The gap fill is 0 by default. `-f 255` gives `$FF`, the erased state of an EEPROM, if a programmer prefers it.
- `-s`, `-e` and `-f` accept only decimal: `-s 0x8000` is rejected as "not a valid integer".

Changes (milestone 7):

- `-s`, `-e` and `-f` accept the same number forms as source: `0x8000`, `$8000`, `8000H`, and decimal. `$8000` needs shell quoting, which the help text notes.
- The example README gives the exact build command: `bespokeasm compile -c w65c02.yaml -s 0x8000 blink.a65c`.

## Milestone 7 notes (Nov 26, 2026)

- **`lcd.a65c` added.** `hello-lcd` and `counter-irq` share the LCD routines (set up, busy wait, instruction, character, string), so they live in an include rather than being repeated.
- **Include files use the language's extension.** `ben-eater.a65c` and `lcd.a65c`, not `.inc`, as the other examples' includes do, so editor extensions highlight them; an extension can't claim `.inc`, which other languages use. BespokeASM rejects including a file twice, so `lcd.a65c` doesn't include `ben-eater.a65c` itself; programs include both. (An `#ifndef` guard was tried and found broken: in an included file, a guard whose block `#define`s its own symbol hides the whole block.)
- **Conventional `.org` layout.** The programs place code with `.org $8000` and the vectors with `.org $FFFA`, both absolute, as 6502 source usually does. With `.memzone ROM` active, an absolute `.org` warns, and the ROM zone protects nothing that `GLOBAL` doesn't. `ben-eater.a65c` still creates the `RAM` and `ROM` zones, documenting the memory map, for programs that place code or data by zone.
- **Zero-page variables at the end.** `counter-irq` declares its variables in `#mute`d `ZERO_PAGE` code after the code that uses them; relaxation still gives them zero-page addressing.
- **Verification.** Each program was translated to ca65 (includes inlined, local labels as `@name`, segments for code, vectors and zero page, with the zero-page segment first so ca65 sees the symbols before use) and linked with ld65 into a 32 KB image filled with zeros. All three images are identical to BespokeASM's. `divide_by_10` and `print_decimal` were checked for all 65,536 values by mirroring them in Python; running the images in a 65C02 simulator (py65) was not done.
- **`print` is a keyword.** A local label `.print` is rejected, as `print` is reserved for `#print`.

## Migration: `bespokeasm migrate`

A `bespokeasm migrate` command rewrites source written for another assembler into BespokeASM syntax for one ISA (decided Nov 25, 2026):

```
bespokeasm migrate -c mos6502.yaml --from ca65 reset.s -o reset.a65
```

- **What the config declares:** which source assemblers ("dialects") it can migrate from, and the rules for each. The rule kinds are a fixed library implemented in BespokeASM, as output-format generators are, so a config never ships code.
- **Help and docs:** `migrate` without `--from` (short `-f`), or with a dialect the config doesn't declare, lists the config's dialects with their descriptions. Shell completion offers them, read from the config's `migrations` section the way `-t` completion reads `output_formats`. Generated ISA docs list them in a **Source Migration** section.
- **Input and output:** one file per run. It never overwrites its input: it writes to `-o` or to stdout, and `-o` naming the source file is a usage error. Output line N is input line N, so a report's line number works in both files, unless a rule puts a statement that shared a line on a line of its own (`split_statements`, milestone 9); reports always give the input line, and the source's line endings (LF or CRLF) and final newline are kept. Includes are not followed: each included file is listed as a note in the summary, to be migrated on its own.
- **Lines it can't convert:** they are kept as `; MIGRATE: <reason>: <original line>`, so nothing is dropped silently. Search for the marker to find what needs a hand port. A dropped directive's line becomes a plain comment, `; .setcpu "65C02"`, after the line's indentation.
- **Summary:** printed to stderr: the lines each rule changed (a rename to the directive already written, such as `.org` → `.org`, is no change), every reported line with file and line (a reported block by its first line), and the notes. The exit status is 0 when nothing was reported and 1 otherwise; notes, such as includes, don't count.
- **Shell completion:** like the other commands, it stays lightweight at import time; the rule engine loads inside the handler.

### Config

```yaml
migrations:
  ca65:
    description: cc65's ca65 assembler
    rules:
      - rename_directives: {include: '#include', if: '#if', ifdef: '#ifdef', ifndef: '#ifndef', elseif: '#elif', else: '#else', endif: '#endif', define: '#define', byt: '.byte'}
      - drop_directives: [setcpu, p02, pc02, debuginfo]
      - assignment_operators: [':=']
      - local_labels: {prefix: '@'}
      - anonymous_labels
      - operand_prefixes: {drop: ['z:'], unsupported: ['a:', 'f:']}
      - unsupported: [{macro: endmacro}, proc, endproc, scope, endscope, segment, import, export]
```

The configs' dialects list more directives in each rule; `.addr`, `.word` and `.res` need no rename, because the configs' `directive_aliases` already accept them.

Rules run in the order listed, each over the whole file (anonymous labels need every line). A rule kind that the config doesn't name never runs. A rule with no parameters may be written as its bare name, as `anonymous_labels` is. Rules work on a line's code only, never inside a string or comment, except `string_escapes`; a line already reported or dropped is left to later rules as it is.

### Rule kinds

| Kind | Parameters | Converts |
|:--|:--|:--|
| `rename_directives` | map of source name → BespokeASM directive | `.include` → `#include`, `#org` → `.org`. Source names match with or without a leading `.` or `#`, case-insensitively. Arguments are kept. A bare word matches only where it can't be one of the ISA's mnemonics or the symbol of an assignment (`name =`, `name equ`). A target must be a BespokeASM directive written with its `.` or `#`, or one of the config's directive aliases (`.word`). |
| `drop_directives` | list | Removes directives with no BespokeASM meaning (`.setcpu`, `.p02`). The line becomes a comment. |
| `unsupported` | list of names or `{start: end}` blocks | Keeps the line as a `; MIGRATE:` comment, reported. A block reports every line from its start to its end directive (`end` may be a list), and later lines using the block's name. |
| `split_statements` (milestone 9) | none | For element syntax, where whitespace and commas separate elements: puts each directive, each run of data and each label not at the start of its line on its own line (`#mute #org 0x0080`). Instructions sharing a line stay together, and get commas between operands. Operands on the next line join their instruction; a label before an operand (self-modifying code) becomes an [operand label](https://github.com/michaelkamprath/bespokeasm/wiki/Assembly-Language-Syntax#operand-labels), `@name: value`. A mnemonic used as a value becomes its opcode. Needs the ISA's operand counts. |
| `bare_data` (milestone 9) | `sizing` (`slu4`) | Data written without a directive becomes `.byte`/`.2byte`, sized by the named strategy; elements of one size share a directive. |
| `char_literals` (milestone 9) | `double_quoted: true` | A single character in double quotes used as a number, `"a"` → `'a'`. |
| `terminated_strings` (milestone 9) | none | String data ending in the ISA's terminator → `.cstr`; split off an instruction, it goes back on that line as an embedded string where the ISA has them (`JPS _Print "READY.\n"`). Strings with tab, line-feed and carriage-return bytes only. |
| `muted_origin` (milestone 9) | `image_start` (optional) | Carsten's two addresses: `#mute`, `#org X`, `#emit` → `.phase X`. A `*` in a phase gets a `.dephase` first when nothing after it depends on addresses; otherwise reported. `#mute` doesn't nest there, so a second one is dropped. `image_start`: where bytes go before the first `#org`. |
| `local_labels` | `prefix` or `suffix` | ca65 `@loop` → `.loop` with `prefix: '@'`; vasm `loop$` and `1$` → `.loop` and `.1` with `suffix: '$'`. BespokeASM local labels have the same scope rule. A label that would become a directive's name (`@byte` → `.byte`) is reported. |
| `anonymous_labels` | none | `:` with `:+`/`:-` (and `:>`/`:<`) → generated local labels `.anon_N`. ca65 and vasm oldstyle use the same syntax, so there is no `style`. A reference that crosses another label is reported. |
| `colonless_labels` | none | A label at column 0 without a colon (vasm) → `label:`, including a `$` local that starts with a digit (`1$`). A name followed by `=`, `equ`, `eq` or `set` is an assignment and is left alone, as is a dotted BespokeASM directive at column 0. |
| `origin_assignment` | `symbol` (default `*`) | `*= $8000` → `.org $8000`. |
| `origin_phases` (milestone 9) | none | For ca65, whose `.org` sets only the address code is assembled for: a `.org` before any bytes stays `.org`, a later one becomes `.phase`. Runs after the renames. |
| `assignment_operators` | list | `COUNT := 3` → `COUNT = 3`. Added in milestone 8: ca65's `:=` is BespokeASM's counter-coordinate operator. |
| `operand_prefixes` | `drop` list, `unsupported` list | Matched in the operands only, so a label named `z` is safe. ca65 `z:` is dropped, since relaxation picks zero page anyway. `a:` and `f:` are reported. |
| `current_address_symbol` | `symbol` | A standalone `$` (Intel, many Z80 assemblers) → `*`. `$7C` stays a hex literal. No dialect in this effort uses it; it is included because it is a simple rewrite that later dialects need. |
| `string_escapes` | `doubled_quotes: true`, `backslash: literal` | `'IT''S'` → `'IT\'S'`. Included for the same reason. `backslash: literal` (milestone 9): `"C:\"` → `"C:\\"`, for an assembler with no escapes. |

A new rule kind needs a stated reason, in the same spirit as directive aliases.

### Dialects

**6502 and W65C02S (`mos6502.yaml` and `w65c02.yaml`, the same dialects in both):**

- `ca65`: the rules in the example above, with longer lists: renames for the `.if` family, `.define`, `.error` and `.fatal` (`#error`), `.out` (`#print`), `.align`, and `.reloc` (`.dephase`, milestone 9); `origin_phases` (milestone 9); drops for `.setcpu`, `.p02`, `.pc02`, `.psc02`, `.debuginfo`, `.smart`, `.list`, `.listbytes`, `.autoimport` and `.case`; and as unsupported the blocks `.macro`, `.mac`, `.repeat`, `.struct`, `.union` and `.enum`, plus `.proc`, `.scope`, segments and their shorthands (`.code`, `.zeropage`, …), imports and exports, `.macpack`, `.feature`, `.charmap`, `.incbin`, `.dbyt`, `.local`, `.set`, `.tag`, `.assert`, `.warning` and the `.ifblank`/`.ifconst`/`.ifref`/`.ifp02` family.
- `vasm` (oldstyle, Ben Eater's): `colonless_labels`, `origin_assignment: {symbol: '*'}`, `local_labels: {suffix: '$'}`, `anonymous_labels`, and `rename_directives` for its include and conditional directives (`cond` and `ifne` as `#if`), `rorg`/`rend` (`.phase`/`.dephase`), `even` (`.align 2`), `align N` (`.align 1 << N`: vasm's argument is a bit count), and its data and space directives. Its `.org`, `.word` and `.asciiz` already assemble.
- vasm's unsupported list: the `macro`/`mac`, `rept`/`repeat`, `struct`, `dsect` and `inline` blocks, `section`, the symbol-visibility directives, `binary`/`incbin`, the `ifeq` family except `ifne`, `assert`, `str`, `abyte`, the word- and long-sized space directives and `set`.
- `.if` conditions are carried over as written. BespokeASM's `#ifdef` tests preprocessor symbols, not labels or constants as ca65's and vasm's do; milestone 11 addresses this.

**Minimal CPU, Minimal 64, Minimal 64x4 and Redux: `slu4`, Carsten Herting's assemblers.** Each config's rules match the assembler for that machine and revision. The dialect has these features:

- Elements separated by whitespace, with several statements on a line.
- `#org 0xADDR` sets the origin.
- `#mute` and `#emit` mean the same as in BespokeASM.
- Data has no directive. Its size comes from the element: hex with more than two digits, a symbol or `*` is a word; other numbers and characters are bytes; strings are bytes. Data may follow an instruction on the same line (`JPS 0xf045 "Hello, World!", 0`).
- OS entry points are declared as `#org 0xf003 _Prompt:` under `#mute`, and the configs already predefine those names.

Its rules, as built in milestone 9: `split_statements`, `bare_data: {sizing: slu4}`, `string_escapes: {backslash: literal}`, `char_literals: {double_quoted: true}`, `terminated_strings`, `muted_origin` and `rename_directives: {org: '.org', page: '.align'}`. The Redux's `muted_origin` has `image_start: 0x2000`; the Minimal CPU's has `image_start: 0x0000`, renames `#end`/`#begin` to `#mute`/`#emit` first, and has no `char_literals` or `#page`.

- `<`, `>` and `*` need no rule, because those configs turn them on with Carsten's meaning (sections 5 and 6), except that his `*` is where the bytes go, which `muted_origin` handles inside a phase.
- Carsten's `#mute` doesn't nest and BespokeASM's does. A second `#mute` before an `#emit` is dropped.
- OS entry points declared as `#org 0xf003 _Prompt:` need no rule: a label in source already takes precedence over a predefined constant of the same name. The planned `predefined_symbols` rule was dropped.

### Testing and verification

- **Unit tests:** the rule engine and each rule kind are tested in `test/`, with dialect fixtures in `test/config_files/`. Rules are checked on small sources, migrated and then assembled.
- **6502:** migrate sample ca65 and vasm programs, assemble each with ca65 and with BespokeASM, and compare the bytes.
- **Minimal:** migrate Carsten's own programs, such as `stars.asm` and `os.asm`. Assemble each with his assembler, built locally, and with BespokeASM, and compare the bytes.
  - This is a manual check; the programs aren't copied into the repository.
  - Small samples with bytes captured from his assembler become test fixtures.

## Milestone 8 notes (Nov 26, 2026)

- **Function names are no longer reserved (done first, as its own change).** smart-t's be-wozmon defines `COUNTER = $2E`, which the flow-enabled 6502 configs rejected. Expression functions (`LSB`, `BYTE0`–`BYTE9`, `COUNTER`, `COORDINATE`) are functions only when written as a call, so they were taken out of the reserved words; editors color them as functions only before `(`, and the Sublime and VS Code plugins skip a call when marking symbol uses. Found on the way: VS Code didn't color `COUNTER(stack)` in `#assert` as a flow use; fixed. Directive names stay reserved in lower case (`print:`, `entry:`, `error:` are rejected as labels); that is a candidate for the same treatment.
- **vasm's anonymous labels are ca65's.** vasm's oldstyle documentation (`doc/syntax_oldstyle.texi`) defines anonymous labels as `:` with `:+`/`:-`, not `-`/`+`, so `anonymous_labels` has no `style`. vasm local labels are `.name` or `name$`, so `local_labels` takes `prefix` or `suffix`.
- **`assignment_operators` added.** ca65's `:=` collides with BespokeASM's `:=`; msbasic assigns every `CONFIG_*` symbol with it.
- **Unsupported blocks.** A `.macro` body would otherwise assemble where it is defined, so `unsupported` takes `{start: end}` blocks and reports the body and later uses of the macro's name. A use of a macro defined in another file isn't detected; it fails to assemble as an unknown instruction.
- **Output keeps line numbers and line endings.** Output line N is input line N, so a report's line number works in both files. CRLF sources stay CRLF.
- **Includes are notes, not reports.** They don't make the exit status 1.
- **A rename to the same directive is no change.** `.org` → `.org` doesn't count, so wozmon migrates with zero changed lines.
- **The M9 rule kinds** (`split_statements`, `bare_data`, `char_literals`, `predefined_symbols`) are left for milestone 9, with the `slu4` dialect.
- **Verification.** Ben Eater's Wozmon gist and smart-t's be-wozmon migrate from `vasm` unchanged, with nothing reported, and assemble to the same bytes as a ca65 port linked by ld65; vasm itself couldn't be built here. Small ca65 and vasm samples covering every rule are test fixtures, with bytes from ca65. msbasic migrates file by file with segments, macros, `.feature` and `.macpack` reported; making it assemble is [milestone 11](#milestone-11-migrating-microsoft-basic).

## Milestone 9 notes (Nov 27, 2026)

**Goal reached:** Carsten Herting's MinOS for the Minimal 64x4 (Revision 1.1, `Programs/asm/os.asm`) migrates with `--from slu4` with nothing reported and assembles to the same 9,168 bytes as his assembler. So do the other 13 Revision 1.1 programs, and every program in the Redux, Minimal 64 and Minimal CPU repositories: 56 programs on four machines, each byte-compared against his assembler for that machine, built locally (asm.cpp for the 64x4, Redux and Minimal 64; asm.py for the Minimal CPU).

**`.phase` and `.dephase` (new directives).** MinOS stores its kernel and each program of its file system in the boot image while assembling them for another address: `#mute #org 0xfc00 #emit` moves only the address labels see, because Carsten's assemblers keep it apart from where the bytes go. BespokeASM placed every byte at its address, so it gained a phase: `.phase X` assembles for X from there while the bytes continue in place; another `.phase` re-phases from the image position; `.dephase` and `.org` end it. The user chose the name over an `.org` option or a memory-zone setting (decided Nov 27, 2026). Each line now has an image position as well as its address: the binary image, Intel HEX and byte outputs, sorting and the overlap check use the image position; labels, `*`, listings and flow analysis use the address. A phase belongs to its memory zone, like the zone's current address. vasm's `rorg`/`phase` and `rend`/`dephase` now convert instead of being reported.

**The file system.** Each MinOS program is stored as a header (name, run address, size) followed by its code. The header is ordinary data before the `#mute`, so it lands after the previous program's bytes; its run address is a label in the phase and its size a difference of two, which is the byte count because a phase's bytes are contiguous. The last line, a filler file sized `0x3000-*-2`, uses `*` as the image position, which is what Carsten's `*` always is; `muted_origin` puts a `.dephase` before it, since nothing after it depends on addresses. The other headers are file-system data in the image, not part of the program before them, so they belong after a `.dephase` too: the listing then shows their image positions, and a label put on one gets that position rather than the previous program's run address. The migration can't know that, so it leaves them in the phase (decided Nov 27, 2026: a migration doesn't make that judgment); the bytes are the same either way, and the `.dephase` lines are added by hand.

**Other assembler changes found on the way:**

- **Directive names are no longer reserved** (decided Nov 27, 2026, the open question from milestone 8): mandel.asm has a label `entry` and the Minimal CPU's textloader one named `error`. Directives are always written with their `.` or `#`. Only the built-in symbols stay reserved, for registers and mnemonics.
- **`.align` keeps an address already on a boundary.** It used to skip a whole page. This changes the 64x4 and Redux `math32lib` and `stringlib` examples, which started a page late; no other example changes.
- **Muted lines don't overlap.** The overlap check compared muted lines too, so MinOS's muted zero-page variables at 0x80 collided with the image's bytes there.
- **A tab may separate a mnemonic from its operands.**
- **An `address_lsb` operand written as a low byte, `<expr`, skips the page check**, as in Carsten's assemblers. Self-modifying code writes a placeholder fast-jump target this way (`FPA <0xcc` in the Redux MinOS).
- **Redux config:** `mbr`, `mrb` and `mrr` had two 8-bit operands; Carsten's argument table and the instructions' titles give two addresses. The 64x4 and Redux configs gained the undotted spellings Carsten's assembler also accepts (`zxr` for `xr.z`), and the 64x4's `sul` its `su.l`/`lsu`.

**Migration:**

- **Line splitting.** A BespokeASM line holds instructions, or one directive or run of data, with at most one label, so `split_statements` puts the rest on lines of their own; `.org X name:` and an instruction followed by an embedded string still share a line (see the review below). That breaks milestone 8's "output line N is input line N" for this dialect; reports keep the input line. MinOS's 1,541 lines migrate to 1,568.
- **Self-modifying code** labels an instruction's operand on the next line (`lenloop: LDI` / `lenterm: 0xff`). BespokeASM's operand labels say the same thing, so it becomes `lenloop: LDI @lenterm: 0xff`, and references are unchanged. (A first version moved the label to the instruction and added the operand's offset to every reference; the user pointed out operand labels.)
- **A mnemonic used as a value is its opcode** (`MIB AIW+0,dyvert` in the line drawer, `LDI INW` on the Minimal 64). BespokeASM has no such expression, so the opcode is written, with a note.
- **`image_start`.** The Redux assembler writes bytes from 0x2000 before the first `#org` while addresses start at 0; the Minimal CPU's starts at 0 where its config's origin is 0x8000.
- **`predefined_symbols` was dropped**: a label in source already takes precedence over a predefined constant.

**Review against existing syntax (Nov 27, 2026).** After the user pointed out operand labels, the whole syntax page was reviewed for other features the migration should use rather than work around. Adopted:

- **Operand labels** for self-modifying code (above).
- **`{directive} label:`**: `.org X name:` is one line in BespokeASM, so `#org 0x0080 PtrA:` (most of the mid-line labels) stays on its line. `.phase` and `.dephase` now take a trailing label too, like `.org`.
- **Embedded strings and `.cstr`**: the 64x4 and Redux configs have `allow_embedded_strings` with terminator 0, so `JPS _Print "READY.", 10, 0` stays one line as `JPS _Print "READY.\n"`, and `"autostart", 0` is `.cstr "autostart"`: the new `terminated_strings` rule.
- **`.align`**, now that it keeps an aligned address: ca65's `.align`, vasm's `even` (as `.align 2`) and vasm's `align N`, whose argument is a bit count (as `.align 1 << N`: the rename keeps `N` after the target), convert instead of being reported. `rename_directives` targets may now carry fixed arguments for this.
- **`#error`, `#if` and `.dephase`** for ca65's `.fatal` and `.reloc` and vasm's `cond` and `ifne`.

Considered and left: ca65's `.warning` as `#print yellow` (it needs an argument inserted, and warns only); writing Carsten's muted `#org X name:` declarations as constants (`name = X`), a style choice, since the converted form is valid BespokeASM; vasm's `dsw`-style word reservations as `.zero` (they need the count doubled).

**ca65's `.org` is BespokeASM's `.phase`.** ca65 assembles what follows for the address but leaves the bytes where the segment puts them (checked with ca65 2.18: `jmp here` after `.org $C000` assembles at $8001 in a segment loaded at $8000, and `.reloc` returns to the segment's addresses). Milestone 8 mapped `.org` to `.org`, which is right only when the segment is loaded at that address. The user chose (Nov 27, 2026) to keep a `.org` before any bytes as `.org` and make later ones `.phase`: the new `origin_phases` rule. A sample with a RAM routine after ROM code migrates to the same bytes as ca65 and ld65. See milestone 11.6 for the linker configuration.

**Testing.** `test/config_files/slu4/` holds a subset of the 64x4 config and a sample in Carsten's syntax with the Intel HEX his assembler produced; the tests migrate and assemble it and compare. The corpus check over his repositories is manual, since the programs aren't copied into this repository.

## Milestone 11: migrating Microsoft BASIC

**Goal:** Ben Eater's [msbasic](https://github.com/beneater/msbasic), mist64's reconstruction of Microsoft BASIC with Ben's `eater` target, migrated with `bespokeasm migrate --from ca65` and assembled with `w65c02.yaml`, gives the same ROM image as `ca65 -D eater msbasic.s` linked with `ld65 -C eater.cfg`. Decided Nov 26, 2026: milestone 8 only reports what msbasic needs; this milestone builds it, after milestone 9.

**Approach: extend existing features.** Decided Nov 26, 2026: where BespokeASM already has a feature close to what ca65 offers, this milestone extends that feature rather than adding a parallel one, so the language and the configuration keep one concept for each job. Each part below names the feature it extends. Source macros (11.5) are the one new feature, and they are a project of their own.

| Part | ca65 feature | Built by extending |
|:--|:--|:--|
| 11.1 | `.ifdef` on labels and constants | `#ifdef`, `#ifndef` |
| 11.2 | `.if` with `.def()`, `&&`, `\|\|`, `!` | the expression parser, and its functions such as `LSB()` |
| 11.3 | `name := <(* - start)`, a value computed from addresses | constants, resolved the way labels are |
| 11.4 | `.macpack longbranch` (`jeq` and so on) | the config's instruction macros, and `select_by_value` |
| 11.5 | `.macro`, `.repeat`, `.strlen`, `.strat` | new: source macros; string encodings extend the data directives |
| 11.6 | `.segment`, the ld65 config, `load`/`run`, generated symbols | memory zones (chained, stored in another zone, in their own address space), with `ZONE_*()` functions; no linker |

**What msbasic uses** (66 source files, about 11,800 lines, surveyed Nov 26, 2026; one build assembles the files `msbasic.s` includes for its target):

| Feature | Use | Status after milestone 8 |
|:--|:--|:--|
| `.ifdef`/`.ifndef`/`.if`/`.elseif`/`.else`/`.endif` | 1,199 directives; the build selects a machine with `-D eater` | renamed to `#ifdef` and so on, but see 11.1 and 11.2 |
| `.def(X)` and `.defined(X)` in conditions, with `&&`, `\|\|`, `!` and parentheses | 95 uses, such as `.if .def(CONFIG_SMALL) && (!.def(CONFIG_2))` | not converted (11.2) |
| `name := value` for configuration symbols | every `CONFIG_*` symbol, tested by `.ifdef` | `:=` → `=` |
| `name := expr` with `*` or labels | `define_token`, `count_tokens` and `define_error`: `token := <(*-DUMMY_START)+$80` | `:=` → `=`, but a constant can't use `*` or labels yet (11.3) |
| `=` as equality in a condition | `.if CONFIG_SCRTCH_ORDER = 2` | not converted (11.2) |
| `.segment` | 67 lines, 14 segments, placed by `eater.cfg` | reported; to become `.memzone` (11.6) |
| `.macro` | 10 macros, about 150 uses, defined in `macros.s` and used in other files | reported where defined (11.5) |
| `.repeat count, var` with `.strlen()` and `.strat()` | inside the `htasc` and `asc80` macros only | reported, inside a macro (11.5) |
| `.ifnblank` | inside `define_token` | reported (11.5) |
| `.macpack longbranch` | `jeq`, `jne`, `jcc`: 7 uses | reported (11.4) |
| `.feature force_range`, `.debuginfo +`, `.setcpu` | once each | `.feature` reported, the others dropped (11.7) |
| `@` cheap locals, `.res`, `.addr`, `.word`, `.byte`, `<(expr)` | throughout | already work |

### 11.1 Conditions on labels and constants: extend `#ifdef`

ca65's `.ifdef X` and `.def(X)` are true once `X` is defined as a label or constant earlier in the source, and `-D eater` defines the assembler symbol `eater`. BespokeASM's `#ifdef` tests preprocessor symbols only (`#define`, `-D`). msbasic depends on ca65's meaning: `defines_eater.s` sets `CONFIG_2A := 1`, `defines.s` derives `CONFIG_2` from it, and the rest of the source tests those.

- **Extend `#ifdef` and `#ifndef`** (and `defined()`, 11.2) to also see labels and constants defined on earlier lines. `-D` and `#define` keep working as now. This is already on the CHANGELOG's TODO list ("include detection of labels and constants"). Only definitions *before* the condition can count, because conditions are decided as the source is read; a later definition can't change one.
- Not chosen: migrate converting a `NAME := value` that is only tested in conditions into `#define NAME value`. It would add a second way to configure source, and needs whole-project knowledge that one-file migration doesn't have.
- Fix the include-guard bug found in milestone 7 here: a guard `#ifndef X` / `#define X` in an included file hides the whole block. msbasic includes files inside conditions.

### 11.2 Boolean conditions: extend the expression parser

`#if` already parses each side of its comparison with the same expression parser that instructions and data use; only its top-level `<expr> <comparison> <expr>` split is special, and it rejects mixing `&&`, `||` and grouping.

- **Add comparison and logical operators** (`==`, `!=`, `<`, `<=`, `>`, `>=`, `&&`, `||`, `!`) to the expression grammar, with C precedence. `#if` and `#elif` then evaluate one expression, true when nonzero, as their implied form already does. The special case and its "mixed expressions are not supported" restriction go away, and the operators work in constants and data values too, since it is one parser.
- **Add `defined(NAME)`** as an expression function, the way `LSB()` and `COUNTER()` are: a function only when written as a call. It is valid only in a preprocessor condition, as `COUNTER()` is valid only in some places.
- **Migration:** a rule converts ca65's `.def(X)` and `.defined(X)` to `defined(X)`, and `=` to `==` inside a condition. Whether that is a new rule kind or a parameter of an existing one is decided with the rule's design, by the milestone 8 bar for new rule kinds.

### 11.3 Constants computed from addresses: extend constants

In BespokeASM, a label and a constant are the same kind of symbol (a `LabelLine`); they differ in when the value is known. A label's value is its address, known once addresses are assigned. A constant's value is evaluated when its line is read, so it may only use constants defined before it, and `*` and labels are rejected:

```
"*" (the current address) is only available in instruction operands and data values; use a label
unknown label "here"; it is not defined in any source file, predefined constant, or data block
```

ca65's `:=` defines a label whose value is an expression, and msbasic's token tables rely on it: `token := <(*-DUMMY_START)+$80` makes a token's value its offset in the `DUMMY` zone.

- **Extend constants:** a constant whose expression uses `*` or a label is resolved the way a label is, after addresses are assigned, with `*` meaning the address of the constant's own line in its memory zone. A constant that uses only constants keeps being resolved when read. The syntax stays `name = expr`, so milestone 8's `:=` → `=` conversion stays right.
- **Limit:** such a constant has no value while the source is read, so it can't be used where a value is needed then: in a preprocessor condition (`#ifdef` still sees that it exists, 11.1), or to size something during pass 1 unless that use can be deferred the way `select_by_value` defers.

### 11.4 Long branches: extend instruction macros and `select_by_value`

`.macpack longbranch` gives `jeq label` and its seven siblings: a short branch when the target is in range, or the opposite branch over a `jmp` when it isn't.

- **The 6502 configs define them as instruction macros** (the `macros` section), each with two variants: the short branch (`beq target`), and the opposite branch over a `jmp` (`bne *+5`, `jmp target`).
- **Extend `select_by_value`** (milestone 5) to `relative_address` operands, choosing a form when the branch offset fits its size, as it now chooses a form when an address is in a zone. Pass-1 relaxation then picks the variant, forward references included.
- First check that `select_by_value` works inside macro variants as it does in instruction variants.
- Migration drops `.macpack longbranch` for a config that defines the macros.

### 11.5 Source macros: new, with string encodings on the data directives

`.macro name args` ... `.endmacro`, with what msbasic uses:

- Arguments substituted into instructions, directives and expressions, including as the name being assigned (`token := ...`).
- Macros that call macros, and labels defined inside a macro (`TOKEN_ADDRESS_TABLE:`).
- `.ifnblank arg` to test for an argument given or left out.
- Use from a file other than the one that defines the macro, so the macro library is included, not copied.
- A macro that switches the memory zone for its caller (11.6).

This is the one new feature in the milestone. Its design belongs to the source-macros project ([source-macros-notes.md](source-macros-notes.md)), which should build on what exists where it can, such as the instruction macros' expansion and their per-instruction placement of relative operands (milestone 4). This milestone takes its result and adds the ca65 conversion to the `ca65` dialect.

msbasic uses `.repeat`, `.strlen()` and `.strat()` only inside two macros, `htasc` (set the high bit of a string's last byte) and `asc80` (set the high bit of every byte). Those are string encodings, like the terminator `.cstr` adds from `general.cstr_terminator`. **Extend the string data directives with an encoding option** instead of adding loops and string functions; with it, msbasic's macros need neither. Syntax and where the option lives (a directive, a directive alias, or the configuration) are decided in this part's design.

### 11.6 Segments as memory zones: extend memory zones

**Decided Nov 26, 2026: BespokeASM gets no separate segment feature. ld65-style segments are built by extending memory zones**, so the configuration and syntax stay one concept rather than two parallel ones. `bespokeasm migrate` converts ca65's `.segment "NAME"` to `.memzone NAME`.

**Decisions made Nov 27, 2026:**

1. **No linker and no relocatable object format.** ld65 exists because ca65 assembles each file separately: its object files carry holes for addresses that the linker fills once it has placed each segment. BespokeASM assembles the whole program at once through `#include`, so every address is known before any byte is written, and layout happens inside the assembler. msbasic is built the same way: `msbasic.s` includes every other file into one ca65 run, and ld65 only places that one object's segments, so what it needs from ld65 is layout, not separate assembly.
2. **One zone concept, in two roles.** A memory zone stays a named address range. For any code, the zone it is assembled in is its **run zone**, and its addresses come from there. A zone may also be **stored in** another zone: its code keeps its own addresses while its bytes go at the storage zone's current position, as ld65's `load = ROM, run = RAM` does. Without that, a zone is stored at its own addresses, as now. Sketch, syntax to be designed: `#create_memzone RAMCODE 0x0200 0x02ff stored_in ROM`.
3. **`.phase` is the inline form of the same thing.** Milestone 9 gave every line a run address and a storage position; a stored-in zone sets that pair for a whole zone, and `.phase` for a block inside one (each MinOS program at 0xfc00). Both stay.
4. **The roles are checked differently.** Run ranges may overlap: MinOS's twelve programs all run at 0xfc00, and overlays share one RAM area. Storage may not, since each position holds one byte; milestone 9's overlap check already compares storage positions. Fill (ld65's `fill = yes`) belongs to storage.
5. **A copier gets its numbers from expression functions**, called like `LSB()`: the run address, storage position and size of a zone, sketched as `ZONE_START(name)`, `ZONE_LOAD(name)` and `ZONE_SIZE(name)`. They replace the symbols ld65 generates with `define = yes` (`__DATA_RUN__`, `__DATA_LOAD__`, `__DATA_SIZE__`), which cc65's `copydata` uses, without magic label names. Their values are known only after layout, so they resolve the way 11.3's address-dependent constants do. Names to be settled in the design.
6. **A zone may declare an address space other than the CPU's.** Every zone lives in an address space, by default the CPU's, which `GLOBAL` spans. A zone may instead declare another space with its own size, such as the Minimal 64x4's 512KB flash (sketch: `#create_memzone FLASH 0x00000 0x7ffff space=flash`), and an ISA config can predefine spaces next to its predefined zones.
   - Code runs only in the CPU's space: a zone in another space can be a storage target but not a run zone. Its labels are still values, so `LSB(table)`, `BYTE1(table)` and `BYTE2(table)` give a flash address's bytes for an instruction such as `RZP`.
   - Each space has its own image: the overlap check, fill and output work per space. Intel HEX has extended-address records for images beyond 64KB. With more than one non-CPU space, each would want its own output file, as ld65's `file =` gives a memory area.
   - There is no mapping between spaces: a space is a separate numbering, not a window onto the CPU's addresses. Code is copied between them at run time.
   - With it, MinOS's layout says what it means: its flash banks become zones in a `FLASH` space, and the kernel, tables and file system are stored in them, instead of the source encoding banks in `#org 0x1000`-style addresses. Milestone 9's check that a storage position fits the CPU's address space becomes a check against the storage zone's space.
7. **`migrate` reads the linker configuration.** A `--linker-config` option (name to be settled) converts an ld65 configuration into zone declarations: memory areas into zones, segment placement into chained zones, `run` addresses into stored-in zones, and `file = ""` areas into muted zones. msbasic needs `eater.cfg` converted this way.
8. **Relocation when a program is loaded, if it is ever wanted, is an output format, not a linker.** A loader that places a program wherever there is room needs the offsets of every word that holds an address, as o65 and CP/M's PRL files list them. BespokeASM knows which operands are addresses, so it could write such a table with the image. Not planned; recorded as the direction for the "relocatable blocks" the user wants eventually.

**ca65's `.org` (decided Nov 27, 2026, built in milestone 9).** ca65's `.org` is BespokeASM's `.phase`: ca65 resolves the addresses of what follows, and the linker still decides where its bytes go (checked with ca65 2.18; see the [milestone 9 notes](#milestone-9-notes-nov-27-2026)). The `ca65` dialect's `origin_phases` rule keeps a `.org` before any bytes as `.org`, since it states where the code is loaded, and makes a later one `.phase`; `.reloc` becomes `.dephase`. A program with a RAM routine after its ROM code migrates to the same bytes as ca65 and ld65. With the linker configuration available (decision 7), the first `.org` can be checked against the real load address.

ld65 places segments from a linker configuration: each memory area (`BASROM: start = $8000, size = $7E00, fill = yes`) holds its segments in the listed order, each starting where the previous one ends. The source switches segments freely, and the code for one segment is the concatenation, in source order, of every stretch written to it. msbasic's `keyword_rts` macro writes to `VECTORS`, `KEYWORDS` and `DUMMY` in one call.

What memory zones already provide:

- **Switching back and forth.** Separate stretches of code in one zone are assembled as if concatenated in source order, which is how a segment collects its code.
- **A named target.** `.memzone NAME` is the counterpart of `.segment "NAME"`.
- **Address checks**, and the zones `select_by_value` tests against.
- **Space with no output.** `#mute` assembles without emitting, which covers ld65 memory with `file = ""` (`ZEROPAGE`, `INPUT_BUFFER`) and msbasic's `DUMMY` token counter, where each `define_token` reserves a byte and a token's value is its offset (with 11.3). Muted code may share addresses with other code: since milestone 9 a muted line puts no bytes in the image, so it overlaps nothing (msbasic's `DUMMY` and `ZEROPAGE` both start at `$0000`).
- **Fill.** `-s`, `-e` and `-f` pad the whole image, which is all a single ROM needs.
- **A run address apart from storage**, per line, since milestone 9's `.phase`.

What memory zones need for this, besides decisions 2 to 6:

- **A floating start.** A zone placed after another zone, so that a chain of zones lays out like an ld65 memory area: each zone starts where the previous one's content ends. Syntax to be designed; a sketch is `#create_memzone KEYWORDS after VECTORS`. Starts then depend on sizes, so they are settled in pass-1 relaxation (milestone 5), which already reruns address assignment until nothing changes. An end bound (ld65's area `size`) is still checked.
- **A zone selection that persists past its file.** An included file starts in `GLOBAL` and the includer's zone returns afterwards; ld65's active segment carries across includes, and a macro can switch it for its caller (`keyword_rts` leaves the caller in `KEYWORDS`). Needed once macros switch zones, so designed with 11.5.
- **To confirm in the design:** what `.org` means inside a zone with a floating start, and inside a stored-in zone.

Where the layout lives follows from this: as `#create_memzone` lines, in source or in the ISA config's `predefined.memory_zones`, like any other zone, written by hand or converted from an ld65 configuration (decision 7).

### 11.7 Smaller items

- `.feature force_range`: check whether any msbasic value needs ca65's truncation of out-of-range values, and drop the directive if none does.
- `.debuginfo +` is dropped already; `.setcpu` likewise.
- **`*` in directive arguments.** `*` is allowed only in instruction operands and data values, so `.res $FFFA - *, 0` (a common ca65 and vasm way to pad up to the vectors; the ca65 port of Wozmon uses it) and `.phase *+N` are errors. Allow it in the address and count arguments of `.org`, `.phase`, `.fill`/`.zero` and `.align` as one change, with `*` the address of the directive's own line. A count that depends on `*` must still settle during relaxation. Raised in the PR #59 review (Nov 27, 2026).

### Order and verification

11.1 and 11.2 first (the preprocessor, and useful to native source), then 11.3 and 11.4, then 11.5 when source macros exist, then 11.6. Each part gets tests on small samples with bytes captured from ca65, as in milestone 8. The end-to-end check is manual, because msbasic isn't copied into the repository: migrate every file, assemble, and compare with the ca65 and ld65 image byte for byte.

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
| `--from` left out, or naming a dialect the config doesn't declare | usage error | lists the config's dialects |
| `-o` names the source file | usage error | `--output-file is the source file; migrate never overwrites its input` |
| `.phase` outside the address space | error | `.phase address 65536 (0x10000) is outside the address space (0x0 to 0xffff)` |
| a phased line's bytes past the end of the address space | error | `the bytes of this line would go at image position …, past the end of the address space` |
| a `migrations` rule kind BespokeASM doesn't have, or a bad parameter | config error | by config path |
| a line a migration rule can't convert | reported | `; MIGRATE: <reason>: <line>` in the output, plus the summary |
| an included file | note | `includes <file>; migrate it separately`, in the summary only |

## Suggested implementation order

Each milestone ends with tests, pre-commit, and byte comparison of all existing examples against the previous milestone.

1. Expressions and literals: `low_high_operators` and `current_address`, with both semantics each; octal literals and the `B` suffix; `~`. Turn them on in the Minimal CPU, Minimal 64, Minimal 64x4 and Redux configs, byte-compared against Carsten's assembler.
2. Immediate `prefix` and directive aliases (with `.fill N`).
3. Per-operand `enclosure` and the `indirect_indexed_numeric` type.
4. `offset_base`.
5. `select_by_value` and pass-1 relaxation.
6. The 6502 and W65C02S configs, with every opcode byte-compared against ca65 fixtures.
7. Ben Eater programs, platform include, docs, wiki and editor checks. (The `-s`/`-e`/`-f` number forms were added early, during milestone 6.)
8. `bespokeasm migrate`: the rule engine and the 6502 `ca65` and `vasm` dialects.
9. The `slu4` dialect in the Minimal CPU, Minimal 64, Minimal 64x4 and Redux configs, byte-compared against Carsten's assemblers, with `.phase`/`.dephase` for MinOS.
10. *(Not yet assigned.)*
11. [Migrating Microsoft BASIC](#milestone-11-migrating-microsoft-basic), extending existing features where possible: `#ifdef` on labels and constants, boolean operators and `defined()` in expressions, constants computed from addresses, long branches as instruction macros, source macros with string encodings on the data directives, and memory zones that place code the way ld65 places segments, including code stored apart from where it runs and storage in its own address space, with `migrate` reading the ld65 configuration. No linker.
