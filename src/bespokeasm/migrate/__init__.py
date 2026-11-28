"""Rewrites source written for another assembler into BespokeASM syntax.

An instruction set configuration declares, in its ``migrations`` section, the assemblers
("dialects") it can migrate source from and the rules for each. The rule kinds are a fixed
library implemented here, so a configuration never ships code. See :mod:`.dialects` for the
configuration and :mod:`.engine` for the migration itself.
"""
