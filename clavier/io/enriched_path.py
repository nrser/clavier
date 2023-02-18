from __future__ import annotations
import os
from pathlib import Path
from typing import Sequence, Type
from clavier.io.io_helpers import Grouper

import splatlog
from splatlog.lib.functions import SlotCachedProperty
from rich.console import (
    Console,
    ConsoleOptions,
    RenderResult,
)
from rich.text import Text
from rich.measure import Measurement
from rich.tree import Tree


_LOG = splatlog.get_logger(__name__)


class EnrichedPath:
    """
    Wraps a `pathlib.Path` object in a `rich.console.ConsoleRenderable` that
    either prints it as a single line (if there is space) or a tree-like stack.

    ##### Examples #####

    ```python
    >>> from pathlib import Path

    >>> wide = Console(width=80)
    >>> narrow = Console(width=30)

    >>> path = Path("/Users/nrser/src/github.com/nrser/clavier/.venv/bin/python")

    >>> wide.print(EnrichedPath(path, continuation = "… "))
    /Users/nrser/src/github.com/nrser/clavier/.venv/bin/python

    >>> narrow.print(EnrichedPath(path, continuation = "… "))
    /Users/nrser/src/github.com/
    … nrser/clavier/.venv/bin/
    … python

    ```
    """

    __slots__ = (
        "_path",
        "_sep",
        "_cont",
        "_min_width",
        "_max_width",
        "_sep_len",
        "_cont_len",
    )

    _path: Path
    _sep: str
    _cont: str
    _sep_len: int
    _cont_len: int

    def __init__(
        self, path: Path, *, separator: str = "/", continuation: str = "... "
    ):
        self._path = path
        self._sep = separator
        self._sep_len = len(separator)
        self._cont = continuation
        self._cont_len = len(continuation)

    @property
    def parts(self) -> tuple[str, ...]:
        return self._path.parts

    @SlotCachedProperty
    def min_width(self) -> int:
        return max(
            (len(part) + (0 if i == 0 else self._cont_len) + self._sep_len)
            for i, part in enumerate(self.parts)
        )

    @SlotCachedProperty
    def max_width(self) -> int:
        return len(str(self._path))

    def to_text(self) -> Text:
        pieces = []
        for part in self.parts:
            if pieces and pieces[-1][0] != self._sep:
                pieces.append((self._sep, "path.sep"))
            pieces.append(
                (part, "path.sep" if part == self._sep else "path.part")
            )

        return Text.assemble(*pieces, no_wrap=True)

    def __rich_measure__(
        self, console: Console, options: ConsoleOptions
    ) -> Measurement:
        return Measurement(self.min_width, self.max_width)

    def __rich_console__old(
        self, console: Console, options: ConsoleOptions
    ) -> RenderResult:
        if self.max_width < options.max_width:
            yield self.to_text()
            return

        parts = list(self.parts)
        is_first_line = True

        while parts:
            pieces: list[tuple[str, str]] = []
            length = 0

            while parts and (
                (
                    length
                    + (0 if is_first_line else self._cont_len)
                    + len(parts[0])
                    + self._sep_len
                )
                < options.max_width
            ):
                if pieces and (pieces[-1][0] != self._sep):
                    pieces.append((self._sep, "path.sep"))
                    length += self._sep_len

                part = parts.pop(0)

                pieces.append(
                    (
                        part,
                        "path.sep" if part == self._sep else "path.part",
                    )
                )

                length += len(part)

            if not pieces:
                part = parts.pop(0)
                pieces.append(
                    (
                        part,
                        "path.sep" if part == self._sep else "path.part",
                    )
                )

            if parts:
                pieces.append((self._sep, "path.sep"))

            yield Text.assemble(
                ("" if is_first_line else self._cont),
                *pieces,
                no_wrap=True,
            )

            is_first_line = False

    def _as_piece(self, s: str) -> tuple[str, str]:
        if s == self._cont:
            return (s, "path.cont")
        if s == self._sep:
            return (s, "path.sep")
        return (s, "path.part")

    def __rich_console__(
        self, console: Console, options: ConsoleOptions
    ) -> RenderResult:
        if self.max_width < options.max_width:
            yield self.to_text()
            return

        pieces: list[tuple[str, str]] = []

        for i, part in enumerate(self.parts):
            if (
                sum(len(part) for part, _style in pieces)
                + len(part)
                + self._sep_len
            ) < options.max_width:
                if pieces and pieces[-1][0] != self._sep:
                    pieces.append(self._as_piece(self._sep))

                pieces.append(self._as_piece(part))

            else:
                if pieces:
                    if i < len(self.parts):
                        pieces.append(self._as_piece(self._sep))

                    yield Text.assemble(*pieces, no_wrap=True)

                pieces = [
                    self._as_piece(self._cont),
                    self._as_piece(part),
                ]

        yield Text.assemble(*pieces, no_wrap=True)
