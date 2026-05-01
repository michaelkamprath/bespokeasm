# Vim Syntax Highlighting — Feature Parity Improvement Plan

## Background

BespokeASM generates editor syntax highlighting for three targets: VSCode, Sublime Text, and vim. The VSCode and Sublime generators produce rich, context-aware highlighting using scoped region models (TextMate grammar and Sublime syntax push/pop contexts respectively). The vim generator currently uses only flat `syn match` and `syn keyword` patterns with no scoped regions, leaving several gaps.

This plan brings the vim syntax file to parity with the other editors **at the grammar layer** — no vim plugin required. Semantic label-usage highlighting and hover-equivalent documentation are covered separately by `vim-semantic-and-hover-plan.md`.

## File to Modify

**`src/bespokeasm/configgen/vim/__init__.py`**

Read this file fully before starting. All changes are to two methods: `_generate_vim_color_lines` and `_build_syntax_vim`. Apply changes in the order listed — several depend on ordering within the generated vim script.

---

## Change 1 — Remove Intrusive Editor-Level Color Overrides

**Why:** Setting `hi Normal`, `hi Visual`, and `hi CursorLine` in a syntax file overrides the user's editor-wide colorscheme for every buffer, not just assembly files. VSCode and Sublime keep theme colors in a separate theme file; vim syntax files should do the same.

In `_generate_vim_color_lines`, delete the entire block that emits these three groups (approximately lines 112–126):

```python
# DELETE these lines:
bg_color = DEFAULT_COLOR_SCHEME.get_color(SyntaxElement.BACKGROUND)
fg_color = DEFAULT_COLOR_SCHEME.get_color(SyntaxElement.FOREGROUND)
bg_cterm = self._get_vim_cterm_approximation(bg_color)
fg_cterm = self._get_vim_cterm_approximation(fg_color)
lines.append(f'hi Normal guifg={fg_color} guibg={bg_color} ctermfg={fg_cterm} ctermbg={bg_cterm}')
selection_color = DEFAULT_COLOR_SCHEME.get_color(SyntaxElement.SELECTION)
selection_cterm = self._get_vim_cterm_approximation(selection_color)
lines.append(f'hi Visual guibg={selection_color} ctermbg={selection_cterm}')
line_highlight_color = DEFAULT_COLOR_SCHEME.get_color(SyntaxElement.LINE_HIGHLIGHT)
line_highlight_cterm = self._get_vim_cterm_approximation(line_highlight_color)
lines.append(f'hi CursorLine guibg={line_highlight_color} ctermbg={line_highlight_cterm} cterm=NONE gui=NONE')
```

The method body should begin immediately at `lines = []` followed by the `vim_mappings` list.

---

## Change 2 — Add Missing Color Scheme Mappings

**Why:** Three syntax elements defined in `color_scheme.py` are used by VSCode and Sublime but never mapped in the vim generator. `AssignOp` exists in the vim output but only as a `hi def link` fallback with no explicit color.

In `_generate_vim_color_lines`, add three tuples to the `vim_mappings` list:

```python
(f'{lang_group}Param', SyntaxElement.PARAMETER),
(f'{lang_group}Separator', SyntaxElement.PUNCTUATION_SEPARATOR),
(f'{lang_group}AssignOp', SyntaxElement.OPERATOR),
```

Then in `_build_syntax_vim`, **delete** the now-redundant fallback (since AssignOp gets an explicit color above):

```python
# DELETE this line from the hi def link block:
lines.append(f'hi def link {lang_group}AssignOp Operator')
```

---

## Change 3 — Add `contained` Helper Patterns

**Why:** These two patterns are the building blocks for contextual operand highlighting. Both are `contained`, meaning they only fire inside regions that explicitly list them — they will not match at the top level and interfere with other tokens.

In `_build_syntax_vim`, immediately after the existing `{lang}Escape` syn match line, insert:

