from functools import total_ordering
from textwrap import dedent
from typing import Callable


@total_ordering
class ViewFormat:
    name: str
    fn: Callable
    is_default: bool

    def __init__(self, name, fn, is_default):
        self.name = name
        self.fn = fn
        self.is_default = is_default

    def __lt__(self, other):
        if self.is_default is other.is_default:
            # Either both are or are not (!?!) defaults, so sort by `name`
            return self.name < other.name
        # Defaults come _first_, so they're _least_
        return self.is_default

    def __eq__(self, other):
        if not isinstance(other, self.__class__):
            return False
        return (
            self.fn == other.fn
            and self.name == other.name
            and self.is_default == other.is_default
        )

    @property
    def help(self):
        if doc := self.fn.__doc__:
            return dedent(doc.strip())
        return "(undocumented)"

    @property
    def list_item(self):
        title = f"`{self.name}`"
        if self.is_default:
            title += " (default)"
        return title + " -- " + self.help
