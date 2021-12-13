# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](http://keepachangelog.com/en/1.0.0/)
and this project adheres to [Semantic Versioning](http://semver.org/spec/v2.0.0.html).

## TODO
Changes that are planned but not implemented yet:

* Add ability for an instruction to have order agnostic operands. That is, `instr a, b` is the same as `instr b, a`. This allows `swap` to occupy less instruction space.
* Enable instruction aliases that allow alternative mnemonics for an instruction. For example, allowing `call` and `jsr` to mean the same thing.
* Allow a label to exist on the same line as an instruction or directive
* add ability for source code to indicate what ISA version it needs to be compiled to.
* Improve error checking, notably with diallowed operands or unknown labels.

## [Unreleased]
* Added `indirect index register` addressing mode. 

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

[Unreleased]: https://github.com/michaelkamprath/bespokeasm/v0.1.5...HEAD
[0.1.6]: https://github.com/michaelkamprath/bespokeasm/v0.1.6...v0.1.5
[0.1.5]: https://github.com/michaelkamprath/bespokeasm/v0.1.5...v0.1.4
