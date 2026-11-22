# BespokeASM Label Annotations and ISA-Defined Output Formats

Nov 21, 2026 · @Michael Kamprath

## Summary

Add two framework features to BespokeASM: **label annotations** in assembly source, and **output formats defined by the instruction set config file**. An annotation attaches typed, config-validated metadata to a label or constant. An output format turns the compiled bytes plus the annotated symbols into a text file through templates in the config.

The first user is Extended Min (xmin). An xmin script can carry machine code in an `asm` block of Intel HEX records, then `call` it and exchange data through fixed-address variables (`int pa @ 0x0115`). Today the user copies records and addresses by hand, and they go stale whenever the routine moves. With this feature, the Minimal 64x4 config defines an `xmin` annotation and an `xmin` format, and `bespokeasm compile -p -t xmin addw.min64x4` writes a complete `.xmin` file that a script loads with `use`.

Both features follow the pattern flow counters already set: the config enables and describes the feature, source opts in with a `#` directive, and using it against an ISA that doesn't enable it is an error.

## Goals and non-goals

Goals:

- Annotations are a general mechanism. An annotation attaches validated attributes to a label or constant, and other BespokeASM features read them. Listings and output formats are the first consumers, but annotations must not depend on them. A future feature reads the same export model (see "Declaring annotations in the ISA config") and needs no change to annotation parsing or validation.
- The generated editor syntax (VS Code, Sublime Text and Vim, from `configgen/`) highlights `#annotate` as a preprocessor directive. Add `annotate` to `BASE_PREPROCESSOR_DIRECTIVES_SET` in `assembler/keywords.py`, because every ISA has the `listing` namespace. As with the flow-counter directives, the generators also highlight the namespace names and argument keys that the config declares. Like every other directive name, `annotate` then becomes a reserved word in every ISA, so a label or constant named `annotate` is an error. The changelog records this as a behavior change.
- An annotation syntax that attaches named, typed arguments to a label or constant definition.
- Annotation namespaces are declared and validated by the ISA config. A namespace the config doesn't declare is an error, never silently ignored.
- Output formats declared in the ISA config, selected with the existing `-t` option, and listed only for ISAs that declare them. An 8085 config never offers `xmin`.
- Formats are declarative (templates and rules in YAML). A config never ships executable code.
- Annotations emit no bytes and don't change the assembled image.
- Only explicitly annotated symbols are exported. Nothing is inferred from label scope or naming.
- **Stretch goal: polymorphic output formats.** Every format, built-in or config, implements one `OutputFormat` interface: a name, documentation, requirements (such as word size) and a render step. There are two implementations. A Python format is a class, as the printers are now. A defined format is a template plus sections, loaded from a definition file (YAML or JSON) in the schema of this spec. Built-in formats can be either kind; config formats are always defined formats. One registry holds both kinds, and `-t`, `PrettyPrinterFactory` and the docs generator use only the interface. So `listing` can stay Python while `hex` or `symbols` ship as definitions.

Non-goals:

- Annotations on instructions, directives or arbitrary lines. Labels and constants only for now.
- Knowledge of a target's memory map in the framework's generators. The config declares the memory zones, and range checking stays with them.
- Multi-target output. One compilation targets exactly one ISA config.
- Python plugins for formats.

## Annotation syntax

An annotation is a `#annotate` directive line that applies to the next label or constant definition, like a Python decorator:

```
#annotate xmin kind=addr name=AddW
add_w:
    ...
    RTS

#annotate xmin kind=var type=int
pa: .2byte 0

#annotate listing heading="Parameter block"
#annotate xmin kind=var type=char count=16
buf: .zero 16

#annotate xmin kind=var type=int array     ; count from the data: int primes[4]
primes: .2byte 2, 3, 5, 7

#annotate xmin kind=var type=str           ; a .cstr without its terminator: char banner[5]
banner: .cstr "Hello"

#annotate xmin kind=const type=int
LIMIT = 100
```

Grammar:

```
annotation = "#annotate" namespace { argument } [ comment ]
argument   = key "=" value | key            (* a bare key is boolean true *)
value      = symbol-word | numeric-literal | quoted-string
```

Rules:

1. The annotation binds to the next line that defines a label (`name:`) or a constant (`name = expr`, `name EQU expr`). It must be on the line directly before the definition. Only further `#annotate` lines, for other namespaces, may sit between them. A blank line, a comment line or any other line in between is an error.
2. Several annotations may stack on one symbol, one per namespace. A second annotation in the same namespace on the same symbol is an error.
3. `numeric-literal` accepts every numeric syntax the assembler accepts (`0x`, `$`, `b`, and so on). Values are literals, not expressions. The one exception is an argument that the config declares as type symbol: its value is the name of one label or constant, and the framework resolves it after assembly.
4. `#annotate` emits no bytes and occupies no address, like the other `#` directives. It obeys conditional compilation (`#if`/`#ifdef`) like any other line.
5. Annotations in `#include`d files work the same way. An annotation at the end of a file with no following definition is an error.

