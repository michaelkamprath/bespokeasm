# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](http://keepachangelog.com/en/1.0.0/)
and this project adheres to [Semantic Versioning](http://semver.org/spec/v2.0.0.html).

## TODO
Changes that are planned but not implemented yet:

* Add ability for an instruction to have order agnostic operands. That is, `instr a, b` is the same as `instr b, a`. This allows `swap` to occupy less instruction space.
* Enable instruction aliases that allow alternative mnemonics for an instruction. For example, allowing `call` and `jsr` to mean the same thing.
* Allow a label to exist on the same line as an instruction or directive
* Create a memory block macro that allows the definition of memory blocks at specific addresses without altering the current address for compilation. This would be used for creatin RAM variables from ROM area code. Also used to place a specific block of code at a specific address. Different from `.org` in that there is an end of the block and at that point the address contniues on from what it was before the start of the block.
* Converge on `byte_code` or `bytecode` in instruction set configuration file
* Improve error checking:
  * Disallowed operands
  * missing `:` after labels
  * unknown labels

KENBAK-1 TODO:
* add compiler defined constants
* Finish ISA
* Add good examples
* Write documentation for KENBAK-1 and Eater SAP-1

## [0.2.0]
* Added `deferred_numeric` operand type. Its intended to be used as a "double derefence" type operand (the value is at the address value contained at the address numeric value given)
* Added `enumeration` operand type that creates byte code and argument values based on a key/value pairs
* Added `numeric_bytecode` operand type that converts the operand numeric value into byte code subject to a bounds check. Useful for bit index type operands that are really different instructions based on value.
* Added the ability for operand byte code contributions to prefix the instruction byte code as opposed to suffixing it.
* Added instruction byte code suffix that suffixes the byte code after the operand byte code is added
* Added examples for the KENBAK-1 retro-computer.


## [0.1.9]
* Fixed language version checking
* Added syntax highlighting for escape characters in strings.

## [0.1.8]
* Improvements to Visual Studio Code language extension generation
* Added ability to generate a language package for Sublime Text editor
* Enabled directive arguments to be numerical expressions
* Added ability for source code to indicate what ISA version it needs to be compiled with.

## [0.1.7]
* Added ability to generate a language extension with syntax highlighting for Visual Code Studio

## [0.1.6]
* Added `indirect index register` addressing mode.
* Fixed a bug in parsing binary numbers assigned to constants
* Added `.cstr` data type to be a null-terminated `.byte` blob, or a C-style string.
* Made `.byte` and `.cstr` data created by strings honor python-style escape sequences in the strings.
* Added improved error checking:
  * Ensures indirect register operands with an offset are properly configured.
  * Ensure that labels do not use directives or key words

## [0.1.5]
* added some error checking on the configuration file
* added support for local and file scoped labels. Local labels start with a `.` and are only valid between two non-local labels. File scope labels start with a `_` and are only valid within the same file they are defined.
* added error that detects when register labels are used in numeric expresions.
* added the ability to `#include` other `asm` source files when compiling a given source file.
* Added the concept of instruction variants to the ISA model configuration. Instruction variants allow a specific operand configuration for an instruction to generate wholely different byte code, such as a different prefix value.

## 0.1.4
First tracked released
* Enabled the `reverse_argument_order` instruction option be applied to a specific operand configuration. This slightly changed the configuration file format.
* Added ability for instructions with operands to have a single "empty operand" variant, e.g., `pop`

[Unreleased]: https://github.com/michaelkamprath/bespokeasm/compare/v0.1.8...HEAD
[0.1.8]: https://github.com/michaelkamprath/bespokeasm/compare/v0.1.8...v0.1.7
[0.1.7]: https://github.com/michaelkamprath/bespokeasm/compare/v0.1.7...v0.1.6
[0.1.6]: https://github.com/michaelkamprath/bespokeasm/compare/v0.1.6...v0.1.5
[0.1.5]: https://github.com/michaelkamprath/bespokeasm/compare/v0.1.5...v0.1.4
