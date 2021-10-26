# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](http://keepachangelog.com/en/1.0.0/)
and this project adheres to [Semantic Versioning](http://semver.org/spec/v2.0.0.html).

## TODO
Changes that are planned but not implemented yet:

* Add ability for an instruction to have order agnostic operands. That is, `instr a, b` is the same as `instr b, a`. This allows `swap` to occupy less instruction space.
* Allow a label to exist on the same line as an instruction or directive

## [Unreleased]
* added some error checking on the configuration file
* added support for local and file scoped labels. Local labels start with a . and are only valid between two non-local labels. File scope labels start with a _ and are only valid within the same file they are defined.

## 0.1.4
First tracked released
* Enabled the `reverse_argument_order` instruction option be applied to a specific operand configuration. This slightly changed the configuration file format.
* Added ability for instructions with operands to have a single "empty operand" variant, e.g., `pop`

[0.1.5]: https://github.com/michaelkamprath/bespokeasm/v0.1.5...v0.1.4
[Unreleased]: https://github.com/michaelkamprath/bespokeasm/v0.1.4...HEAD
