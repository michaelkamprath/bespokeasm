"""Output-format options that source can set with `#output-format <format> <option>=<value> ...`.

A generator declares the options it accepts from source. A format offers the options of its
generators, with the defaults its definition gives them; a value set in source applies from
its line to the end of the file, and an option written without `=value` returns to the
format's default. Generated ISA documentation lists each format's options.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SourceOption:
    name: str
    # How the allowed values read in documentation and messages: "wrap, truncate or none".
    values: str
    description: str
    # Turns a configuration value, or the text written in source, into the option's value.
    # Raises ValueError with a message that completes "must be ...".
    parse: Callable[[Any], Any]


def _choice(*choices: str) -> Callable[[Any], str]:
    def parse(value: Any) -> str:
        text = str(value).strip().lower()
        if text not in choices:
            raise ValueError(f'one of {", ".join(choices)}')
        return text
    return parse


def _whole_number(minimum: int) -> Callable[[Any], int]:
    def parse(value: Any) -> int:
        if isinstance(value, bool):
            raise ValueError(f'a whole number of at least {minimum}')
        try:
            number = int(str(value).strip(), 0)
        except ValueError:
            raise ValueError(f'a whole number of at least {minimum}') from None
        if number < minimum:
            raise ValueError(f'a whole number of at least {minimum}')
        return number
    return parse


# The listing's instruction column: how a line wider than `width` is shown.
LISTING_OVERFLOW = SourceOption(
    'overflow', 'wrap, truncate or none',
    'How the listing shows source text wider than `width`: `wrap` continues it on the rows below, '
    '`truncate` cuts it short with `...`, and `none` widens the column to fit.',
    _choice('wrap', 'truncate', 'none'),
)
LISTING_WIDTH = SourceOption(
    'width', 'a whole number, at least 16',
    'The width, in characters, at which `overflow` applies.',
    _whole_number(16),
)
LISTING_DEFAULTS = {'overflow': 'none', 'width': 80}
