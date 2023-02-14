from __future__ import annotations
from argparse import SUPPRESS
from typing import TYPE_CHECKING, Callable

from rich.console import Group, RenderableType as _RT

from clavier import io

if TYPE_CHECKING:
    from ..rich_help_formatter import RichHelpFormatter


class RichSectionFormatter:
    formatter: "RichHelpFormatter"
    parent: RichSectionFormatter | None
    heading: str | None
    items: list[Callable[[], _RT | None]]

    def __init__(
        self,
        formatter: "RichHelpFormatter",
        parent: RichSectionFormatter | None = None,
        heading: str | None = None,
    ):
        self.formatter = formatter
        self.parent = parent
        self.heading = heading
        self.items = []
        if parent is None:
            self.level = 0
        else:
            self.level = 1 + parent.level

    @property
    def title(self) -> str | None:
        if self.heading is not SUPPRESS and self.heading is not None:
            return self.heading.title()
        return None

    def get_renderable_items(self) -> tuple[_RT, ...]:
        return tuple(
            x
            for x in (f() for f in self.items)
            if x is not None and x is not io.EMPTY
        )

    def format_rich(self) -> Group | None:
        items = self.get_renderable_items()

        if len(items) == 0:
            return None

        if self.parent is None:
            return Group(*items)

        if self.title is None or self.title == "":
            return Group(*items, io.NEWLINE)
        else:
            return Group(
                *io.header(self.title),
                *items,
                io.NEWLINE,
            )

    def format_help(self):
        # Note really sure what the story was here... guess it doesn't get
        # called?
        raise NotImplementedError("TODO..?!?")
        # return self.renderable
