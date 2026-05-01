# Vim Semantic Highlighting & Hover-Equivalent Plan

## Background

The grammar-layer vim syntax file (see `vim-syntax-improvement-plan.md`) brings vim to parity with VSCode/Sublime for everything that can be expressed as static syntax patterns. Two features remain:

1. **Semantic label-usage highlighting** — recognizing identifiers that are *actually defined as labels in the current buffer* and highlighting them differently from arbitrary bare identifiers. VSCode/Sublime fake this with grammar rules that match label-shaped tokens; we can do better in vim by actually scanning the buffer.
2. **Hover documentation** — vim has no native hover, but it has `K` (keyword lookup) and `popup_atcursor()` (floating windows in vim 8.2+ / Neovim). The doc data already exists — commit `7a4c747` added hover docs for directives, registers, and expression functions for the other editors.

Both features ship as **generated runtime files** alongside the existing `syntax/<ft>.vim` and `ftdetect/<ft>.vim`. No vim plugin manager required — files drop into the user's `~/.vim/` (or `~/.config/nvim/`) and vim auto-loads them.

## Files to Modify / Create

- **Modify:** `src/bespokeasm/configgen/vim/__init__.py` — add generation of two new files.
- **Generated (new):** `<export_dir>/ftplugin/<vim_filetype>.vim` — runtime label scan + `K` mapping + popup glue.
- **Generated (new):** `<export_dir>/autoload/<vim_filetype>_docs.vim` — static dict of `mnemonic → markdown docstring` (loaded lazily on first hover).
- **Modify:** `src/bespokeasm/configgen/vim/__init__.py::_build_syntax_vim` — add `LabelUsage` to relevant `contains=` lists and `hi def link` block (Change 9 in the syntax plan, folded into this work).
- **Modify:** `test/test_configgen.py` — new tests for ftplugin and autoload outputs.

Apply the changes in the order below.

---

## Change 1 — Add `LabelUsage` to the Syntax File

**Why:** The runtime ftplugin will populate a dynamically-defined `syn match <ft>LabelUsage` group. The static syntax file must (a) reserve the highlight group name with a `hi def link` fallback and an explicit color, and (b) include `LabelUsage` in the `contains=` lists of the regions where label references can appear (operand, bracket).

In `_build_syntax_vim`, add `LabelUsage` to **two** contains lists. **Do not** add it to `directive_contains` in the first pass — directive arguments rarely reference labels, and avoiding it keeps the surface area smaller. (Revisit if users complain.)

```python
operand_contains = ','.join([
    # ... existing entries ...
    f'{lang_group}LabelUsage',
])
bracket_contains = ','.join([
    # ... existing entries ...
    f'{lang_group}LabelUsage',
])
```

In the `hi def link` block, add:

```python
lines.append(f'hi def link {lang_group}LabelUsage Identifier')
```

In `_generate_vim_color_lines`, add to `vim_mappings`:

```python
(f'{lang_group}LabelUsage', SyntaxElement.LABEL_USAGE),
```

`SyntaxElement.LABEL_USAGE` already exists at `src/bespokeasm/configgen/color_scheme.py:34`.

