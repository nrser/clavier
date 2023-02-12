import sys
from pathlib import Path
import json
from functools import total_ordering
from textwrap import dedent
from io import StringIO
from collections import UserList
from typing import Callable, Generic, TypeGuard, TypeVar, overload

from rich.console import (
    Console,
    ConsoleRenderable,
    RichCast,
    Group,
    RenderableType,
)
from rich.theme import Theme
from rich.pretty import Pretty
from rich.rule import Rule
from rich.text import Text, TextType
from rich.syntax import Syntax
from rich.style import Style as _S
from rich.panel import Panel
from rich.padding import Padding, PaddingDimensions
from rich.traceback import Traceback

from mdutils.mdutils import MdUtils

from . import etc, txt, cfg, err


TData = TypeVar("TData")


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
        "panel.error.title": _S(color="red", bold=True),
        "panel.error.context": _S(italic=True, dim=True),
        "panel.error.subtitle": _S(color="red", dim=True),
        "panel.error.border": _S(color="red"),
    }
)


OUT = Console(theme=THEME, file=sys.stdout)
ERR = Console(theme=THEME, file=sys.stderr)

EMPTY = Group()
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


def as_traceback(error: BaseException) -> Traceback:
    return Traceback.from_exception(
        type(error),
        error,
        error.__traceback__,
    )


@overload
def _as_error_panel_text(text: None, style_key: str) -> None:
    ...


@overload
def _as_error_panel_text(text: TextType, style_key: str) -> Text:
    ...


def _as_error_panel_text(text, style_key):
    if text is None or isinstance(text, Text):
        return text
    return Text(text, f"panel.error.{style_key}")


def error_panel(
    *renderables: RenderableType,
    margin: PaddingDimensions = (1, 0),
    padding: PaddingDimensions = (0, 1, 1, 1),
    title: TextType | None = None,
    subtitle: TextType | None = None,
    context: TextType | None = None,
) -> RenderableType:
    body = Grouper()

    if context is not None:
        body.append(_as_error_panel_text(context, "context"))
        body.append(NEWLINE)

    body.extend(renderables)

    panel = Panel(
        body.to_group(),
        title=_as_error_panel_text(title, "title"),
        subtitle=_as_error_panel_text(subtitle, "subtitle"),
        border_style="panel.error.border",
        padding=padding,
    )

    if (isinstance(margin, int) and margin != 0) or (
        isinstance(margin, tuple) and any(n != 0 for n in margin)
    ):
        return Padding(panel, margin)

    return panel


def header(text, level=1):
    yield Text(text, style="h")
    yield Rule(style="rule.h")
    # yield NEWLINE # removed -- tighten it up a bit, make usage look nicer


def code(code, lexer_name, code_width: int | None = 80, **opts):
    return Syntax(code, lexer_name, code_width=code_width, **opts)


def is_rich(x: object) -> TypeGuard[ConsoleRenderable | RichCast]:
    return isinstance(x, (ConsoleRenderable, RichCast))


def rel(path: Path, to: Path | None = None) -> Path:
    if to is None:
        to = cfg.current()[{(rel, "to"): Path}]
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


class Grouper(UserList):
    def to_group(self):
        return Group(*self.data)

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


class View(Generic[TData]):
    DEFAULT_FORMAT = "rich"

    @classmethod
    def formats(cls) -> list[ViewFormat]:
        def create(attr_name: str) -> ViewFormat:
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

    data: TData
    return_code: int
    out: Console
    err: Console

    def __init__(
        self,
        data: TData,
        *,
        return_code: int = 0,
        out: Console = OUT,
        err: Console = ERR,
    ):
        self.data = data
        self.return_code = return_code
        self.out = out
        self.err = err

    def print(self, *args, **kwds):
        self.out.print(*args, **kwds)

    def render(self, format: str = DEFAULT_FORMAT):
        method_name = f"render_{format}"
        method = getattr(self, method_name, None)

        if method is None:
            raise RuntimeError(
                f"format {format} not supported by view {self.__class__} "
                f"(method `{method_name}` does not exist)"
            )

        if not callable(method):
            raise err.InternalError(
                f"found attribute `{method_name}` on "
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
        render_to_console(self.data, console=self.out)


# class ErrorView(View):
#     def __init__(
#         self,
#         data,
#         *,
#         return_code: int = 1,
#         out: Console = OUT,
#         err: Console = ERR,
#     ):
#         super().__init__(data, return_code=return_code, out=out, err=err)


if __name__ == "__main__":
    import doctest

    doctest.testmod()
