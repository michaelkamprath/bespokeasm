"""``#verbatim <namespace> [<part>]`` ... ``#endverbatim``: a block of text that is not assembled.

The lines between the two directives are kept exactly as written and are not preprocessed:
a ``#`` line inside a block is text. An output format writes a namespace's blocks with the
``verbatim`` generator, one section for the blocks that name no part and one for each part.
``AssemblyFile`` reads a block as a unit, so conditional compilation applies to it as a whole.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from bespokeasm.assembler.diagnostic_reporter import AssemblerError
from bespokeasm.assembler.line_identifier import LineIdentifier
from bespokeasm.assembler.line_object.preprocessor_line import PreprocessorLine
from bespokeasm.assembler.memory_zone import MemoryZone
from bespokeasm.assembler.parsing import split_line_comment

VERBATIM_DIRECTIVE = '#verbatim'
END_DIRECTIVE = '#endverbatim'
_VERBATIM_PATTERN = re.compile(r'#verbatim(?=\s|;|$)')
_END_PATTERN = re.compile(r'#endverbatim(?=\s|;|$)')
_NAMESPACE_PATTERN = re.compile(r'(?P<namespace>[A-Za-z][A-Za-z0-9_]*)(?:\s+(?P<part>[A-Za-z][A-Za-z0-9_]*))?')


def is_verbatim_line(line_str: str) -> bool:
    return _VERBATIM_PATTERN.match(line_str) is not None


def is_end_verbatim_line(line_str: str) -> bool:
    return _END_PATTERN.match(line_str) is not None


@dataclass(frozen=True)
class VerbatimBlockSource:
    """A block as read from a file: its directive lines and the text lines between them."""
    namespace: str | None                    # None when the #verbatim line names no namespace
    part: str | None                         # None when the #verbatim line names no part
    header: tuple[str, str]                  # the #verbatim line's code and comment
    body: tuple[tuple[int, str], ...]        # (line number, text as written) of each text line
    end_line: int
    end: tuple[str, str]                     # the #endverbatim line's code and comment


def read_verbatim_block(source_lines: list[str], index: int, line_id: LineIdentifier) -> VerbatimBlockSource:
    """Read the block whose ``#verbatim`` line is ``source_lines[index]``, through its ``#endverbatim``."""
    code, comment = split_line_comment(source_lines[index].strip())
    code = code.strip()
    rest = code[len(VERBATIM_DIRECTIVE):].strip()
    names = _NAMESPACE_PATTERN.fullmatch(rest)
    if rest and names is None:
        raise AssemblerError(
            line_id,
            'the #verbatim line takes an annotation namespace and an optional part, such as '
            f'"#verbatim xmin" or "#verbatim xmin header", not "{rest}"',
        )
    body: list[tuple[int, str]] = []
    for end_index in range(index + 1, len(source_lines)):
        line = source_lines[end_index].rstrip('\r\n')
        if is_end_verbatim_line(line.strip()):
            end_code, end_comment = split_line_comment(line.strip())
            if end_code.strip() != END_DIRECTIVE:
                raise AssemblerError(
                    LineIdentifier(end_index + 1, filename=line_id.filename),
                    f'{END_DIRECTIVE} takes no arguments',
                )
            return VerbatimBlockSource(
                namespace=names.group('namespace') if names else None,
                part=names.group('part') if names else None,
                header=(code, comment.strip()),
                body=tuple(body),
                end_line=end_index + 1,
                end=(end_code.strip(), end_comment.strip()),
            )
        body.append((end_index + 1, line))
    raise AssemblerError(line_id, f'#verbatim block started on line {line_id.line_num} has no #endverbatim')


class EndVerbatimLine(PreprocessorLine):
    """The ``#endverbatim`` line of a block. Emits nothing; the block's text is on its ``VerbatimLine``."""

    def __repr__(self) -> str:
        return f'EndVerbatimLine<{self._line_id}>'


class VerbatimLine(PreprocessorLine):
    """The ``#verbatim`` line of a block, carrying the block's text. Emits nothing."""

    def __init__(
        self,
        line_id: LineIdentifier,
        instruction: str,
        comment: str,
        memzone: MemoryZone,
        namespace: str,
        text_lines: tuple[str, ...],
        part: str | None = None,
    ) -> None:
        super().__init__(line_id, instruction, comment, memzone)
        self._namespace = namespace
        self._part = part
        self._text_lines = text_lines

    def __repr__(self) -> str:
        name = f'{self._namespace} {self._part}' if self._part else self._namespace
        return f'VerbatimLine<{name}: {len(self._text_lines)} lines>'

    @property
    def namespace(self) -> str:
        return self._namespace

    @property
    def part(self) -> str | None:
        """The part the block names, or ``None``."""
        return self._part

    @property
    def text_lines(self) -> tuple[str, ...]:
        """The block's lines exactly as written."""
        return self._text_lines

    @property
    def text(self) -> str:
        """The block's text as a format writes it: trailing spaces removed from each line, and the
        blank lines at the start and end of the block dropped."""
        lines = [line.rstrip() for line in self._text_lines]
        while lines and not lines[0]:
            lines.pop(0)
        while lines and not lines[-1]:
            lines.pop()
        return '\n'.join(lines)

    @staticmethod
    def check_names(line_id: LineIdentifier, namespace: str | None, part: str | None, namespaces: dict) -> None:
        """A block must name an annotation namespace of the ISA that accepts verbatim blocks, and
        a part only when the namespace declares it."""
        accepting = sorted(name for name, spec in namespaces.items() if spec.accepts_verbatim)
        if namespace is None:
            example = accepting[0] if accepting else 'xmin'
            raise AssemblerError(
                line_id,
                f'#verbatim requires an annotation namespace, for example "#verbatim {example}"',
            )
        spec = namespaces.get(namespace)
        if spec is not None and spec.accepts_verbatim:
            if part is None or part in spec.verbatim_part_names:
                return
            parts = spec.verbatim_part_names
            which = f'its parts are: {", ".join(parts)}' if parts else 'it declares no parts'
            raise AssemblerError(line_id, f"annotation '{namespace}' has no #verbatim part '{part}'; {which}")
        which = (
            f'namespaces that do: {", ".join(accepting)}' if accepting
            else 'no annotation namespace of this instruction set does'
        )
        raise AssemblerError(line_id, f"annotation '{namespace}' does not accept #verbatim blocks; {which}")
