# Overview
The goal of this feature is to create a standard way of documenting an instruction set architecture in the **BesopokeASM** language configuration file, and then a way to generate a Markdown documentation page from the configuration file.

# Requirements

## Configuration File
All added elements for documentation will be optional. If the user does not provide a value for the documentation field, then the documentation will not be generated for the relevant aspect of the instruction set architecture.

### General Documentation
The general documentastion is mostly implied by the configuration of the `general` section of the instruction set configuration file. However, `general` section can have an optional `documetnations` field that can be used for top-level documentation of the instruction set architecture. The `docuemtnation` sections will have the following fields (all optional):

| Option Key | Value Type | Description |
| --- | --- | --- |
| `description` | string | A short description of the instruction set architecture. |
| `details` | string | _Optional_ A detailed description of the instruction set architecture. Markdown text is allowed. |
| `addressing_modes` | dictionary | _Optional_ A dictionary of addressing modes. The keys are the addressing mode names and the values are dictionaries with the following keys:<ul><li>`description` - A short description of the addressing mode.</li><li>`details` - _Optional_ A detailed description of the addressing mode. Markdown text is allowed.</li></ul>The keys in this dictionary are used by the `mode` field in the [Operand Documentation](#operand-documentation) section. Note that while there is corelation between an instruction set's addressing modes and **BespokeASM**'s operand types, an operand type describes how *BespokeASM* will parse the operand value when assembling an instruction, while an addressing mode describes how the operand value is used in the instruction set and ultimately in the hardware the assembled bytecode is executed on and is not a **BespokeASM** concept. |
| `examples` | array | _Optional_ An array of example instructions. Each example is a dictionary with the following keys:<ul><li>`description` - A short description of the example.</li><li>`details` - _Optional_ A detailed description of the example. Markdown text is allowed.</li><li>`code` - The code of the example instruction.</li></ul><p>Examples are used to show how the instruction set can be used in practice. They should be used to demonstrate the use of the instruction set in a way that is easy to understand and use. |


### Instruction Documentation
Each instruction entry in the configuration file (as documented in the [Instruction Set Configuration File](https://github.com/michaelkamprath/bespokeasm/wiki/Instruction-Set-Configuration-File#instructions) wiki page) must be able to describe the instruction in a way that is easy to understand and use. It will do this by adding an optional `documentation` field to the instruction entry. The `documentation` field will be a dictionary with the following keys:

| Option Key | Value Type | Description |
| --- | --- | --- |
| `category` | string | The category of the instruction. This is used to group instructions together in the documentation page.  Categories include things like "Data Movement", "Arithmetic", "Control Flow", "Memory", "I/O", "Bitwise", etc. There is no absolute constraint on the categories, but they should be used to group instructions together in a way that is easy to understand and use, and the catefory titles should be concise and descriptive. |
| `description` | string | A short description of the instruction. |
| `details` | string | _Optional_ A detailed description of the instruction. Markdown text is allowed. |
| `modifies` | array | _Optional_ An array of dictionaries each representing a register or memory location that is modified by the instruction. Each dictionary has the following keys:<ul><li>`register` - The register that is modified. The value of this key is the name of the register.</li><li>`memory` - The memory location that is modified. The value of this key is the name of the memory location.</li><li>`flag` - The flag that is modified. The value of this key is the name of the flag.</li><li>`description` - A short description of the modification.</li><li>`details` - _Optional_ A detailed description of the modification. Markdown text is allowed.</li></ul><p>The each dictionary must contain exact one of the keys `register`, `memory`, or `flag`, and the `description` field, and `details` field is optional. |
| `examples` | array | _Optional_ An array of example usages of the instruction. Each example is a dictionary with the following keys:<ul><li>`description` - A short description of the example.</li><li>`details` - _Optional_ A detailed description of the example. Markdown text is allowed.</li><li>`code` - The code of the example instruction.</li></ul><p>Examples are used to show how the instruction can be used in practice. They should be concise and to the point. |

### Operand Documentation
Each operand entry in the configuration file (as documented in the [Instruction Set Configuration File](https://github.com/michaelkamprath/bespokeasm/wiki/Instruction-Set-Configuration-File#operands) wiki page) must be able to describe the operand in a way that is easy to understand and use. It will do this by adding an optional `documentation` field to the operand entry. The `documentation` field will be a dictionary with the following keys:

| Option Key | Value Type | Description |
| --- | --- | --- |
| `mode` | string | A short string representing the aaddressing mode of the operand. For example 'register', 'immediate', 'memory', 'flag', etc. The value of this field is the key in the `addressing_modes` dictionary in the [General Documentation](#general-documentation) section. |
| `description` | string | A short description of the operand. |
| `details` | string | _Optional_ A detailed description of the operand. Markdown text is allowed. |

### Operand Set Documentation

# Generated Documentation

## Markdown Documentation Page

### Instruction Set Documentation
The instructions sections of the documetnation page will be prefaced with a markdown sectiontion header `# Instructions` and then the instructions will be listed in alphabetical order.

Each instruction's documentation will be prefaced with a markdown section header `## <instruction mnemonic> : <instruction description>]` when `<instruction mnemonic>` is the instruction mnemonic and  ` : <instruction description>` is the instruction description from the [Instruction Documentation](#instruction-documentation) section and is only present if the `description` field is present in the [Instruction Documentation](#instruction-documentation) section.



## Language Extension
The language extension feature of **BesopokeASM** will be used to add various IDE-specific features to the language extensions that are available.

### VS Code Extension
The VS Code language extension will be augmented with a [HoverProvider](https://code.visualstudio.com/api/language-extensions/programmatic-language-features) that will provide the documentation for the instruction when the user hovers over the instruction in the editor.

### Sublime Text Extension

## Cursor Project Rules

# Design Considerations

## Reusable Documentation Elements
The internal documentation model should be designed such that the same methods can be used for generating the markdown documentation page, the language extensions, and the cursor project rules.