The framework also validates each annotation against the symbol it annotates. The ISA config defines these constraints (`data_size` and `value_range`, below). A violation is a compile error, not a warning. Example: `#annotate xmin kind=var type=int` on `x: .byte 0` fails, because `int` needs 2 words and `x` owns 1.

Sizes are counted in **words**, the ISA's addressable unit (`general.word_size`). On an ISA with 8-bit words, such as the Minimal 64x4, a word is a byte.

What a label's data must be depends on its annotation, so `data_size` checks the label's **data run**. The data run is the data directives (`.byte`, `.2byte`, `.4byte`, `.8byte`, `.zero`, `.fill`, `.cstr` and the like) that start on the label's line or the line after it and continue without a break. Blank and comment lines do not end the run. Any other line ends it: another label, an instruction, or a directive that is not data.

- The run's total size must equal the size the annotation declares. For `type=int`, `.2byte 0` passes, and so do two `.byte` values. `.8byte 0` fails, and so does `.2byte 0` followed directly by `.byte 0`.
- If something that is not data follows the label (another label, an instruction, `.org`), the run is empty and the check fails, because what follows the label is not an int.
- When the `infer_times` argument is true (`array` in the example), the data sets the count: the run's size divided by the size the other arguments select (one element). The run must hold at least one element and a whole number of them, and the count argument may not also be given. The count is then recorded with the annotation's arguments, so formats and `-t symbols` read it like a given count. Example: `#annotate xmin kind=var type=char array` on `greeting: .cstr "hello"` exports `char greeting[6]`, since the run is 6 words including the terminator. `type=int array` on `.byte 1, 2, 3` fails, because 3 words is not a whole number of 2-word ints.
- When `terminated_when` holds (`type=str` in the example), the data also sets the count, but its last element must be a terminator: every word of it equals the ISA's `.cstr` terminator (`general.cstr_terminator`, default 0). The count leaves the terminator out, and there must be at least one element before it. This suits a target whose strings carry a length instead of a terminator. xmin strings are counted (`char msg = "Hello"` has 5 elements), so `#annotate xmin kind=var type=str` on `greeting: .cstr "hello"` exports `char greeting[5]`, while `type=char array` would export `char greeting[6]` with the terminator as a sixth element. A binding without a size (`char greeting @ ...`) would not work, because xmin gives it one element. The terminator is checked after bytecode generation, when the words exist.
- An annotation with no `data_size` constraint for its arguments, such as `kind=addr`, puts no requirement on what follows the label. Such an annotation exports the label as a symbol: only its address matters. The label can sit on code, on data of any size, or directly above another label.

A constant owns no memory, so `data_size` does not apply to it. Instead, `value_range` checks the constant's resolved value against the range that its arguments select. The config states each range, so it can match the target language: xmin's int and long are signed, and its char constants are 0 to 255. Example: `#annotate xmin kind=const type=char` on `LIMIT = 1000` fails, because `char` allows 0 to 255.

The label line itself is unchanged. An inline form such as `pa [xmin int]: .2byte 0` was rejected: it would change the label pattern and clash with ISAs that use brackets in operands.

## Declaring annotations in the ISA config

A new top-level `annotations` section declares each namespace and its arguments. The framework validates every `#annotate` line against it while parsing. Only the framework's own namespace (`listing`, see below) exists without a declaration.

```yaml
annotations:
  xmin:
    documentation:
      description: Export a symbol to the xmin source file format.
    applies_to: [label, constant]
    scopes: [global]              # .local and _file symbols may not carry it
    arguments:
      kind:
        type: enum
        values: [addr, var, const]
        required: true
      type:
        type: enum
        values: [char, int, long, str]
        required_when: { kind: [var, const] }
      count:
        type: integer
        min: 1
        allowed_when: { kind: [var], type: [char, int, long] }
      array:                      # count comes from the data
        type: boolean
        allowed_when: { kind: [var], type: [char, int, long] }
      name:
        type: string
        pattern: '^[A-Za-z][A-Za-z0-9]{0,12}$'
    data_size:                    # constraint: size of the label's data run, in words
      when: { kind: [var] }
      words: { type: { char: 1, int: 2, long: 4, str: 1 }, times: count, infer_times: array }
      terminated_when: { type: [str] }   # a str's data ends with a terminator that count leaves out
    value_range:                   # constraint: range the constant's value must lie in
      when: { kind: [const] }
      range: { type: { char: [0, 255], int: [-32768, 32767], long: [-2147483648, 2147483647], str: null } }
```

Schema:

