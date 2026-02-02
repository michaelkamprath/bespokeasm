# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](http://keepachangelog.com/en/1.0.0/)
and this project adheres to [Semantic Versioning](http://semver.org/spec/v2.0.0.html).

## TODO
Changes that are planned but not implemented yet:

* Add ability for an instruction to have order agnostic operands. That is, `instr a, b` is the same as `instr b, a`. This allows `swap` to occupy less instruction space.
* Improve error checking:
  * Disallowed operands
  * missing `:` after labels
  * unknown labels
  * Disallow instructions on the same line as an `.org` directive
* Create a "align if needed" preprocessor directive paid that generates an `.align` directive if the bytecode in between the pair isn't naturally on the same page and can fit on the same page if aligned. An error would be benerated if the block of code can't fit on the same page regardless of alignment.
* Update the `#ifdef` and related preprocessor directives to include detection of labels and constants.
* Allow multiple `cstr` defininitions on the same line


## [Unreleased]
* Added `.16byte` data directive to emit 16-byte values with configured multi-word endianness.
* Added `#error` preprocessor directive for compile-time errors with optional message.

## [0.7.1]
* Added support to the VSCode and Sublime Text language extensions for editor hovers for mnemonics, labels, and constants; plus improved semantic syntax highlighting that differentiations label and constant defintion from label and constant usage.
* Updated the `#include` preprocessor directive to allow relative paths in the specified included file. The relative paths are resolved relative to the file currently being compiled.
* Fixed bug where conditional compilation was not handling constant definition correctly.
* Added user warnings for scenarios that wouldn't prevent a successful compilation but are potentionally an unintended bug by the user. Warnings can be elevated to errors with the `-W` command line option.
* Consolidated all error, warning, and info handling into a centralized manager class. This will allwo more consistent behavior in the future.

## [0.7.0]
- Fixed a bug in handling comparisons to preprocessor language version symbols.
- Added GitHub action to automatically create stand-alone binaries upon release, or create them locally using the Makefile.
- Added command to install shell tab completions for  **BespokeASM**.
- Added the ability to create a markdown file documenting the configured instruction set in a human- and AI-readable format. Intended use is to provide AI coding agents with documentation of the assembly language and how to use it. Use in combination with [the general **BespokeASM** syntax documentation](https://github.com/michaelkamprath/bespokeasm/wiki/Assembly-Language-Syntax). Consider this feature as "beta", as the format and completeness of the generated output will evolve.
- Removed the unmaintained `update-config` command.

## [0.6.0]
- Added support for instruction aliases: you can now specify an `aliases` field (a list of alternative mnemonics) in an instruction's configuration. All aliases are globally unique, are accepted as valid mnemonics in assembly source, and generate the same code as the root mnemonic. This does not apply to macros.
- Added `#print` preprocessor directive for compile-time messages with optional verbosity gating and honoring conditional/mute controls.
- Added Vim syntax highlighting generator via `bespokeasm generate-extension vim`. This creates Vim `syntax/` and `ftdetect/` files for your ISA.
- Added support for built-in language version symbols in `#require`, `#if`, and `#elif` preprocessor directives.
- Added **named label scopes** feature: Create custom symbol namespaces with user-defined prefixes that can be shared across files. Use `#create-scope "name" prefix="prefix_"`, `#use-scope "name"`, and `#deactivate-scope "name"` directives. Supports library workflows where scopes can be used before being defined.
- Fixed a bug where `#include` directives were not properly processed when they were inside a conditional block.
- Fixed a test isolation issue where instruction pattern caching caused pytest failures when different ISA configurations were used across test files.

## [0.5.1]
- Support for preserving comments, integer formats, list formats, and file type in configuration files during `update-config` command
- Added `string_byte_packing` and `string_byte_packing_fill` options to the `general` section of the configuration file. When `string_byte_packing` is enabled, quoted strings in `.byte` and `.cstr` data directives are packed tightly into words (if `word_size` is a multiple of 8 and at least 16). The `string_byte_packing_fill` option controls the byte value used to pad the last word if the string does not fill it completely. The `.cstr` directive always appends the configured `cstr_terminator` before padding. Extensive tests and documentation updates included.

## [0.5.0]
* Major refactoring of the code base the enables support for data words of any size. See [Data Words and Endianness](https://github.com/michaelkamprath/bespokeasm/wiki/Instruction-Set-Configuration-File#data-words-and-endianness) for more information.This is a **BREAKING CHANGE** for the configuration file.
  * The `endian` general configuration option is deprecated and replaced with `multi_word_endianness` and `intra_word_endianness`.
  * The `byte_size` configuration options used in many places is deprecated and replaced with `word_size`. Similarly, the `byte_align` configuration option is deprecated and replaced with `word_align`.
  * **Additional upgrade instructions for configuration file changes:**
    * The new fields `multi_word_endianness` and `intra_word_endianness` must be set to either `'big'` or `'little'`. If omitted, they default to `'big'`.
    * The new field `word_size` (in bits) replaces all uses of `byte_size`. If omitted, it defaults to `8`.
    * The new field `word_segment_size` (in bits) is optional and defaults to the value of `word_size`. Only set this if your word is composed of smaller segments (e.g., 16-bit word with 8-bit segments).
    * The new field `word_align` replaces `byte_align` for alignment settings.
    * All these fields must be placed in the `general` section of the configuration file.
    * The deprecated fields (`endian`, `byte_size`, `byte_align`) are still recognized for now, but will emit warnings and should be removed from your configuration files.
* Upgrade python version requirements to 3.11
* Improved several error messages
* Fixed a bug where embedded strings weren't properly parsed if they contained a newline character or there were multiple embedded strings per line
* Fixed a bug where parsing properly discriminate between labels starting with `BYTE` string and the `BYTEx()` operator.
* Fixed a bug in generating the syntax highlighting configuration that caused mnemonics with special characters to not be highlighted properly.
* Added support for symbol definitions in Sublime Text. Symbols defined are labels and constants.
* Added a new `update_config` CLI command to automatically upgrade older configuration files to the latest format required by this version. This tool will convert deprecated fields, set new defaults, and update the `min_version` field for you.
* Running 'bespokeasm <args>' now defaults to the 'compile' command, so you no longer need to specify 'compile' explicitly. Other commands (such as 'update-config' and 'generate-extension') still require their explicit subcommand.

## [0.4.2]
*  Added support for The Minimal 64x4 Home Computer with an example and updated assembler functionality to support it.
*  Added `address` operand type that enables several features specific to absolute addresses, include slicing the address to support "short jump" type instructions.
*  Added `.align` directive to align the current address to a multiple of a given value.
*  Changed syntax highlight color theme name to be specific to the language rather than the generic "BespokeASM Theme" name.
*  Added optional support for embedded strings in the assembly code. When enabled, strings can be ebdedded in the code withou a data directive such as `.cstr`. This is enabled by setting the `allow_embedded_strings` option in the `general` section of the configuration file to `true`.
*  Added ability to mute byte code emission with the preprocessor directive `#mute` and unmute with `#unmute`.
*  Improved handling of include directories  by duplicating and normalizing all search paths.

## [0.4.1]
* added `.asciiz` as an equivalent data directive to `.cstr`
* Updated Github workflow to add Python 3.11 to the test matrix.
* Remove usage of deprecated aspects of Python `importlib` library so that the code will work with Python 3.11 without deprecation warnings.
* Fixed [reported bug](https://github.com/michaelkamprath/bespokeasm/issues/25) where indirect indexed register operands were not parsed properly.
* Fixed bug that did not sanely handle an instructions operand configuration indicating 0 operands
* Allow predefined constants to labels starting with `_`, which also indicates file scope for code defined labels
* Added The Minimal 64 Home Computer example
* Added support for negative values in numeric expressions, data type initializations, and constant values
* Improved several compilation errors.

## [0.4.0]
* Added ability to create preprocessor macros/symbols with `#define` directive. Thes macros can then be used in code. Also added the ability to define preprocessor symbols on the command line and in the instruction set configuration file.
* Added conditional assembly preprocessor directives tht act on preprocessor symbols:
  * `#if`
  * `#elif`
  * `#else`
  * `#endif`
  * `#ifdef`
  * `#ifndef`
* Added the ability to set the `cstr` terminating character. It default to `0`, but can be set to another byte value.
* Added support for using character ordinals in numeric expressions. For example, `'a'` is the same as `97`. Only valid for single character strings using single quotes.
* Allow expressions to be used in data directives. For example, `.byte 1 + 2` is the same as `.byte 3`.

## [0.3.3]
* Improved error messages for a badly configured configuration file.
* Added the listing pretty print format, replacing the legacy default pretty print format.

## [0.3.2]
* Corrected workflows bug
* Improved error messaging
* Added `indexed_register` operand type. Similar to `indirect_indexed_register`, but it does not imply the address dereferencing.

## [0.3.1]
* Changed the instaltion method to use the modern `pyproject.toml` approach.

## [0.3.0]
* Added ability for an numeric operand that is ostensibly an address to be checked to be a valid address value per the `GLOBAL` memory zone. Uses the `valid_address` option in the `argument` setting for an operand. Only valid for `numeric`, `indirect_numeric`, `deferred_numeric`, and `relative_address` operand types.
* Added checks to ensure memory zones are defined within the `GLOBAL` memory zone.
* Allow instruction configuration to only contain a `variants` list.
* Added example for the MOSTEK 3870
* Added example for Intel 8085 processor
* Addressed some bugs in how macros are handled.
* Added syntax highlighting to differentiate macros from native instructions
* Added operand decorators to some operand types. This allows for some semantically differentiated notation, for exmaple, here `++` is the decorator: `[sp]++`
* Added hexadecimal format indicated by a trailing capital `H`. For example `08FH` would be a hex value for `$8F`.
* Added ability to use `EQU` to assign constant label values in addition to `=`.
* Changed use of `byte_code` to `bytecode` in instruction set configuration file. THIS IS A BREAKING CHANGE

## [0.2.4]
* Fixed bug where unknown instructions did not produce an error.
* Fixed bug where `#include` directives did not recognize otherwise valid file names
* Fixed bug where zero operand macros did not get recognized correctly
* Added ability to reverse the order of the byte code that an instruction's operands emit.
* Added the `relative_address` operand type.
* Added more examples
* Added named memory zones feature.
  * As a result of this addition, the "memory block" feature was renamed to "data block" to further distinguish the two features.

## [0.2.3]
* Made instructions case insensitive
* Added example for the slu4 Minimal UART CPU System
* Added more pretty print formats and the ability to select them
* Added support for more than one instruction per line in the assembly source. There are some limitations. See documentation.
* Added support for `MSB` and `LSB` unary functions in expressions

## [0.2.2]
* Added instruction macros feature
* Started using `pipenv` for dependency management.
* Fixed bug for numeric enumeration operads that emit a argument value.
* Added `.8byte` data type directive
* Fixed bug in how complex expressions are parsed in certain directive arguments
* Added bit shifting operations to expressions
* Fixed a bug in handling registers named `b`, which is also the binary number prefix

## [0.2.1]
* Allow a label to exist on the same line as an instruction or directive
* Fixed a bug in how compiler defined constants were handled
* Fixed and improved syntax highlighting for language extensions
* Added some snippets
* Improved error handling
* Added KENBAK-1 example

## [0.2.0]
* Added `deferred_numeric` operand type. Its intended to be used as a "double derefence" type operand (the value is at the address value contained at the address numeric value given)
* Added `enumeration` and `numeric_enumeration` operand type that creates byte code and argument values based on a key/value pairs. `enumeration` uses string keys, and `numeric_enumeration` uses integer key values reesolved from a numeric expression.
* Added `numeric_bytecode` operand type that converts the operand numeric value into byte code subject to a bounds check. Useful for bit index type operands that are really different instructions based on value.
* Added the ability for operand byte code contributions to prefix the instruction byte code as opposed to suffixing it.
* Added instruction byte code suffix that appends the byte code after the operand byte code is added to the base byte code.
* Added `origin` option to `general` section of configuration that sets the initial origin address for compilation. Defaults to zero.
* Added support for predefined constants and memory blocks with labels that can be used at compile time.
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

[Unreleased]: https://github.com/michaelkamprath/bespokeasm/compare/v0.7.1...HEAD
[0.7.1]: https://github.com/michaelkamprath/bespokeasm/compare/v0.7.0...v0.7.1
[0.7.0]: https://github.com/michaelkamprath/bespokeasm/compare/v0.6.0...v0.7.0
[0.6.0]: https://github.com/michaelkamprath/bespokeasm/compare/v0.5.1...v0.6.0
[0.5.1]: https://github.com/michaelkamprath/bespokeasm/compare/v0.5.0...v0.5.1
[0.5.0]: https://github.com/michaelkamprath/bespokeasm/compare/v0.4.2...v0.5.0
[0.4.2]: https://github.com/michaelkamprath/bespokeasm/compare/v0.4.1...v0.4.2
[0.4.1]: https://github.com/michaelkamprath/bespokeasm/compare/v0.4.0...v0.4.1
[0.4.0]: https://github.com/michaelkamprath/bespokeasm/compare/v0.3.3...v0.4.0
[0.3.3]: https://github.com/michaelkamprath/bespokeasm/compare/v0.3.2...v0.3.3
[0.3.2]: https://github.com/michaelkamprath/bespokeasm/compare/v0.3.1...v0.3.2
[0.3.1]: https://github.com/michaelkamprath/bespokeasm/compare/v0.3.0...v0.3.1
[0.3.0]: https://github.com/michaelkamprath/bespokeasm/compare/v0.2.4...v0.3.0
[0.2.4]: https://github.com/michaelkamprath/bespokeasm/compare/v0.2.3...v0.2.4
[0.2.3]: https://github.com/michaelkamprath/bespokeasm/compare/v0.2.2...v0.2.3
[0.2.2]: https://github.com/michaelkamprath/bespokeasm/compare/v0.2.1...v0.2.2
[0.2.1]: https://github.com/michaelkamprath/bespokeasm/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/michaelkamprath/bespokeasm/compare/v0.1.9...v0.2.0
[0.1.9]: https://github.com/michaelkamprath/bespokeasm/compare/v0.1.8...v0.1.9
[0.1.8]: https://github.com/michaelkamprath/bespokeasm/compare/v0.1.7...v0.1.8
[0.1.7]: https://github.com/michaelkamprath/bespokeasm/compare/v0.1.6...v0.1.7
[0.1.6]: https://github.com/michaelkamprath/bespokeasm/compare/v0.1.5...v0.1.6
[0.1.5]: https://github.com/michaelkamprath/bespokeasm/compare/v0.1.4...v0.1.5
