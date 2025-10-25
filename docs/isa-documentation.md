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
| `description` | string | A short description of the instruction. |
| `details` | string | _Optional_ A detailed description of the instruction. Markdown text is allowed. |
| `modifies` | array | _Optional_ An array of dictionaries each representing a register or memory location that is modified by the instruction. Each dictionary has the following keys:<ul><li>`register` - The register that is modified. The value of this key is the name of the register.</li><li>`memory` - The memory location that is modified. The value of this key is the name of the memory location.</li><li>`flag` - The flag that is modified. The value of this key is the name of the flag.</li><li>`description` - A short description of the modification.</li><li>`details` - _Optional_ A detailed description of the modification. Markdown text is allowed.</li></ul><p>Each `modifies`dictionary must contain exact one of the keys `register`, `memory`, or `flag`, and the `description` field, and `details` field is optional. |
| `examples` | array | _Optional_ An array of example usages of the instruction. Each example is a dictionary with the following keys:<ul><li>`description` - A short description of the example.</li><li>`details` - _Optional_ A detailed description of the example. Markdown text is allowed.</li><li>`code` - The code of the example instruction.</li></ul><p>Examples are used to show how the instruction can be used in practice. They should be concise and to the point. |

### Operand Documentation
Each operand entry in the configuration file (as documented in the [Instruction Set Configuration File](https://github.com/michaelkamprath/bespokeasm/wiki/Instruction-Set-Configuration-File#operands) wiki page) must be able to describe the operand in a way that is easy to understand and use. It will do this by adding an optional `documentation` field to the operand entry. The `documentation` field will be a dictionary with the following keys:

| Option Key | Value Type | Description |
| --- | --- | --- |
| `mode` | string | A short string representing the aaddressing mode of the operand. For example 'register', 'immediate', 'memory', 'flag', etc. The value of this field is the key in the `addressing_modes` dictionary in the [General Documentation](#general-documentation) section. |
| `description` | string | A short description of the operand. |
| `details` | string | _Optional_ A detailed description of the operand. Markdown text is allowed. |

### Operand Set Documentation
_TBC_

# Generated Documentation

## Markdown Documentation Page

The generated markdown documentation will be structured as follows:

### Overall Document Structure

The markdown documentation page will have the following overall structure:

1. **Document Header** - ISA name (from `general.identifier.name`) and description (from `general.documentation.description` if present)
2. **General Information Section** - Comprehensive information from the entire `general` section including hardware architecture, configuration details, and custom documentation if present
3. **Instructions Section** - Organized by category with detailed instruction documentation

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
**Registers** - If the `registers` seciton fo the `general` configuration is present, then the set of registers will be documentated in a table with the following columns:
* Register Name
* Description
* Bit Size

The columns in this table should only be present if the relevant configuration is available for at least one register in the set.

#### Addressing Modes
- **Addressing Modes** - Table of addressing modes from `general.documentation.addressing_modes` (if present)

#### Flags
- **Flags** - Table of flags from `general.flags` (if present). Each flag entry is keyed by its symbol, and the symbol is rendered as inline code in the table.

#### Examples
- **Examples** - Code examples from `general.documentation.examples` (if present)

#### Compatibility
- **Minimum BespokeASM Version** - From `general.min_version` (required field)

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

Each instruction's documentation will be prefaced with a markdown section header ``### `<instruction mnemonic>` : <instruction description>`` where `<instruction mnemonic>` is the instruction mnemonic capitalized and rendered as inline code. The ` : <instruction description>` suffix comes from the [Instruction Documentation](#instruction-documentation) section and is only present if the `description` field is provided.

If the instruction has a `modifies` field, then it will be listed in a markdown table under the instruction's documentation with the text header of "Modifies:". Each entry in the `modifies` field will be listed in the table with the following columns:
- `Type` - The type of modification (Register, Memory, or Flag).
- `Target` - The target that is modified (register name, memory location, or flag name).
- `Description` - The description of the modification.
- `Details` - The detailed description of the modification.

Note: Column inclusion follows the [Table Column Optimization](#table-column-optimization) rules - empty columns will be omitted from the generated table.

If the instruction has an `examples` field under the instruction's documentation, then a `#### Examples` section will be added under the instruction's documentation and the examples will be added with this format:
```markdown
#### Examples
##### <example description>
<example details formatted as markdown text>
<example code formatted as markdown code block>
```

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