| Key | Meaning |
| --- | --- |
| `applies_to` | `label`, `constant`, or both |
| `scopes` | symbol scopes allowed: `global`, `file`, `local` (default: all). The scope comes from the name's prefix (`.` local, `_` file, otherwise global); being defined inside a named scope (`#create-scope`) does not change it |
| `arguments.<key>.type` | `enum`, `integer`, `string`, `boolean` or `symbol`. A symbol value names a label or constant, and the export model carries its resolved value: an address for a label, the value for a constant |
| `values`, `min`, `max`, `pattern` | constraints for that type |
| `required`, `required_when`, `allowed_when` | presence rules; `_when` keys test other enum arguments |
| `default` | value used when the argument is absent |
| `data_size` | constraint: the exact word count of the label's data run, from argument values (`words`). A mismatch is a compile error. In `words`, `times` names an integer argument that multiplies the selected size, and `infer_times` names a boolean argument that, when true, sets the `times` argument from the data instead. `terminated_when` is a condition on enum arguments; when it holds, the data sets `times` and must end with a terminator element that `times` leaves out (see below). |
| table entries | `words` and `range` select their value by one enum argument and list every value of it. A `null` entry means that value is not allowed where the rule applies: `str: null` in `value_range` makes `kind=const type=str` an error. |
| `value_range` | constraint: the inclusive range a constant's value must lie in, from argument values. A value outside it is a compile error. |

The framework records the result on the symbol: namespace, validated arguments with defaults applied, the symbol's value (address or constant), its scope, and for labels the size (in words) and the words of its data run. Formats read this export model; they never re-parse source.

A config that uses `annotations` or `output_formats` sets `general.min_version` to the first BespokeASM release that supports them.

## Config-defined output formats

A new top-level `output_formats` section declares pretty-print formats. Each one becomes a valid `-t` value for that config only. `-t xmin` against a config without it fails with "this instruction set does not define output format 'xmin'". A config format may not reuse a built-in name (`intel_hex`, `hex`, `listing`, `symbols`). Built-in names match `-t` without regard to case, as they do today; config format names must match exactly.

A format is selected only when `-p` is given. Like every pretty-print format, its text goes to stdout unless `--pretty-print-output` names a file.

Every format has the same shape: a `template` and named `sections`. The template is the text of the file. It holds file-level fields and one `{<section>}` placeholder for each section. Each section names one framework `generator` and sets that generator's options. All examples in this spec use this one shape.

```yaml
output_formats:
  xmin:
    documentation:
      description: Extended Min source file with an asm block and exported symbols.
    requires_word_size: 8
    template: |
      # {source_file}: generated by BespokeASM {bespokeasm_version} ({isa_name} {isa_version})
      asm
      {code}

      {symbols}
    sections:
      code:
        generator: intel_hex
      symbols:
        generator: exports
        annotation: xmin
        order: address              # or: source
        unique: name                # two exports with one name is an error
        name_pattern: '^[A-Za-z][A-Za-z0-9]{0,12}$'   # checked on every export name, from the name argument or the symbol
        reserved_names: [and, append, asm, break, call, char, def, elif, else, empty, if, int, key, len, long, not, or, output, pop, print, return, serial, sizeof, use, while, xor]
        value_map: { type: { str: char } }   # xmin writes a string as a char array
        lines_key: kind             # annotation argument that selects the line template
        lines:
          addr:  "int {name} := 0x{address:04x}"
          var:   "{type} {name}{?[{count}]} @ 0x{address:04x}"   # [count] only when count is present
          const: "{type} {name} := {value}"
```

Fields are fixed names with Python format specs, not expressions:

