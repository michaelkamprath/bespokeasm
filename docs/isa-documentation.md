# Overview
The goal of this feature is to create a standard way of documenting an instruction set architecture in the **BesopokeASM** language configuration file, and then a way to generate a Markdown documentation page from the configuration file.

# Requirements

## Configuration File
All added elements for documentation will be optional. If the user does not provide a value for the documentation field, then the documentation will not be generated for the relevant aspect of the instruction set architecture.

### General Documentation
The general documentastion is mostly implied by the configuration of the `general` section of the instruction set configuration file. However, `general` section can have an optional `documentation` field that can be used for top-level documentation of the instruction set architecture. The `documentation` sections will have the following fields (all optional):

| Option Key | Value Type | Description |
| --- | --- | --- |
| `description` | string | A short description of the instruction set architecture. |
| `details` | string | _Optional_ A detailed description of the instruction set architecture. Markdown text is allowed. |
| `addressing_modes` | dictionary | _Optional_ A dictionary of addressing modes. The keys are the addressing mode names and the values are dictionaries with the following keys:<ul><li>`description` - A short description of the addressing mode.</li><li>`details` - _Optional_ A detailed description of the addressing mode. Markdown text is allowed.</li></ul>The keys in this dictionary are used by the `mode` field in the [Operand Documentation](#operand-documentation) section. Note that while there is corelation between an instruction set's addressing modes and **BespokeASM**'s operand types, an operand type describes how *BespokeASM* will parse the operand value when assembling an instruction, while an addressing mode describes how the operand value is used in the instruction set and ultimately in the hardware the assembled bytecode is executed on and is not a **BespokeASM** concept. |
| `examples` | array | _Optional_ An array of example instructions. Each example is a dictionary with the following keys:<ul><li>`description` - A short description of the example.</li><li>`details` - _Optional_ A detailed description of the example. Markdown text is allowed.</li><li>`code` - The code of the example instruction.</li></ul><p>Examples are used to show how the instruction set can be used in practice. They should be used to demonstrate the use of the instruction set in a way that is easy to understand and use. |

Flag documentation is defined directly in the `general.flags` dictionary rather than inside the `documentation` subsection. Each entry in that dictionary is keyed by the flag symbol and contains the remaining metadata (for example, `description` and optional `details`).


### Instruction Documentation
Each instruction entry in the configuration file (as documented in the [Instruction Set Configuration File](https://github.com/michaelkamprath/bespokeasm/wiki/Instruction-Set-Configuration-File#instructions) wiki page) must be able to describe the instruction in a way that is easy to understand and use. It will do this by adding an optional `documentation` field to the instruction entry. The `documentation` field will be a dictionary with the following keys:

| Option Key | Value Type | Description |
| --- | --- | --- |
| `category` | string | The category of the instruction. This is used to group instructions together in the documentation page.  Categories include things like "Data Movement", "Arithmetic", "Control Flow", "Memory", "I/O", "Bitwise", etc. There is no absolute constraint on the categories, but they should be used to group instructions together in a way that is easy to understand and use, and the catefory titles should be concise and descriptive. |
| `title` | string | A short title or summary of the instruction. |
| `details` | string | _Optional_ A detailed description of the instruction. Markdown text is allowed. |
| `modifies` | array | _Optional_ An array of dictionaries each representing a register or memory location that is modified by the instruction. Each dictionary has the following keys:<ul><li>`register` - The register that is modified. The value of this key is the name of the register.</li><li>`memory` - The memory location that is modified. The value of this key is the name of the memory location.</li><li>`flag` - The flag that is modified. The value of this key is the name of the flag.</li><li>`description` - A short description of the modification.</li><li>`details` - _Optional_ A detailed description of the modification. Markdown text is allowed.</li></ul><p>Each `modifies`dictionary must contain exact one of the keys `register`, `memory`, or `flag`, and the `description` field, and `details` field is optional. |
| `examples` | array | _Optional_ An array of example usages of the instruction. Each example is a dictionary with the following keys:<ul><li>`description` - A short description of the example.</li><li>`details` - _Optional_ A detailed description of the example. Markdown text is allowed.</li><li>`code` - The code of the example instruction.</li></ul><p>Examples are used to show how the instruction can be used in practice. They should be concise and to the point. |

### Macro Documentation
Instruction macros may also include documentation, using the same schema as instructions. When a macro is defined with the dictionary-style configuration (macro name maps to an object), an optional `documentation` field can be provided alongside the `variants` list. The fields are identical to those in [Instruction Documentation](#instruction-documentation):

| Option Key | Value Type | Description |
| --- | --- | --- |
| `category` | string | The category of the macro. Used to group macros together in the documentation page. |
| `title` | string | A short title or summary of the macro. |
| `details` | string | _Optional_ A detailed description of the macro. Markdown text is allowed. |
| `modifies` | array | _Optional_ An array of dictionaries describing registers, memory locations, or flags modified by the macro. Same structure as instructions. |
| `examples` | array | _Optional_ An array of macro usage examples. Same structure as instructions. |

Variant-level documentation is also supported: each entry in the macro `variants` list may include its own `documentation` block with the same keys. Legacy list-style macro configurations remain supported; they simply cannot carry macro-level documentation because the list form has no place for a `documentation` key.

### Operand Documentation
Each operand entry in the configuration file (as documented in the [Instruction Set Configuration File](https://github.com/michaelkamprath/bespokeasm/wiki/Instruction-Set-Configuration-File#operands) wiki page) must be able to describe the operand in a way that is easy to understand and use. It will do this by adding an optional `documentation` field to the operand entry. The `documentation` field will be a dictionary with the following keys:

| Option Key | Value Type | Description |
| --- | --- | --- |
| `title` | string | _Optional_ A friendly display name for the operand. Falls back to the operand key when not provided. |
| `syntax_example` | string | _Optional_ A literal example of how this operand should appear in assembly syntax. When present, this string is used verbatim in calling syntax blocks, `where` tables, and operand set tables instead of any auto-derived placeholder. |
| `mode` | string | A short string representing the aaddressing mode of the operand. For example 'register', 'immediate', 'memory', 'flag', etc. The value of this field is the key in the `addressing_modes` dictionary in the [General Documentation](#general-documentation) section. |
| `description` | string | A short description of the operand. |
| `details` | string | _Optional_ A detailed description of the operand. Markdown text is allowed. When omitted, certain operand types (for example `numeric_enumeration`) will auto-populate the documentation with helpful metadata such as the list of valid enumeration values. |

### Operand Set Documentation
Each operand set entry in the configuration file (see the [Instruction Set Configuration File](https://github.com/michaelkamprath/bespokeasm/wiki/Instruction-Set-Configuration-File#operand-sets) wiki page) may include an optional `documentation` field alongside its `operand_values`. This dictionary describes the operand set as a whole so that generated documentation can introduce the set before listing the individual operands.

| Option Key | Value Type | Description |
| --- | --- | --- |
| `title` | string | _Optional_ A friendly display name for the operand set. Falls back to the operand set key when not provided. |
| `category` | string | _Optional_ A grouping label (for example “Registers”, “Addressing”, “Literals”) used to cluster operand sets within the generated documentation. |
| `description` | string | A short sentence summarizing the operand set’s role. |
| `details` | string | _Optional_ Extended markdown content describing nuances, encoding notes, or architectural constraints for the operand set. Markdown text is allowed. |
| `operand_order` | array[string] | _Optional_ Ordered list of operand keys from `operand_values` that dictates how operands are presented in documentation. Defaults to the configuration order if omitted. |

The individual operands within an operand set continue to use the [Operand Documentation](#operand-documentation) fields (`mode`, `description`, `details`). When both levels are present, the generated documentation will introduce each operand set using the fields above and then tabulate its member operands, leveraging the per-operand metadata to populate the table.

### Predefined Memory Zone Documentation
Each entry in `predefined.memory_zones` (see the [Instruction Set Configuration File](https://github.com/michaelkamprath/bespokeasm/wiki/Instruction-Set-Configuration-File#predefined) wiki page) may include an optional `documentation` field that describes the memory zone in generated ISA docs.

| Option Key | Value Type | Description |
| --- | --- | --- |
| `title` | string | _Optional_ A friendly display name for the memory zone. Falls back to the zone `name` when not provided. |
| `description` | string | A short summary of the memory zone's purpose or usage. |

### Predefined Constant Documentation
Each entry in `predefined.constants` (see the [Instruction Set Configuration File](https://github.com/michaelkamprath/bespokeasm/wiki/Instruction-Set-Configuration-File#predefined) wiki page) may include an optional `documentation` field that describes the constant in generated ISA docs.

| Option Key | Value Type | Description |
| --- | --- | --- |
| `type` | string | The constant type. Allowed values are `subroutine`, `variable`, or `address`. |
| `size` | integer | _Optional_ Size in bytes for `variable` constants. Required when `type` is `variable`. |
| `description` | string | A short summary of the constant's meaning or usage. |

# Generated Documentation

## Markdown Documentation Page

The generated markdown documentation will be structured as follows:

### Overall Document Structure

The markdown documentation page will have the following overall structure:

1. **Document Header** - ISA name (from `general.identifier.name`) and description (from `general.documentation.description` if present)
2. **General Information Section** - Comprehensive information from the entire `general` section including hardware architecture, configuration details, and custom documentation if present
3. **Predefined Memory Zones Section** - Documents the `predefined.memory_zones` entries declared in the configuration file
4. **Predefined Constants Section** - Documents the `predefined.constants` entries declared in the configuration file
5. **Operand Sets Section** - Documents each configured operand set with narrative context and a per-operand table
6. **Instructions Section** - Organized by category with detailed instruction documentation
7. **Macros Section** - Organized by category with detailed macro documentation using the same layout as instructions

### General Information Section

The General Information section will include comprehensive details from the entire `general` section of the configuration file. Each subsection is emitted as a two-column markdown table (`<Attribute> | Value`) with the attribute names bolded. When multiple tables are generated, they are separated by horizontal rules (`---`) to match the curated example layout. Fields that are absent from the configuration are omitted from the tables entirely.

#### ISA Overview
- **ISA Name** - From `general.identifier.name` (if present)
- **Version** - From `general.identifier.version` (if present)
- **File Extension** - From `general.identifier.extension` (if present). Values are rendered using the `*.ext` convention (e.g., `*.sap1`).
- **Description** - From `general.documentation.description` (if present)
- **Details** - From `general.documentation.details` (if present, rendered as markdown immediately after the table)

#### Hardware Architecture Details
- **Address Size** - From `general.address_size` (required field)
- **Word Size** - From `general.word_size`
- **Word Segment Size** - From `general.word_segment_size` (only shown when different from `general.word_size`)
- **Page Size** - From `general.page_size` (only shown when the value is greater than 1, rendered as `<value> addresses`)
- **Origin Address** - From `general.origin` (shown as **Default Origin Address** when the value is `0`)

#### Endianness Configuration
- **Multi-Word Endianness** - From `general.multi_word_endianness` (defaults to "big" if not specified)
- **Intra-Word Endianness** - From `general.intra_word_endianness` (defaults to "big" if not specified)
- Note: If the deprecated `general.endian` field is present, it should be reported with a deprecation warning

#### String and Data Handling
- **C-String Terminator** - From `general.cstr_terminator` (defaults to 0 if not specified)
- **Embedded Strings Allowed** - From `general.allow_embedded_strings` (defaults to false if not specified)
- **String Byte Packing** - From `general.string_byte_packing` (defaults to false if not specified)
- **String Byte Packing Fill** - From `general.string_byte_packing_fill` (only shown when string byte packing is enabled)

#### Register Set
**Registers** - If the `registers` section of the `general` configuration is present, then the set of registers is documented in a table that always includes a `Symbol` column and conditionally includes the following columns when data is available for at least one register:
* `Title` — Populated from the register's `title` attribute.
* `Description` — Populated from the register's `description` attribute (with the optional `details` value appended).
* `Bit Size` — Populated from the register's configured `size`.

#### Addressing Modes
- **Addressing Modes** - Table of addressing modes from `general.documentation.addressing_modes` (if present)

#### Flags
- **Flags** - Table of flags from `general.flags` (if present). Each flag entry is keyed by its symbol, and the symbol is rendered as inline code in the table.

#### Examples
- **Examples** - Code examples from `general.documentation.examples` (if present)

#### Compatibility
- **Minimum BespokeASM Version** - From `general.min_version` (required field)

### Predefined Memory Zones Section
The predefined memory zones section is emitted immediately after the General Information section and before the `# Operand Sets` section. It begins with the markdown header `## Predefined Memory Zones`. This section is generated only when `predefined.memory_zones` is present and contains at least one entry (documentation fields remain optional).

Each memory zone is rendered as a table row with the following default columns:
- `Name` - The memory zone `name`, rendered as inline code.
- `Start` - The `start` value rendered as hexadecimal.
- `End` - The `end` value rendered as hexadecimal.
- `Title` - Populated from `documentation.title` when present (falls back to the zone name when absent).
- `Description` - Populated from `documentation.description` when present.

Hexadecimal values should be zero-padded to match the ISA address size when `general.address_size` is available (for example, 16-bit address space renders `0x0000`). When the address size is missing or not divisible by 4, render the shortest hexadecimal representation.

Column inclusion follows the [Table Column Optimization](#table-column-optimization) guidance. When no zone supplies a `documentation` field, the `Title` and `Description` columns are omitted and only `Name`, `Start`, and `End` are shown.

### Predefined Constants Section
The predefined constants section is emitted immediately after the Predefined Memory Zones section and before the `# Operand Sets` section. It begins with the markdown header `## Predefined Constants`. This section is generated only when `predefined.constants` is present and contains at least one entry (documentation fields remain optional).

Each constant is rendered as a table row with the following default columns:
- `Name` - The constant `name`, rendered as inline code.
- `Value` - The constant `value` rendered as hexadecimal. Hex values should be zero-padded to match the ISA address size when `general.address_size` is available (for example, 16-bit address space renders `0x0000`). When the address size is missing or not divisible by 4, render the shortest hexadecimal representation.
- `Type` - Populated from `documentation.type`.
- `Size (Words)` - Populated from `documentation.size` when the type is `variable`.
- `Description` - Populated from `documentation.description` when present.

Column inclusion follows the [Table Column Optimization](#table-column-optimization) guidance. When no constant supplies a `documentation` field, the `Type`, `Size`, and `Description` columns are omitted and only `Name` and `Value` are shown.

### Operand Sets Section
The operand sets section is emitted immediately after the Predefined Constants section and before the `# Instructions` section. It begins with the markdown header `## Operand Sets`. Each operand set documented in the ISA configuration is rendered as a separate `### `<operand set key>` - <operand set title>` subsection (if `documentation.title` is provided). If no title is provided, the header is simply `### `<operand set key>`` with the key rendered as inline code. Operand sets are ordered first by `documentation.category` (alphabetical, with uncategorized sets listed last) and then by display name.

For each operand set subsection:
1. **Category Label** — When `documentation.category` is present, emit an italicized line `*Category: <category>*` directly beneath the heading.
2. **Summary** — Render `documentation.description` as a short lead-in paragraph, followed by `documentation.details` as multi-line markdown when available.
3. **Operand Table** — Emit a table where each row represents an operand from the operand set. Rows are ordered by `documentation.operand_order` when provided; otherwise the operands preserve the configuration file order. The default table columns are:
   - `Operand` — The operand key from `operand_values`, rendered as inline code.
   - `Syntax` — Shows how the operand would be written in source code. Prefer `operand_values.<operand>.documentation.syntax_example` when provided; otherwise derive the syntax from the operand’s configuration using the rules in [Operand Syntax Resolution](#operand-syntax-resolution). Syntax is reused in calling syntax placeholders when present so bracketed/decorated forms surface there.
   - `Value` — Summarizes the underlying target or constraint (register name, numeric range, enumeration tokens). Decorators stay in `Syntax`; `Value` shows the plain register name for register-backed operands and the allowed range for numeric bytecode, etc.
   - `Mode` — Populated from the operand’s `documentation.mode`. The column header links to the Addressing Modes section only when `general.documentation.addressing_modes` is present; otherwise the header is plain text.
   - `Description` — Populated from the operand’s `documentation.description`.
   - `Details` — Populated from the operand’s `documentation.details`, allowing inline markdown.

   Column inclusion follows the [Table Column Optimization](#table-column-optimization) guidance. If every operand lacks a value for a column, that column is omitted entirely.

Operand sets that lack a `documentation` block are still rendered to keep coverage complete. In this case, the subsection heading is derived from the operand set key, and the operand table is generated using the available per-operand documentation (fields are left blank when absent).

### Operand Syntax Resolution

When a literal example is not supplied via `documentation.syntax_example`, derive operand syntax using these rules so that both operand tables and calling syntax blocks show the notation writers actually type:
- **Register-backed operands** (`register`, `indexed_register`, `indirect_register`, `indirect_indexed_register`): render the configured `register` value (not the operand key) and apply any decorator inline (`+a`, `a++`, `+[sp]`, etc.). For indirect forms, wrap the decorated register in brackets; include offsets/index operands only when they are supported by configuration. Examples: `[ix]` when no offset is enabled, `[ix+offset]` when an offset is supported, `r + <index operand syntax>` for indexed registers, and `[r + <index operand syntax>]` for indirect indexed registers (nested brackets are preserved if an index operand is itself indirect).
- **Numeric expressions** (`numeric`, `indirect_numeric`, `deferred_numeric`, `address`, `relative_address`, `numeric_enumeration`, `numeric_bytecode`): use the operand key as the placeholder inside the addressing-mode wrapper that matches the operand type (e.g., ``addr`` → `[addr]`, ``target`` → `{target}` when curly braces are enabled). This operand-key-based syntax is what appears in calling syntax when no `syntax_example` is provided.
- **Enumeration literals**: when an operand value maps to a specific token via `value_dict`, use that literal token inline (for example ``ADD``). If multiple tokens exist and no `syntax_example` is provided, default to the operand key.
- **Empty operands**: emit a blank syntax string to indicate the operand is implicit.

Decorator placement always follows the notation defined in the [Addressing Modes](https://github.com/michaelkamprath/bespokeasm/wiki/Assembly-Language-Syntax#addressing-modes) guide and the operand’s `decorator` configuration (prefix vs. postfix). Decorators stay in the syntax column; the `Value` column for register-backed operands always lists the plain register name (`register \`is\``), regardless of decorators.

The same resolution drives the `Value` column in `where` tables: registers resolve to the concrete register name, enumerations list the literal token(s) permitted, and numeric-style operands summarize the allowed range or bit width when `min`/`max` or `size` constraints are present (for example, “numeric expression valued between 0 and 0xB” for a constrained `numeric_bytecode`, or “numeric expression expressed as 8-bit value” when only a bit size is provided). Numeric immediates (`numeric`) and addresses (`address`) always show “numeric expression” and append constraints when present. When a range includes negative bounds, decimal formatting is used for all bounds; otherwise, non-negative values ≥10 may use hex for readability.

When an instruction signature references an operand set, its `where` table row keeps `Type` as `operand_set` and does not inline set members—except when the operand set has exactly one operand value. In that single-member case, the instruction row will also show that member’s `Syntax` and `Value` to give readers the precise usage without leaving the instruction section.

When an operand set has exactly one operand value, instruction documentation inherits that member’s identity: the calling syntax uses the member name and syntax, and the `Type` column reflects the member’s operand type (not `operand_set`) while the `Value` column reflects the member’s constraints.

### Formatting Guidelines

The following formatting guidelines apply to all sections of the generated documentation:

- Tables are used whenever possible for attribute/value pairs to improve scanability.
- Boolean fields are rendered as "Enabled" or "Disabled".
- Optional fields that are not present are omitted from the documentation.
- Required fields should always be displayed when data exists.
- Deprecated fields should be marked with a deprecation notice.

#### Table Column Optimization

For all tables throughout the generated markdown documentation, if a column is empty for all rows in a table (i.e., all entries for that column are null, empty strings, or otherwise contain no meaningful content), the entire column should be omitted from the table. When columns are omitted, the remaining columns should maintain their logical order and proper markdown table formatting

This optimization ensures that generated tables are clean, concise, and only display columns that contain useful information for the user.

### Instruction Set Documentation

The instructions sections of the documentation page will be prefaced with a markdown section header `# Instructions` and then the instructions will be organized by category.

The distinct set of `category` values will be used as level 2 sections in the documentation page with the format of `## <category>`. The category names will be capitalized using title case (e.g., "data movement" becomes "Data Movement"). Each instruction with that category will be documented in its category section as described below.

Instructions within each category will be listed in alphabetical order.

Each instruction's documentation will be prefaced with a markdown section header ``### `<instruction mnemonic>` : <instruction title>`` where `<instruction mnemonic>` is the instruction mnemonic capitalized and rendered as inline code. The ` : <instruction title>` suffix comes from the [Instruction Documentation](#instruction-documentation) section and is only present if the `title` field is provided.

Immediately after the instruction heading, render the shared narrative elements that apply to all operand signatures:
- Emit `documentation.description` as a short lead-in paragraph.
- Follow with `documentation.details`, when provided, as multiline markdown.

Once the shared description is in place, evaluate the operand signatures defined for the instruction. Signatures can come from the top-level `operands` configuration, from entries in the `variants` list, or both. The generator treats these configurations as an ordered list of versions:

1. If the top-level instruction configuration includes an `operands` block, it becomes Version&nbsp;1.
2. Each item in the `variants` list is considered in file order and assigned the next version number (Version&nbsp;2, Version&nbsp;3, …).
3. If the instruction omits a top-level `operands` block and only declares variants, numbering still starts at Version&nbsp;1 using the first variant.

When more than one signature exists, insert a subheading `#### Version <N>` for each version. If the variant provides a `documentation.title`, append it after the version number with a colon separator (for example, `#### Version 2 : LOAD REGISTER A, KL`). These subheadings appear immediately after the shared description (and before any `Modifies` or `Examples` subsections). For instructions with only one signature, omit the subheading and apply the Version&nbsp;1 layout directly under the shared description.

Variant-level documentation is fully supported. Any `documentation` fields present on a variant (e.g., `documentation.title`, `documentation.description`, `documentation.details`, `documentation.modifies`, `documentation.examples`) are rendered within that version’s section in the same format used for instruction-level documentation. This allows each operand signature to carry its own narrative, modifiers, and examples without affecting the shared instruction description.

Inside each version section, emit a syntax summary that makes the callable form of that signature explicit. The syntax block follows this structure:

1. Render an italicized lead-in line `*Calling syntax:*`.
2. Emit an `````asm```` code block that shows the mnemonic followed by its operands in source order, separated by `, ` to match the [assembly language syntax](https://github.com/michaelkamprath/bespokeasm/wiki/Assembly-Language-Syntax#general-assembler-syntax). Each operand string is resolved using [Operand Syntax Resolution](#operand-syntax-resolution), favoring any `documentation.syntax_example` that has been provided.
3. When at least one operand placeholder is present, add a `where` paragraph followed by a markdown table describing each operand. The default columns are `Operand`, `Type`, `Value`, and `Description`, with an optional `Details` column included only when any operand surfaces `documentation.details` or auto-generated notes. The `Operand` column echoes the syntax string used in the code block (adding ordered suffixes when a signature repeats the same operand position), the `Type` column reflects the configured operand type, and the `Value` column summarizes the literal token or numeric constraints implied by the configuration (for example, the concrete register name, `[reg+offset]`, an allowed enumeration token, or the numeric min/max for `numeric_bytecode`). Descriptions and details prefer author-provided documentation but may be augmented with derived information. Column inclusion continues to follow the [Table Column Optimization](#table-column-optimization) rules.

Operand placeholders and table rows are derived from the instruction version's operand configuration:

- **Specific operands**: For each entry in `specific_operands`, emit a dedicated syntax block. Operands appear in the order of the `list` dictionary. The `Operand` column uses the resolved syntax string (with numeric suffixes appended only when the same operand position appears multiple times), the `Type` column is populated from that operand's configured `type`, and the `Value`/`Description`/`Details` columns combine derived constraints (register name, enumeration token, numeric bounds, addressing wrapper) with any text from the operand's `documentation` stanza. If an operand uses the `empty` type, omit it from the mnemonic output while still documenting it in the table so that readers understand the implicit behavior.
- **Operand sets**: When `operand_sets` are used (and no overlapping `specific_operands` override the combination), emit a syntax block whose operand placeholders come from the resolved syntax of each set entry. The `Type` column for these rows is the literal string `operand_set`, and the description data is sourced from the operand set's documentation (`operand_sets.<set name>.documentation.description` with optional `details`). If an operand set lacks documentation, leave the description blank in this table—the Operand Sets section already clarifies the set's members and behavior. When an operand set has exactly one operand value, the calling syntax and table use that member’s syntax/name/value/type instead of the set key.
- **Mixed configurations**: When both `specific_operands` and `operand_sets` are present, list all `specific_operands` variants first (preserving configuration order) and then emit the operand set signature that applies when no specific variant matches.

For instruction versions with zero operands, still render the `*Calling syntax:*` lead-in and a single-line code block containing only the mnemonic. In this case the `where` paragraph and operand table are omitted.

After all version sections are rendered, if the instruction has a `modifies` field, list it in a markdown table under the instruction's documentation with the text header of "Modifies:". Each entry in the `modifies` field will be listed in the table with the following columns:
- `Type` - The type of modification (Register, Memory, or Flag).
- `Target` - The target that is modified (register name, memory location, or flag name).
- `Description` - The description of the modification.
- `Details` - The detailed description of the modification.

Note: Column inclusion follows the [Table Column Optimization](#table-column-optimization) rules - empty columns will be omitted from the generated table. Once the `Modifies` and `Examples` subsections (if present) are emitted for an instruction, insert a horizontal rule (`---`) before documenting the next instruction in the category. This provides clear separation between instruction entries without interrupting the syntax section itself.

If the instruction has an `examples` field under the instruction's documentation, then a `#### Examples` section will be added under the instruction's documentation and the examples will be added with this format:
```markdown
#### Examples
##### <example description>
<example details formatted as markdown text>
<example code formatted as markdown code block>
```

### Macro Documentation Section

Macro documentation is emitted under a dedicated `# Macros` heading. Macros are grouped by their `documentation.category` (or `Uncategorized` when absent) using `## <category>` subsections. Each macro uses the same presentation as instructions: a `### \`<mnemonic>\` : <title>` heading when a title is present, followed by shared description/details, per-variant calling syntax and `where` tables derived from the macro’s operand configuration, and optional `Modifies` and `Examples` subsections. Variant-level documentation from individual entries in the macro `variants` list is rendered within the corresponding version block just like instruction variants. Macros without documentation are still listed with a placeholder message when documentation is generated.

## CLI Command Implementation

The documentation generation feature will be accessible via a new CLI command:

### Command Syntax
```
bespokeasm docs -c /path/to/language_config.yaml -o /path/to/documentation.md
```

### Command Options
- `-c, --config-file` (required): Path to the ISA configuration file (YAML or JSON)
- `-o, --output-file` (optional): Path to output markdown file. If not specified, the output file will be created in the same directory as the config file with the same base name but `.md` extension
- `-v, --verbose`: Enable verbose output for debugging

### Output File Generation Logic
When the `-o` option is not provided:
1. Take the directory path of the input configuration file
2. Take the base filename (without extension) of the configuration file
3. Append `.md` extension
4. Create the output file path by combining directory + base filename + `.md`

Example: `config/my-isa.yaml` → `config/my-isa.md`

### Error Handling Requirements

The documentation generator must handle the following error conditions gracefully:

#### Configuration File Errors
- **File not found**: Clear error message indicating the config file path doesn't exist
- **Invalid file format**: Clear error message for malformed YAML/JSON with line numbers if possible
- **Missing required fields**: Clear error message indicating which required fields are missing from the ISA configuration
- **Invalid documentation structure**: Clear error message for malformed documentation fields

#### Output File Errors
- **Permission denied**: Clear error message when output directory is not writable
- **Directory doesn't exist**: Attempt to create parent directories, or clear error if creation fails
- **File already exists**: Overwrite with warning message (unless in quiet mode)

#### Documentation Content Errors
- **Missing documentation fields**: Gracefully skip missing optional documentation fields without error
- **Invalid markdown in details**: Preserve content as-is but warn if verbose mode is enabled
- **Empty categories**: Skip empty instruction categories in output
- **Malformed examples**: Skip individual malformed examples but process others

#### Verbose Output
When `-v` flag is used, provide detailed information about:
- Configuration file loading process
- Documentation fields found and processed
- Warnings for missing optional fields
- Output file generation progress
- Summary of instructions, categories, and examples processed

## Language Extension
The language extension feature of **BesopokeASM** will be used to add various IDE-specific features to the language extensions that are available.

### VS Code Extension
The VS Code language extension will be augmented with a [HoverProvider](https://code.visualstudio.com/api/language-extensions/programmatic-language-features) that will provide the documentation for the instruction when the user hovers over the instruction in the editor.

### Sublime Text Extension

## Cursor Project Rules

# Design Considerations

## Implementation Architecture

The documentation generation feature will be implemented in the `src/bespokeasm/docsgen/` directory to maintain separation from the existing `configgen` modules used for IDE syntax highlighting.

## Reusable Documentation Elements
The internal documentation model should be designed such that the same methods can be used for generating the markdown documentation page, the language extensions, and the cursor project rules.