```python
lines.append(fr'syn match {lang_group}Separator /,/ contained')
lines.append(fr'syn match {lang_group}Param /\<[A-Za-z_][A-Za-z0-9_.]*\>/ contained')
```

**Critical ordering requirement:** `{lang}Param` must be emitted into the vim script **before** `{lang}CompilerLabel`. In vim, when two `syn match` patterns tie (same start position, same match length), the one defined **later** wins. Since `CompilerLabel` is more specific and must win over the catch-all `Param`, `Param` must appear earlier in the generated file. Do not reorder these relative to the CompilerLabel match that follows later in the method.

---

## Change 4 — Replace Bracket/Paren `syn match` with `syn region`

**Why:** Global `syn match` for `[`, `]`, `[[`, `]]`, `(`, `)` matches brackets anywhere in the file and provides no context for their contents. Scoped regions allow bracket interiors to have their own contained patterns (registers, numbers, labels, nested brackets).

Remove these three existing lines from near the end of `_build_syntax_vim`:

```python
# REMOVE:
lines.append(fr'syn match {lang_group}Bracket /\[\|\]/')
lines.append(fr'syn match {lang_group}DoubleBracket /\[\[\|\]\]/')
lines.append(fr'syn match {lang_group}Paren /(\|)/')
```

Define the shared `contains` string for bracket/paren interiors (no strings — strings don't appear inside `[...]`):

```python
bracket_contains = ','.join([
    f'{lang_group}Register',
    f'{lang_group}HexNumber',
    f'{lang_group}BinNumber',
    f'{lang_group}DecNumber',
    f'{lang_group}CharNumber',
    f'{lang_group}CompilerLabel',
    f'{lang_group}OperandLabelAt',
    f'{lang_group}OperandLabelName',
    f'{lang_group}Operator',
    f'{lang_group}DoubleBracketExpr',
    f'{lang_group}BracketExpr',
    f'{lang_group}ParenExpr',
    f'{lang_group}Param',
])
```

Replace with three region definitions:

```python
lines.append(
    fr'syn region {lang_group}DoubleBracketExpr '
    fr'matchgroup={lang_group}DoubleBracket '
    fr'start=/\[\[/ end=/\]\]/ oneline '
    fr'contains={bracket_contains}'
)
lines.append(
    fr'syn region {lang_group}BracketExpr '
    fr'matchgroup={lang_group}Bracket '
    fr'start=/\[\(\[\)\@!/ end=/\]/ oneline '
    fr'contains={bracket_contains}'
)
lines.append(
    fr'syn region {lang_group}ParenExpr '
    fr'matchgroup={lang_group}Paren '
    fr'start=/(/ end=/)/ oneline '
    fr'contains={bracket_contains}'
)
```

**Regex notes:**
- `\(\[\)\@!` is vim's negative lookahead — it matches `[` only when not followed by another `[`, so single brackets do not match at `[[`
- `DoubleBracketExpr` must be emitted before `BracketExpr` in the output (conventional; the lookahead handles correctness regardless)
- These regions are **not** `contained` — they fire at the top level too, since `[addr]` indirect addressing can appear in any operand context

---

## Change 5 — Replace Instruction/Macro `syn match` with `syn region`

**Why:** This is the most impactful change. With flat `syn match`, the instruction mnemonic is highlighted but its operands get no contextual treatment. With `syn region`, everything after the mnemonic until end-of-line or a comment is a scoped operand context where registers, labels, numbers, brackets, commas, and bare identifiers are all highlighted appropriately.

Remove:

```python
# REMOVE:
if instructions_alt:
    lines.append(fr'syn match {lang_group}Instruction /\<' + instructions_alt + r'\>/')
if macros_alt:
    lines.append(fr'syn match {lang_group}Macro /\<' + macros_alt + r'\>/')
```

Define the operand `contains` string (adds `String` and `Separator` compared to the bracket list):

```python
operand_contains = ','.join([
    f'{lang_group}String',
    f'{lang_group}Register',
    f'{lang_group}HexNumber',
    f'{lang_group}BinNumber',
    f'{lang_group}DecNumber',
    f'{lang_group}CharNumber',
    f'{lang_group}CompilerLabel',
    f'{lang_group}OperandLabelAt',
    f'{lang_group}OperandLabelName',
    f'{lang_group}Operator',
    f'{lang_group}Separator',
    f'{lang_group}DoubleBracketExpr',
    f'{lang_group}BracketExpr',
    f'{lang_group}ParenExpr',
    f'{lang_group}Param',
])
```

Build the end pattern. BespokeASM allows multiple instructions on a single line, so an `InstrLine`/`MacroLine` region must also terminate just before the next operation mnemonic — otherwise the second mnemonic would be swallowed as an operand of the first:

```python
operations_alt = self._alternation(list(self.model.operation_mnemonics))
operation_line_end = (
    fr'\s*\ze\<{operations_alt}\>\|\s*\ze;\|$'
    if operations_alt else r'\s*\ze;\|$'
)
```

Replace with:

```python
if instructions_alt:
    lines.append(
        fr'syn region {lang_group}InstrLine '
        fr'matchgroup={lang_group}Instruction '
        fr'start=/\<{instructions_alt}\>/ '
        fr'end=/{operation_line_end}/ oneline '
        fr'contains={operand_contains}'
    )
if macros_alt:
    lines.append(
        fr'syn region {lang_group}MacroLine '
        fr'matchgroup={lang_group}Macro '
        fr'start=/\<{macros_alt}\>/ '
        fr'end=/{operation_line_end}/ oneline '
        fr'contains={operand_contains}'
    )
```

**Regex notes:**
- `\s*\ze;\|$` means "optional whitespace, then stop just before `;`, OR match end of line." The `\ze` assertion (vim's end-of-match marker) prevents consuming the `;`, leaving it available for the top-level comment pattern to match.
- `\s*\ze\<{operations_alt}\>` adds a third terminator: stop just before the next operation mnemonic on the same line. Without consuming it, the next mnemonic is free to open its own `InstrLine`/`MacroLine` region. `operation_mnemonics` is the union of instructions and macros, so this works symmetrically for both region types.

**How `Param` works here:** `Register` is a `syn keyword` and always beats `syn match`. `CompilerLabel` is defined later in the script than `Param` and beats it on ties. Everything else that looks like a bare identifier (a label reference or operand variable) falls through to `Param`. This is the same logic Sublime's `operands_variables` context uses.

---

## Change 6 — Replace Directive/Datatype `syn match` with `syn region`

**Why:** Same reasoning as Change 5. Directive arguments (addresses, constants, expressions) currently get no contextual highlighting.

Remove:

```python
# REMOVE:
for w in directives_words:
    lines.append(fr'syn match {lang_group}Directive /\s*\.' + self._vim_escape(w) + r'\>/')
for w in datatypes_words:
    lines.append(fr'syn match {lang_group}DataType /\s*\.' + self._vim_escape(w) + r'\>/')
```

Define directive contents (no comma separator needed):

```python
directive_contains = ','.join([
    f'{lang_group}String',
    f'{lang_group}HexNumber',
    f'{lang_group}BinNumber',
    f'{lang_group}DecNumber',
    f'{lang_group}CharNumber',
    f'{lang_group}CompilerLabel',
    f'{lang_group}Operator',
    f'{lang_group}DoubleBracketExpr',
    f'{lang_group}BracketExpr',
    f'{lang_group}ParenExpr',
    f'{lang_group}Param',
])
```

Replace with:

```python
for w in directives_words:
    lines.append(
        fr'syn region {lang_group}DirectiveLine '
        fr'matchgroup={lang_group}Directive '
        fr'start=/\s*\.{self._vim_escape(w)}\>/ '
        fr'end=/\s*\ze;\|$/ oneline '
        fr'contains={directive_contains}'
    )
for w in datatypes_words:
    lines.append(
        fr'syn region {lang_group}DataTypeLine '
        fr'matchgroup={lang_group}DataType '
        fr'start=/\s*\.{self._vim_escape(w)}\>/ '
        fr'end=/\s*\ze;\|$/ oneline '
        fr'contains={directive_contains}'
    )
```

The `{lang}Directive` and `{lang}DataType` highlight groups are preserved — they are used via `matchgroup` on the region start matches, so their colors still apply to the directive keywords themselves. Only the region names changed to `DirectiveLine`/`DataTypeLine`.

---

## Change 7 — Add Missing `hi def link` Fallbacks

**Why:** Several highlight groups currently only have explicit `hi guifg=... ctermfg=...` colors. Terminals with `termguicolors` disabled (no true-color support) see nothing for these tokens. `hi def link` provides a fallback to a standard vim highlight group.

In the `hi def link` block in `_build_syntax_vim`, add:

```python
lines.append(f'hi def link {lang_group}CompilerLabel Constant')
lines.append(f'hi def link {lang_group}StringPunc Delimiter')
lines.append(f'hi def link {lang_group}Bracket Delimiter')
lines.append(f'hi def link {lang_group}DoubleBracket Delimiter')
lines.append(f'hi def link {lang_group}Paren Delimiter')
lines.append(f'hi def link {lang_group}Separator Delimiter')
lines.append(f'hi def link {lang_group}Param Identifier')
lines.append(f'hi def link {lang_group}PreProcPunc PreProc')
```

Confirm `hi def link {lang}AssignOp Operator` has been removed (done in Change 2).

---

## Change 8 — Update Tests

In `test/test_configgen.py`, update assertions that verify the generated vim syntax output.

**Assert these patterns are absent:**
- `syn match {lang}Instruction` (replaced by `syn region {lang}InstrLine`)
- `syn match {lang}Macro` (replaced by `syn region {lang}MacroLine`)
- `syn match {lang}Directive` (replaced by `syn region {lang}DirectiveLine`)
- `syn match {lang}DataType` (replaced by `syn region {lang}DataTypeLine`)
- `syn match {lang}Bracket /\[` (replaced by region)
- `syn match {lang}DoubleBracket` (replaced by region)
- `syn match {lang}Paren` (replaced by region)
- `hi Normal` (removed)
- `hi Visual` (removed)
- `hi CursorLine` (removed)
- `hi def link {lang}AssignOp` (removed — now has explicit color)

**Assert these patterns are present:**
- `syn match {lang}Separator /,/ contained`
- `syn match {lang}Param` with `contained`
- `syn region {lang}InstrLine matchgroup={lang}Instruction` (if the test ISA has instructions)
- `syn region {lang}MacroLine matchgroup={lang}Macro` (if the test ISA has macros)
- `syn region {lang}BracketExpr matchgroup={lang}Bracket`
- `syn region {lang}DoubleBracketExpr matchgroup={lang}DoubleBracket`
- `syn region {lang}ParenExpr matchgroup={lang}Paren`
- `hi def link {lang}CompilerLabel Constant`
- `hi def link {lang}Param Identifier`
- `hi def link {lang}Separator Delimiter`

Run the full test suite after all changes: `pytest test/test_configgen.py`

---

## Summary

| Change | Effect |
|---|---|
| 1 | Stops overriding the user's editor-wide colorscheme |
| 2 | All color scheme elements now have explicit vim colors |
| 3 | Comma separators and catch-all operand identifiers available as contained patterns |
| 4 | `[...]` and `[[...]]` are scoped regions with contextual contents |
| 5 | Instruction/macro operands highlighted in context: registers, labels, numbers, brackets, commas, and bare identifiers all get appropriate colors only in operand position |
| 6 | Directive arguments get the same contextual treatment |
| 7 | Terminals without true-color support get reasonable fallback highlighting for all groups |
| 8 | Tests updated to reflect the new structure |