**Critical ordering:** The `LabelUsage` group is only ever defined dynamically by the ftplugin (via `syn match ... contained`). The static syntax file does not emit a `syn match` for it. The ftplugin runs *after* the syntax file has loaded (vim's `:setfiletype` flow runs `syntax/<ft>.vim` first, then `ftplugin/<ft>.vim`), so the ftplugin's match is the latest definition and wins on ties against `Param` and `CompilerLabel` inside the contains regions.

---

## Change 2 — Generate `ftplugin/<vim_filetype>.vim`

**Why:** This file holds the runtime semantic scan and the hover bindings. It is loaded automatically by vim whenever `setfiletype <vim_filetype>` runs.

Add a new method `_build_ftplugin_vim(self, vim_filetype: str) -> str` to `VimConfigGenerator`. Call it from `generate()` and write the result to `<export_dir>/ftplugin/<vim_filetype>.vim`.

The generated file has these sections (in order):

### 2a. Guard and buffer-local autocmd group

```vim
if exists("b:did_<ft>_ftplugin") | finish | endif
let b:did_<ft>_ftplugin = 1

augroup bespokeasm_<ft>
  autocmd! * <buffer>
augroup END
```

### 2b. Label scan function

```vim
function! s:ScanLabels_<ft>() abort
  let l:globals = {}
  let l:locals = {}
  for l:lnum in range(1, line('$'))
    let l:line = getline(l:lnum)
    " Strip trailing comment
    let l:line = substitute(l:line, ';.*$', '', '')
    " Global label: ^<whitespace><.?word>:
    let l:m = matchlist(l:line, '^\s*\(\.\?\w\+\)\s*:')
    if !empty(l:m)
      let l:globals[l:m[1]] = 1
      continue
    endif
    " Operand/local label: ^<whitespace>@<word>:
    let l:m = matchlist(l:line, '^\s*@\(\w\+\)\s*:')
    if !empty(l:m)
      let l:locals[l:m[1]] = 1
    endif
  endfor
  let b:bespokeasm_<ft>_globals = keys(l:globals)
  let b:bespokeasm_<ft>_locals = keys(l:locals)
endfunction
```

### 2c. Apply scan to syntax

```vim
function! s:ApplyLabelHighlight_<ft>() abort
  silent! syntax clear <ft>LabelUsage
  if !empty(get(b:, 'bespokeasm_<ft>_globals', []))
    let l:alt = join(map(copy(b:bespokeasm_<ft>_globals), 'escape(v:val, ''/\.'')'), '\|')
    execute 'syntax match <ft>LabelUsage /\<\%(' . l:alt . '\)\>/ contained'
  endif
  if !empty(get(b:, 'bespokeasm_<ft>_locals', []))
    let l:alt = join(map(copy(b:bespokeasm_<ft>_locals), 'escape(v:val, ''/\.'')'), '\|')
    execute 'syntax match <ft>LabelUsage /\%(@\)\@<=\<\%(' . l:alt . '\)\>/ contained'
  endif
endfunction

function! s:RefreshLabels_<ft>() abort
  call s:ScanLabels_<ft>()
  call s:ApplyLabelHighlight_<ft>()
endfunction
```

Two notes:
- The locals match uses `\%(@\)\@<=` (positive lookbehind for `@`) so a local `foo` defined as `@foo:` is highlighted at `@foo` references but not at bare `foo` references — local labels are scoped to their `@`-prefix.
- We reuse a single `LabelUsage` highlight group for both globals and locals in v1. If users want different colors, split into `LabelUsage` and `LocalLabelUsage` later — the generator already mirrors this split for `OperandLabelName`.

### 2d. Performance guard

Skip the scan on very large buffers — re-scanning a 50k-line file on every `CursorHold` is felt. Cap at 10k lines, overridable:

```vim
if !exists("g:bespokeasm_<ft>_max_scan_lines")
  let g:bespokeasm_<ft>_max_scan_lines = 10000
endif

function! s:RefreshLabelsGuarded_<ft>() abort
  if line('$') > g:bespokeasm_<ft>_max_scan_lines | return | endif
  call s:RefreshLabels_<ft>()
endfunction
```

Have the autocmds call `RefreshLabelsGuarded_<ft>` instead of the unguarded version.

### 2e. Autocmd triggers

```vim
autocmd bespokeasm_<ft> BufReadPost <buffer> call s:RefreshLabelsGuarded_<ft>()
autocmd bespokeasm_<ft> BufWritePost <buffer> call s:RefreshLabelsGuarded_<ft>()
autocmd bespokeasm_<ft> CursorHold <buffer> call s:RefreshLabelsGuarded_<ft>()
autocmd bespokeasm_<ft> CursorHoldI <buffer> call s:RefreshLabelsGuarded_<ft>()

" Initial scan when the ftplugin loads on an already-open buffer
call s:RefreshLabelsGuarded_<ft>()
```

`CursorHold` fires after `&updatetime` ms of inactivity (default 4000). Document in a generator-emitted comment that users can `set updatetime=1000` for snappier updates.

### 2f. Hover binding

```vim
setlocal keywordprg=:call\ <ft>_docs#Show(expand('<cword>'))
```

This rebinds `K` to call our autoload function with the word under the cursor. We use `keywordprg` rather than mapping `K` directly so user remappings of `K` still work via the standard mechanism.

### 2g. Optional auto-popup on hover

Off by default (annoys users who don't want it):

```vim
if get(g:, 'bespokeasm_<ft>_auto_hover', 0)
  autocmd bespokeasm_<ft> CursorHold <buffer>
        \ call <ft>_docs#PopupAtCursor(expand('<cword>'))
endif
```

---

## Change 3 — Generate `autoload/<vim_filetype>_docs.vim`

**Why:** Vim's autoload mechanism lazy-loads files in `autoload/` only when their namespaced functions are called. Putting the docs dict here means startup cost is zero — the file is only read the first time the user presses `K`.

Naming: file is `autoload/<vim_filetype>_docs.vim`, functions inside use `<vim_filetype>_docs#FuncName` (vim's `#` = path-to-file mapping). Note `<vim_filetype>` is already lowercase no-dashes from the generator's sanitization step; if it ever could contain `-` or `.`, sanitize again here — autoload names are strict.

### 3a. Generate the docs dict

Add a method `_collect_hover_docs(self) -> dict[str, str]` to the generator. It should pull the same data the VSCode/Sublime hover generators use — likely from `self.model.instructions`, `self.model.macros`, `self.model.registers`, the directive sets in `bespokeasm.assembler.keywords`, and `EXPRESSION_FUNCTIONS_SET`. Each value is a markdown string.

**Reuse, don't reinvent:** Find where the VSCode hover docs are built (search for `hoverDocs`, `description`, or grep around commit `7a4c747`). Extract that logic into a shared helper on the model or a new module under `bespokeasm/configgen/` that both VSCode/Sublime and vim generators import. Do not maintain two parallel implementations.

### 3b. Emit the dict

```vim
let s:docs = {
\   'mov': "...markdown string...",
\   '.org': "...",
\   ...
\ }
```

Escape values for vim string literals: `"` → `\"`, `\` → `\\`, newlines → `\n`. Add a helper `_vim_string_escape(s: str) -> str` to the generator.

### 3c. Lookup function

```vim
function! <ft>_docs#Show(word) abort
  let l:key = a:word
  if !has_key(s:docs, l:key)
    " Try with leading dot for directives
    if has_key(s:docs, '.' . l:key)
      let l:key = '.' . l:key
    else
      echo 'No docs for ' . a:word
      return
    endif
  endif
  call s:OpenPreview(l:key, s:docs[l:key])
endfunction

function! s:OpenPreview(title, body) abort
  let l:lines = split(a:body, '\n')
  silent! pedit __bespokeasm_docs__
  wincmd P
  setlocal buftype=nofile bufhidden=wipe noswapfile
  setlocal filetype=markdown
  silent %delete _
  call setline(1, ['# ' . a:title, ''] + l:lines)
  setlocal nomodifiable
  wincmd p
endfunction
```

### 3d. Popup variant (vim 8.2+ / Neovim only)

```vim
function! <ft>_docs#PopupAtCursor(word) abort
  let l:key = has_key(s:docs, a:word) ? a:word :
        \ (has_key(s:docs, '.' . a:word) ? '.' . a:word : '')
  if l:key == '' | return | endif
  let l:lines = ['# ' . l:key, ''] + split(s:docs[l:key], '\n')
  if has('popupwin')
    call popup_atcursor(l:lines, {'border': [], 'padding': [0,1,0,1]})
  elseif has('nvim') && exists('*nvim_open_win')
    let l:buf = nvim_create_buf(v:false, v:true)
    call nvim_buf_set_lines(l:buf, 0, -1, v:false, l:lines)
    call nvim_open_win(l:buf, v:false, {
          \ 'relative': 'cursor', 'row': 1, 'col': 0,
          \ 'width': 60, 'height': len(l:lines),
          \ 'style': 'minimal', 'border': 'rounded'
          \ })
  endif
endfunction
```

Both branches are no-ops on vim versions that don't support popups, which is the right failure mode.

---

## Change 4 — Generator Wiring

In `VimConfigGenerator.generate()`, after the existing syntax + ftdetect writes, add:

```python
ftplugin_dir = os.path.join(self.export_dir, 'ftplugin')
autoload_dir = os.path.join(self.export_dir, 'autoload')
Path(ftplugin_dir).mkdir(parents=True, exist_ok=True)
Path(autoload_dir).mkdir(parents=True, exist_ok=True)

ftplugin_fp = os.path.join(ftplugin_dir, f'{vim_filetype}.vim')
with open(ftplugin_fp, 'w', encoding='utf-8') as f:
    f.write(self._build_ftplugin_vim(vim_filetype))

docs_fp = os.path.join(autoload_dir, f'{vim_filetype}_docs.vim')
with open(docs_fp, 'w', encoding='utf-8') as f:
    f.write(self._build_docs_autoload_vim(vim_filetype))
```

Mirror the existing verbose-print pattern.

---

## Change 5 — Tests

In `test/test_configgen.py`, add test methods:

### `test_vim_ftplugin_generated`
- File `ftplugin/<ft>.vim` exists.
- Contains the `b:did_<ft>_ftplugin` guard.
- Contains the `bespokeasm_<ft>` augroup with `autocmd! * <buffer>` reset.
- Contains `BufReadPost`, `BufWritePost`, `CursorHold` autocmds.
- Contains `setlocal keywordprg=:call\ <ft>_docs#Show`.
- Contains the global `g:bespokeasm_<ft>_max_scan_lines` default.
- The `s:RefreshLabelsGuarded_<ft>` function is called as both an autocmd target and an inline initial-scan call.

### `test_vim_autoload_docs_generated`
- File `autoload/<ft>_docs.vim` exists.
- Defines `s:docs` as a dict.
- Defines `<ft>_docs#Show` and `<ft>_docs#PopupAtCursor` functions.
- Contains entries for at least one known instruction, one register, and one directive from the test ISA.
- All string values are properly escaped (no unescaped `"` or unescaped trailing `\`).

### `test_vim_syntax_includes_label_usage`
- `LabelUsage` appears in the operand and bracket `contains=` lists in `syntax/<ft>.vim`.
- `hi def link <ft>LabelUsage Identifier` is present.
- An explicit `hi <ft>LabelUsage guifg=...` line is present (from the color generator).
- The static syntax file does **not** emit a `syn match <ft>LabelUsage` (that's the ftplugin's job).

### Update `_assert_vim_contextual_syntax`
- Add a check that `LabelUsage` is in the operand_contains list of the InstrLine region.

---

## Change 6 — Documentation Update

Append a note to `docs/vim-syntax-improvement-plan.md` indicating that semantic label-usage highlighting is now covered by `vim-semantic-and-hover-plan.md`, replacing the "out of scope" disclaimer in its Background section.

---

## Edge Cases & Known Limitations (Document in a Generated Comment Header)

The generated `ftplugin/<ft>.vim` should start with a comment block listing:

1. **Cross-file label resolution is not supported.** Labels defined in `#include`'d files are not highlighted as references in the current buffer. To add: extend `s:ScanLabels_<ft>` to follow `#include` directives, but watch for cycles and absolute-vs-relative path resolution. Out of scope for v1.
2. **Buffers larger than `g:bespokeasm_<ft>_max_scan_lines` (default 10000) are not scanned.** Override in `vimrc` if you have larger files.
3. **Operand-label scoping is approximated.** Local labels (`@foo:`) are scoped to their enclosing global label in BespokeASM's actual semantics, but the highlighter treats all `@foo` references as the same. False positives only occur if two different global-label scopes both define `@foo` differently — visually, both will be highlighted; semantically, only the lexically-nearest definition applies.
4. **Hover popups require vim 8.2+ or Neovim.** On older vim, `K` opens a preview window instead.

---

## Summary

| Change | Effect |
|---|---|
| 1 | Static syntax file reserves the `LabelUsage` highlight group and includes it in operand/bracket contains lists |
| 2 | Generated ftplugin scans the buffer for label definitions and dynamically registers `LabelUsage` matches |
| 3 | Generated autoload provides a `K`-bound docs lookup (preview window) and an optional popup variant |
| 4 | Generator writes the two new files alongside `syntax/` and `ftdetect/` |
| 5 | Tests cover all generated outputs |
| 6 | Existing syntax plan updated to cross-reference this one |

After these changes, the vim experience matches VSCode/Sublime for: contextual operand highlighting, semantic label-reference recognition, and on-demand hover documentation. The remaining gap is interactive features that require a language server (go-to-definition, find-all-references, rename) — out of scope here.