- Template: `source_file`, `isa_name`, `isa_version`, `bespokeasm_version`, and the section names. A section name may not be the same as a field name, and a section field takes no format spec. A section's text never starts or ends with a blank line; the template decides the spacing around it. A section the template never uses is a config warning.
- `exports` items: `name` (the `name` argument, else the symbol), `symbol`, `address` (labels only), `value` (constants only), `size` (in words; empty for a label with no data run, such as `kind=addr` on code), `words` (the words of a label's data run, in hex, in memory order, separated by spaces), and every annotation argument. A `symbol`-typed argument's field is its resolved value, an argument named in the section's `value_map` is its mapped text, and a count that the data set (`infer_times`, `terminated_when`) reads like a given one. An annotation argument may not have the name of one of these fields, except `name`; using such an annotation in `exports` is a config error.
- `byte_lines` items: `label` (a label at that address, else empty), `address`, `byte`, `source` (the instruction text, on its first byte only) and `comment` (the same).
- `rows` items: `byte`, and `address` in `org_line`.

`value_map` rewrites enum argument values in the section's output, as `{argument: {value: text}}`; `lines_key` still selects the line by the source value. An unknown field is a config error at load time, and so is a format spec that cannot apply to the field's type, such as `04x` on `name`. An empty field prints as nothing, and its format spec is not applied. In `exports`, `lines_key` names the enum argument whose value selects a `lines` template, and every value of that enum needs a template. With order: address, labels come first in address order, and constants follow in the order they are defined. With order: source, every export is in the order it is defined. The default is source.

Optional parts. In any line template, `{?...}` is an optional group. The generator writes the group only when every field inside it has a value; otherwise it writes nothing for the whole group. Example: `{name}{?[{count}]}` gives `buf[16]` when `count` is 16 and `pa` when there is no `count`. Groups do not nest, and an unmatched `{?` is a config error. Literal braces are written `{{` and `}}`, as in Python.

Generators:

| Generator | Output | Options |
| --- | --- | --- |
| `intel_hex` | Intel HEX records with the EOF record, as `-t intel_hex` | none |
| `hex` | text hex dump, as `-t hex` | none |
| `byte_list` | comma-separated `0x..` bytes, for formats that embed a blob | none |
| `listing` | the same text as `-t listing`, with `listing` annotations applied | none |
| `rows` | rows of bytes, with an address line at each `.org` | `bytes_per_row`, `row_prefix`, `byte`, `org_line` |
| `byte_lines` | a table with one line per assembled byte | `columns`, `separator` |
| `exports` | one line per symbol that carries the annotation | `annotation`, `order`, `unique`, `reserved_names`, `name_pattern`, `value_map`, then either `lines_key` + `lines`, or `columns` + `separator` |

Tables. `byte_lines`, and `exports` with `columns`, use one column model. `columns` is a list in output order. Each entry names a `field`, and it can set `header` (default empty), `format` (a Python format spec, for example `03o` for octal), `align` (`left` or `right`, default `left`) and `min_width` (default 0). In `exports`, a column can instead choose its field per row, the table counterpart of `lines_key`: `by` names an enum argument, and `cases` maps its values to `{field, format}`. A row whose value has no case gets an empty cell. The lookup uses the source value, before `value_map`. `xmin_listing` uses this to show a `var`'s address under `address` and an `addr` export's address under `value`, as the xmin lines do. The generator writes a header row from the headers, unless all headers are empty, and then one row per item. A header is aligned like its column's values. `exports` takes either `lines_key` and `lines` or `columns`, never both, and `separator` only with `columns`. A column entry takes only `field`, `by`, `cases`, `header`, `format`, `align` and `min_width`; any other key is a config error. A column has either `field` or `by` with `cases`, not both. A `by` column sets `format` in each case instead of on the column, and a case takes only `field` and `format`. Export names are checked (`name_pattern`, `reserved_names`, `unique`) the same way in both modes.

Column widths adjust to the content, as in the built-in `-t listing`. The generator formats every value first. Each column is then as wide as the largest of its `min_width`, its header, and its widest value. Columns are joined with `separator` (default two spaces). The last column gets no padding, and the generator removes trailing spaces from each line, but not the rest of a separator: with `separator: " | "`, a row whose last cell is empty ends in `|`.

Responsibilities:

| Part | Owned by |
| --- | --- |
| `#annotate` parsing, binding, argument validation, the export model | framework |
| Template rendering, body generators, `-t` registration and errors | framework |
| `listing` annotation namespace | framework |
| Which annotation namespaces exist and their arguments | ISA config |
| Format templates, export line templates, reserved names, identifier rules | ISA config |

## Multiple formats and shared definitions

A config can declare any number of formats, and each one is a separate `-t` value. Definitions that several formats need go in a top-level `output_format_shared` section, in named sets. A format names a set with `shared`, and it can add or override items for itself. Memory zones and constants declared this way exist only when a format that uses them is selected.

```yaml
output_format_shared:
  xmin:                             # a named set; a config can have several
    requires_word_size: 8
    predefined:                     # memory_zones and constants only; nothing that emits bytes
      memory_zones:
        - name: XMIN_USER_CODE
          start: 0x0100
          end: 0x0FFF
        - name: XMIN_USER_CODE_HI
          start: 0xED80
          end: 0xEFFF
      constants:
        - name: XMIN_DEBUG
          value: 0
    sections:
      symbols:
        generator: exports
        annotation: xmin
        unique: name
        reserved_names: [and, append, asm, ...]   # as in the section above
        value_map: { type: { str: char } }        # in the set, so xmin_listing shows char too

output_formats:
  xmin:
    shared: xmin
    template: |
      ...                           # as in the section above
    sections:
      code:
        generator: intel_hex
      symbols:
        order: address
        lines_key: kind
        lines:
          ...                       # as in the section above
  xmin_listing:
    shared: xmin
    documentation:
      description: Listing of the xmin build, with the exported symbols and their values.
    predefined:
      constants:
        - name: XMIN_DEBUG          # overrides the shared value for this format only
          value: 1
    template: |
      {code}

      Exported to xmin:
      {symbols}
    sections:
      code:
        generator: listing
      symbols:
        order: source
        columns:
          - { field: name, header: name }
          - { field: kind, header: kind }
          - { field: type, header: type }
          - header: address         # a var is bound to an address
            by: kind
            cases: { var: { field: address, format: "#06x" } }
          - { field: size, header: size }
          - header: value           # addr and const export a value
            by: kind
            cases:
              addr: { field: address, format: "#06x" }
              const: { field: value }
```

Rules:

1. A format is its shared set with the format's own keys applied over it. `predefined` merges by item name: the same name replaces the shared item, and a new name adds an item. `sections` merges by section name, and then by option key.
2. A set can hold any format key except `template`, `documentation` and `shared`. A format without `shared` stands alone. A `shared` value that names no set is a config error. A set that no format names is a config warning. A section of the set that a format's template does not use is not part of that format: it is not checked and gets no warning there. An error in a merged value names the key where it was written, in the set or in the format.
3. When a format is selected, the framework adds its merged zones and constants before it parses source. They then act the same as top-level predefined ones.
4. When no format that declares or shares a name is selected, a reference to that name is an error that names the formats: `unknown memory zone "XMIN_USER_CODE"; it is defined only by output formats 'xmin', 'xmin_listing' (compile with -p and -t naming one of them)`. With one format, the note ends `(compile with -p -t xmin)`. A constant gives the same note after `unknown label "XMIN_DEBUG"; it is a constant defined only by ...`. Source may define a label of the same name when no such format is selected; when one is, the name is defined twice, as with any predefined name.
5. A shared or format-level name may not reuse a top-level predefined name (a memory zone, or a constant or data label), nor name the `GLOBAL` zone, nor appear twice in one list. Each is a config error.
6. One compilation writes one format. To get the `.xmin` file and the listing, compile twice. If the two formats override a constant differently and the source tests it, the two compiles can produce different bytes. The framework does not check this; keeping them the same is the programmer's job.
7. Config formats add to the built-in formats; they do not replace them. A config that declares formats can still use every built-in format (intel\_hex, hex, listing, symbols). But a built-in format does not select a format's shared set, so source that uses XMIN\_USER\_CODE fails with -t listing. Use -t xmin\_listing for that source. The same is true of a compile with no -p, and of -p with no -t, because the default format is listing.
8. In the worked example below, `XMIN_USER_CODE` comes from the shared set, so the source needs no include file for it.

For the worked example below, `-t xmin_listing` ends with this table, sized by the column rules above:

```
Exported to xmin:
name    kind   type  address  size  value
AddW    addr                        0x0100
pa      var    int   0x0113   2
pb      var    int   0x0115   2
pr      var    int   0x0117   2
MAXARG  const  int                  1000
```

## Worked example: the Minimal 64x4 `xmin` format

The `slu4-minimal-64x4` and `slu4-minimal-64x4-redux` configs each carry the `xmin` annotation and format from the two sections above. Source `addw.min64x4`:

```
.memzone XMIN_USER_CODE
.org 0 "XMIN_USER_CODE"

#annotate xmin kind=addr name=AddW
add_w:
    LDB pa+0 ADB pb+0 STB pr+0
    LDB pa+1 ACB pb+1 STB pr+1
    RTS

#annotate xmin kind=var type=int
pa: .2byte 0
#annotate xmin kind=var type=int
pb: .2byte 0
#annotate xmin kind=var type=int
pr: .2byte 0

#annotate xmin kind=const type=int
MAXARG = 1000
```

`bespokeasm compile -c slu4-minimal-64x4.yaml -n -p -t xmin --pretty-print-output addw.xmin addw.min64x4` writes (records abbreviated):

```
# addw.min64x4: generated by BespokeASM <version> (slu4-min64x4-asm <version>)
asm
:10010000...
:09011000...
:00000001FF

int AddW := 0x0100
int pa @ 0x0113
int pb @ 0x0115
int pr @ 0x0117
int MAXARG := 1000
```

The script uses it like this:

```
use "addw"
pa = 1234
pb = 99
call AddW
print(pr)
```

Notes:

- `name=AddW` keeps the assembly label `add_w`, which isn't a legal xmin identifier, without renaming it silently. kind=addr exports only the address as an int constant, so the script can call AddW or bind a variable to it with @ AddW.
- `pa`, `pb` and `pr` are assembled as `.2byte 0`, so the `asm` block zero-fills the parameter block. `data_size` checks that each is 2 words (2 bytes on this 8-bit machine).
- A Redux build compiles Redux source (no `ACB` there) against the Redux config and produces that machine's file. The format knows nothing about which machine it is on beyond `isa_name` in the header.

## Second example: moving `minhex` into the Minimal CPU config

Today `minhex` is a built-in printer (`pretty_printer/minhex.py`) and a fixed `-t` choice in `cli.py`, so every ISA offers it. Only `slu4-minimal-cpu` uses it, and it errors at run time on ISAs whose word size is not 8. The move makes it a config format of `slu4-minimal-cpu.yaml` only.

What the printer does now: it writes rows of up to 16 bytes, each row starts with `:`, and each byte is two lowercase hex digits followed by a space. At each `.org` it ends the current row and writes the new address on its own line, `address_size / 4` hex digits wide. Muted lines are skipped.

The other generators cannot produce this, so the framework needs the `rows` generator:

```yaml
output_formats:
  minhex:
    documentation:
      description: Minimal CPU hex dump, for pasting into the Minimal CPU terminal.
    requires_word_size: 8
    template: "{code}\n"            # the printer ended its last row with a newline too
    sections:
      code:
        generator: rows
        bytes_per_row: 16
        row_prefix: ":"
        byte: "{byte:02x} "          # each byte, with its trailing space
        org_line: "{address:04x}"    # written at each .org; 4 digits for address_size 16
```

Work needed:

1. Framework: the `rows` generator. Its four options are required; a missing one is a config error. `bytes_per_row` is a positive whole number and `row_prefix` a string; `byte` and `org_line` are templates with the fields `byte` and `address`. Like `intel_hex`, it needs 8-bit words. Its text ends without a newline, as every section's does, so the template adds the final one: `"{code}\n"` reproduces the printer's output byte for byte. (A program that emits nothing now gives one empty line instead of nothing.)
2. CLI: build the `-t` choices from the built-in formats plus the config's formats. Remove `minhex` from the built-ins, and delete `MinHexPrettyPrinter` and its branch in `PrettyPrinterFactory`.
3. Config: add the format above to `slu4-minimal-cpu.yaml`, and raise its `general.min_version` and `identifier.version`.
4. Tests: tests may not read `examples/` (see AGENTS.md), so copy the example programs and the Minimal CPU config into a fixture directory under `test/`. Before you delete the old printer, record its output for each copied program as golden files there. Then the new format, added to the copied config as well, must match them byte for byte. Replace `test_pretty_printer_minhex.py` and the `minhex` case in `test_pretty_printer_factory.py` with that golden test. Every minhex row ends with a space, so the golden files (`test/config_files/minhex/*.minhex`) are excluded from pre-commit's trailing-whitespace hook. Running several of the programs in one process exposed a shared default argument that carried included files from one assembly to the next; it is fixed.
5. Docs: the command in `examples/slu4-minimal-cpu/README.md` does not change. The changelog must say that `-t minhex` is gone for every other ISA. The break is intended. minhex was made for one config, and it is the main existing example of why a config-specific format belongs in its config.

## Third example: an octal listing for the KENBAK-1

KENBAK-1 programs are traditionally written in octal. A listing has one byte per row and four columns: label, address, coded data and a description. Addresses and bytes are three octal digits, and an operand byte gets its own row ([kenbak.com, Programming](https://www.kenbak.com/programming)). The built-in `-t listing` and the `listing` generator write hex, so neither can produce this layout.

The framework needs the `byte_lines` generator. It writes a table with one line per assembled byte, with the column model and automatic widths from "Config-defined output formats". Octal comes from the format spec `03o`.

```yaml
output_formats:
  octal_listing:
    documentation:
      description: KENBAK-1 style listing, one byte per row, in octal.
    requires_word_size: 8
    template: |
      # {source_file}: generated by BespokeASM {bespokeasm_version} ({isa_name} {isa_version})

      {code}
    sections:
      code:
        generator: byte_lines
        columns:
          - { field: label, header: label, min_width: 8 }
          - { field: address, header: adr, format: "03o" }
          - { field: byte, header: data, format: "03o" }
          - { field: source, header: description, min_width: 16 }
          - { field: comment }
```

For `examples/kenbak-1/led-chaser.kb1`, `-t octal_listing` would start like this. These bytes match a real compile of the file with `-t listing`. The column widths are only an illustration, because a real build sizes them from the whole file.

```
label        adr  data  description
init         004  023   ld a, 1
             005  001
             006  034   ld [OUTPUT], a     init the screen display
             007  200
.loop        010  367   jm left_loop       call left_loop function
             011  016
```

Work needed:

1. Framework: the `byte_lines` generator. It uses the shared column model.
2. Config: add the format to `kenbak-1-isa.yaml`, and raise `general.min_version` and `identifier.version`.
3. Tests: copy `led-chaser.kb1` and the KENBAK-1 config, with the new format, into a fixture directory under `test/`, and add a golden file from it.

A `radix` option on the built-in listing would also give octal. A config format is better here because it also sets the columns to match the traditional KENBAK-1 layout.

## The built-in `listing` namespace

The framework defines one namespace that every ISA has: `listing`. It shapes `-t listing` output and is ignored by every other format.

| Argument | Effect in the listing |
| --- | --- |
| `heading="..."` | prints a heading line before the symbol |
| `page_break` | starts a new page (form feed) before the symbol |
| `collapse` | shows the first line of the symbol's data and a count of words omitted, for large tables and `.zero` fills |
| `hide` | omits the symbol's lines from the listing, bytes still assembled |

Example:

```
#annotate listing heading="Lookup tables" collapse
sine_table:
    .byte 0x00, 0x03, 0x06, ...
```

collapse acts on the label's data run. hide acts on every line from the label up to the next label of any scope. A config may not declare a namespace named `listing`. Further framework namespaces would follow the same rule.

## Errors and diagnostics

Every problem is an error with the source line, not a warning, unless marked otherwise. Config errors (last row) fail when the config loads, before any source is read.

| Condition | Message (suggested) |
| --- | --- |
| Namespace not declared by the ISA | `this instruction set does not define annotation 'xmin'` |
| Unknown argument, bad value, missing required argument | `annotation 'xmin': argument 'type' must be one of char, int, long, str` |
| Argument not allowed for this combination (`allowed_when`) | `annotation 'xmin': 'count' is only allowed when kind is var and type is one of char, int, long` |
| The data sets the count, and the count is also given | `annotation 'xmin': 'count' cannot be given with 'array', which takes count from the data` |
| Data that cannot set the count: not a whole number of elements, or too little data | `'odd' is annotated as type=int array, which needs a whole number of 2-word elements, but 3 words of data follow it` |
| The next line is not a label, a constant or another #annotate | `#annotate must be directly above a label or constant definition` |
| Symbol kind or scope not allowed (`applies_to`, `scopes`) | `annotation 'xmin' is not allowed on local label '.loop'` |
| Same namespace twice on one symbol | `symbol 'pa' already has an 'xmin' annotation` |
| `data_size` mismatch, or constant outside its value\_range (each names the arguments that chose the size or range) | `'pa' is annotated as type=int, which needs 2 words, but 1 word of data follows it` / `'MAXARG' value 40000 is outside -32768 to 32767, the range of type=int` |
| `terminated_when` data that does not end with the terminator | `'msg' is annotated as type=str, which needs its data to end with a 0 terminator, but it ends with 0x42` |
| A rule's table has a `null` entry for the selected value | `annotation 'xmin': type=str is not allowed when kind is const` |
| Format not defined by the ISA | `this instruction set does not define output format 'xmin'` |
| Export name fails the `name` pattern, or is in `reserved_names` | `export name 'sum_to' is not valid for format 'xmin'` |
| Two exports with one name (`unique: name`) | `export name 'pa' is used by 'pa' and '_pa'` |
| Format used with no matching annotations | **warning**: `format 'xmin': no symbols carry an 'xmin' annotation` |
| `-t` is given but `-p` is absent (any format, built-in or config) | **warning**: `-t xmin has no effect without -p; output format 'xmin' is not selected` |
| Config: unknown template field, missing `lines` entry, namespace named `listing`, format named like a built-in | config error naming the key path |

Errors from the later sections:

| Condition | When | Message (suggested) |
| --- | --- | --- |
| A `symbol` argument names no label or constant | compile | `annotation 'xmin': 'len' names unknown symbol 'buf_len'` |
| Source uses a format-scoped zone or constant, and that format is not selected | compile | `unknown memory zone "XMIN_USER_CODE"; it is defined only by output formats 'xmin', 'xmin_listing' (compile with -p and -t naming one of them)` |
| Export name fails `name_pattern` | compile | `export name 'sum_to' is not valid for format 'xmin'` |
| `shared` names no set in `output_format_shared` | config load | `output_formats.xmin.shared names unknown shared set 'xmn'; shared sets are xmin` |
| A shared set holds `template`, `documentation` or `shared` | config load | config error naming the key path |
| A shared set that no format names | config load | **warning** naming the set |
| A shared or format-level zone or constant reuses a top-level predefined name | config load | `output_formats.xmin.predefined.memory_zones[ZERO_PAGE] cannot be defined: 'ZERO_PAGE' is already a predefined memory zone` |
| Format-scoped `predefined` holds a key other than `memory_zones` or `constants` | config load | config error naming the key path |
| A generator is missing a required option, or has an unknown one | config load | `output format 'minhex', section 'code': generator 'rows' requires 'org_line'` |
| Unknown generator name | config load | `output format 'xmin', section 'code': unknown generator 'intelhex'` |
| A section name equals a template field name, or the template names a section that is not defined | config load | config error naming the key path |
| Unmatched `{?`, or a nested optional group | config load | config error naming the key path and the template |
| A `columns` entry has no `field` (or `by` and `cases`), both, an unknown `field`, `align`, `format` or key, a bad `min_width` or `header`, or a `by` that is not an enum argument or a case for a value it does not have | config load | config error naming the key path, e.g. `output_formats.xmin_listing.sections.symbols.columns[3].align must be left or right, not "center"` |
| `exports` has both `lines` and `columns`, or `separator` without `columns` | config load | config error naming the section |
| `-t` names a format that needs a different word size | compile | `output format 'minhex' requires 8-bit words` |
| A section uses a generator that cannot work with the ISA's word size (`intel_hex`, `hex` and `byte_list` need 8-bit words) | config load | `generator 'intel_hex', which needs 8-bit words; this instruction set has 16-bit words` |

## Documentation generation

Today `bespokeasm docs` writes markdown from the config (`docsgen/`): general information, predefined memory zones, constants and data, operand sets, flow counters, instructions and macros. The same model also gives the hover text for editor extensions (`configgen/hover_docs.py`), and `docsgen/directive_docs.py` holds the hover text for each directive. It does not read `annotations`, `output_format_shared` or `output_formats`, so without changes the new features do not appear in the docs.

Changes:

1. **Annotations section.** For each namespace: its `documentation.description`, `applies_to`, `scopes`, and a table of arguments with type, allowed values or range, required or `_when` rules, and default. The `data_size` and `value_range` constraints are described in prose, for example "`type=int` needs 2 words", "with `array`, the count comes from the data", "`type=str` data ends with the string terminator, which the count leaves out", and "`type=str` is not allowed when kind is const" for a `null` entry.
2. **Output formats section.** For each format: its `-t` name, `documentation.description`, `requires_word_size`, and its shared set. Built-in formats are listed too, so the reader sees every `-t` value that this ISA accepts.
3. **Format-scoped zones and constants.** They appear with the other predefined items, marked with the formats that define them, for example "only with `-t xmin` or `-t xmin_listing`". Their hover text carries the same note. An override shows its value per format.
4. **Directive hover text.** Add a `#annotate` entry to `directive_docs.py`.

The `documentation` keys in the config examples above exist for this purpose. A namespace or format without `documentation.description` still appears, with no description.

## Open questions

1. **Directive name.** Decided: `#annotate`. The shorter `#attr` and `#label` were rejected.
2. **Named-target form.** Should `#annotate pa xmin kind=var type=int` also be allowed, so a header block can annotate symbols defined elsewhere? Decided: no. An annotation is always directly above the definition it applies to.
3. **Config-declared namespaces in listings.** Should a config namespace be able to add listing behavior, or does `listing` stay framework-only? Decided: framework-only.
4. **Generic symbol export.** Decided: add a built-in `-t symbols`. It writes every label and constant as JSON, with its value, scope and annotations, so other tools can use annotations without a config format. It starts as a Python format. If it later ships as a definition, it needs a `symbols_json` generator, because templates do not escape JSON strings.
5. **Template conditionals.** `count_suffix` was a special case. Decided: replaced by general optional groups, `{?...}` (see "Config-defined output formats").
6. **Built-in formats as shipped definitions.** Should `intel_hex`, `hex`, `listing` and `symbols` be format definitions in a file shipped with BespokeASM, in the same schema as config formats? Recommendation: yes, in YAML like the configs. Each one is a template with one section, for example `{code}` with `generator: listing`. Then `PrettyPrinterFactory`, the `-t` choices and the docs use one path for all formats. The generators stay Python. The listing printer, about 300 lines with automatic widths, file headers and flow columns, does not become declarative. Decided: a stretch goal, with Python and defined built-ins side by side (see Goals).

## Suggested implementation order

1. Annotations core: #annotate parsing and binding, the annotations config schema, argument validation, the data\_size and value\_range checks, and the export model. No output yet; covered by parser and validation tests.
2. The built-in -t symbols format, in Python. It is the first reader of the export model.
3. The format engine: the OutputFormat interface and registry, -t choices built from the built-ins plus the config, template rendering with optional groups, and the intel\_hex, hex, byte\_list, listing and exports (lines) generators.
4. xmin: shared sets with format-scoped zones and constants, then the xmin annotation and format in the Minimal 64x4 and Redux configs, with a golden-file test of the worked example. This is the first release that is useful on its own.
5. The column model: exports with columns, and xmin\_listing.
6. The rows generator and the minhex move. This removes a built-in -t value, so it needs its own changelog entry.
7. The byte\_lines generator and the KENBAK-1 octal listing.
8. The listing namespace in the listing printer.
9. Documentation generation, hover text, and the VS Code, Sublime Text and Vim syntax for #annotate.
10. Stretch: built-in formats shipped as definitions.

The worked example's golden test follows the same rule as the minhex and KENBAK-1 tests: copy `addw.min64x4` and the Minimal 64x4 config, with the xmin annotation and format, into a fixture directory under `test/`.

On the xmin side, nothing changes in the interpreter. `tests/asm/asmblock.min64x4` would gain annotations, and its generated `.xmin` would replace the hand-copied records in `tests/asmblock.xmin`.
