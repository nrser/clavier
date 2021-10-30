from typing import *
import sys
from pathlib import Path
import json
from functools import total_ordering
from textwrap import dedent
from io import StringIO
from collections import UserList

from rich.console import Console, ConsoleRenderable, RichCast, RenderGroup
from rich.theme import Theme
from rich.pretty import Pretty
from rich.rule import Rule
from rich.text import Text
from rich.syntax import Syntax

from mdutils.mdutils import MdUtils

from .cfg import CFG
from . import etc, txt

THEME = Theme(
    {
        "good": "bold green",
        "yeah": "bold green",
        "on": "bold green",
        "bad": "bold red",
        "uhoh": "bold red",
        "holup": "bold yellow",
        "todo": "bold yellow",
        "h": "bold blue",
        "rule.h": "blue",
    }
)

OUT = Console(theme=THEME, file=sys.stdout)
ERR = Console(theme=THEME, file=sys.stderr)
EMPTY = RenderGroup()
NEWLINE = Text("\n", end="")

# def h1(text):
#     yield Text(text, style="h")
#     yield Rule(
#         # characters="=",
#         style="rule.h"
#     )
#     yield NEWLINE

# def h2(text):
#     yield Text(text, style="h")
#     yield Rule(
#         # characters="-",
#         style="rule.h"
#     )
#     yield NEWLINE


def header(text, level=1):
    yield Text(text, style="h")
    yield Rule(style="rule.h")
    yield NEWLINE


def code(code, lexer_name, code_width: Optional[int] = 80, **opts):
    return Syntax(code, lexer_name, code_width=code_width, **opts)


def is_rich(x: Any) -> bool:
    return isinstance(x, (ConsoleRenderable, RichCast))


# @cfg.inject_kwds
def rel(path: Path, to: Optional[Path] = None) -> Path:
    if to is None:
        to = CFG[rel, "to"]
    return path.relative_to(to)


def fmt_path(path: Path) -> str:
    # pylint: disable=bare-except
    try:
        return f"@/{rel(path)}"
    except:
        return str(path)


def fmt_cmd(cmd, *, code_width: int = 80, **opts):
    if isinstance(cmd, (list, tuple)):
        cmd = txt.fmt_cmd(cmd, code_width=code_width)
    return code(cmd, "shell", **opts)


def fmt(x):
    if isinstance(x, Path):
        return fmt_path(x)
    return str(x)


def render_to_console(data, console: Console = OUT):
    if data is None:
        pass
    elif isinstance(data, str) or is_rich(data):
        console.print(data)
    elif isinstance(data, list):
        for entry in data:
            render_to_console(entry, console=console)
    else:
        console.print(Pretty(data))


def render_to_string(data, **kwds) -> str:
    sio = StringIO()
    console = Console(file=sio, **kwds)
    render_to_console(data, console)
    return sio.getvalue()


def capture(*args, **kwds) -> str:
    """\
    Like `rich.console.Console.print`, but renders to a string.

    Yes, this is confusing because we already had `render_to_string`, which does
    something different -- I _think_ it's useful for intermediate renders that
    will eventually be given to `rich.console.Console.print`?

    Anyways, this behaves more like I'd expect it to as a user.
    """
    console = Console()
    with console.capture() as capture:
        console.print(*args, **kwds)
    return capture.get()


class RenderGrouper(UserList):
    def to_group(self):
        return RenderGroup(*self.data)

    def join(self, separator):
        return self.__class__(etc.interspersed(self.data, separator))


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


class View:
    DEFAULT_FORMAT = "rich"

    @classmethod
    def formats(cls):
        def create(attr_name):
            fn = getattr(cls, attr_name)
            name = attr_name.replace("render_", "")
            return ViewFormat(name, fn, cls.DEFAULT_FORMAT == name)

        return sorted(
            (
                create(attr)
                for attr in dir(cls)
                if (attr.startswith("render_") and callable(getattr(cls, attr)))
            )
        )

    @classmethod
    def help(cls):
        builder = MdUtils(file_name="")

        builder.new_paragraph(
            "How to print output. Commands can add their own custom output "
            "formats, but pretty much all commands should support `rich` and "
            "`json` outputs."
        )

        builder.new_list([format.list_item for format in cls.formats()])

        return builder.file_data_text

    def __init__(self, data, *, return_code: int = 0, console: Console = OUT):
        self.data = data
        self.return_code = return_code
        self.console = console

    def print(self, *args, **kwds):
        self.console.print(*args, **kwds)

    def render(self, format=DEFAULT_FORMAT):
        method_name = f"render_{format}"
        method = getattr(self, method_name)

        if method is None:
            raise RuntimeError(
                f"ViewFormat format {format} not supported by {self.__class__} "
                "view (method `{method_name}` does not exist)"
            )
        if not callable(method):
            raise RuntimeError(
                f"Internal error -- found attribute `{method_name}` on "
                f"{self.__class__} view, but it is not callable."
            )

        method()

    def render_json(self):
        """\
        Dumps the return value in JSON format.
        """
        self.print(json.dumps(self.data, indent=2))

    def render_rich(self):
        """\
        Pretty, colorful output for humans via the [rich][] Python package.

        [rich]: https://rich.readthedocs.io/en/stable/
        """
        render_to_console(self.data, console=self.console)


class ErrorView(View):
    def __init__(self, data, *, return_code: int = 1, console: Console = ERR):
        super().__init__(data, return_code=return_code, console=console)


if __name__ == "__main__":
    import doctest

    doctest.testmod()
