import re
from dataclasses import dataclass


PREPROCESSOR_MESSAGE_COLORS = (
    'black',
    'red',
    'green',
    'yellow',
    'blue',
    'magenta',
    'cyan',
    'white',
)
_COLOR_PATTERN = '|'.join(PREPROCESSOR_MESSAGE_COLORS)
_COLORED_MESSAGE_PATTERN = re.compile(
    rf'^(?:(.*)\s+)?({_COLOR_PATTERN})\s+"([\s\S]*?)"\s*$',
    flags=re.IGNORECASE,
)
_PREFIXED_MESSAGE_PATTERN = re.compile(r'^(.*)\s+"([\s\S]*?)"\s*$')
_MESSAGE_ONLY_PATTERN = re.compile(r'^"([\s\S]*?)"\s*$')


@dataclass(frozen=True)
class PreprocessorMessage:
    """A quoted directive message and any text that precedes it."""

    leading_text: str
    text: str
    color: str | None = None


def parse_trailing_message(source: str) -> PreprocessorMessage | None:
    """Parse the preferred interpretation of a final quoted message."""
    candidates = parse_trailing_message_candidates(source)
    return candidates[0] if candidates else None


def parse_trailing_message_candidates(
    source: str,
) -> tuple[PreprocessorMessage, ...]:
    """Return colored and plain interpretations of a quoted message suffix."""
    candidates = []
    colored_match = _COLORED_MESSAGE_PATTERN.fullmatch(source)
    if colored_match is not None:
        candidates.append(
            PreprocessorMessage(
                leading_text=(colored_match.group(1) or '').strip(),
                text=colored_match.group(3),
                color=colored_match.group(2).lower(),
            )
        )

    prefixed_match = _PREFIXED_MESSAGE_PATTERN.fullmatch(source)
    if prefixed_match is not None:
        candidates.append(
            PreprocessorMessage(
                leading_text=prefixed_match.group(1).strip(),
                text=prefixed_match.group(2),
            )
        )

    message_only_match = _MESSAGE_ONLY_PATTERN.fullmatch(source)
    if message_only_match is not None:
        candidates.append(
            PreprocessorMessage(
                leading_text='',
                text=message_only_match.group(1),
            )
        )
    return tuple(candidates)
