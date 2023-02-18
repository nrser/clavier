from io import StringIO
from typing import Generator, Iterable, TypeGuard, TypeVar
from pathlib import Path
from pathlib import Path
from collections import UserList
from typing import overload

from more_itertools import intersperse
from rich.console import (
    Console,
    Group,
    RenderableType,
    ConsoleRenderable,
    RichCast,
)
from rich.rule import Rule
from rich.text import Text, TextType
from rich.syntax import Syntax
from rich.panel import Panel
from rich.padding import Padding, PaddingDimensions
from rich.traceback import Traceback
from rich.pretty import Pretty

from clavier import cfg, etc

from .io_consts import OUT, NEWLINE


def is_rich(x: object) -> TypeGuard[ConsoleRenderable | RichCast]:
    return isinstance(x, (ConsoleRenderable, RichCast))


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
        return Padding(panel, pad=margin)

    return panel


def header(text, level=1):
    yield Text(text, style="h")
    yield Rule(style="rule.h")
    # yield NEWLINE # removed -- tighten it up a bit, make usage look nicer


def code(code, lexer_name, code_width: int | None = 80, **opts):
    return Syntax(code, lexer_name, code_width=code_width, **opts)


def rel(path: Path, to: Path | None = None) -> Path:
    if to is None:
        to = cfg.current[{(rel, "to"): Path}]
    return path.relative_to(to)


def fmt_path(path: Path) -> str:
    # pylint: disable=bare-except
    try:
        return f"@/{rel(path)}"
    except:
        return str(path)


def fmt_cmd(cmd, *, code_width: int = 80, **opts):
    if isinstance(cmd, (list, tuple)):
        cmd = etc.txt.fmt_cmd(cmd, code_width=code_width)
    return code(cmd, "shell", **opts)


def fmt(x):
    if isinstance(x, Path):
        return fmt_path(x)
    return str(x)


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


TGrouper = TypeVar("TGrouper", bound="Grouper")


class Grouper(UserList[RenderableType | None]):
    """Builder `rich.console.Group` instances with an object that acts like a
    `list` (via `collections.UserList`).

    Allows adding of `None` entries, which are filtered out when converted
    `to_group`. Also see `renderables` and `compact`.
    """

    @overload
    def __init__(self, iterable: Iterable[RenderableType | None], /):
        ...

    @overload
    def __init__(self, *iterable: RenderableType | None):
        ...

    def __init__(self, *args):
        iterable: Iterable[RenderableType | None] | None

        match args:
            case ():
                iterable = None

            case (arg_0,) if isinstance(arg_0, RenderableType):
                iterable = args

            case (arg_0,) if isinstance(arg_0, Iterable):
                iterable = arg_0

            case _:
                iterable = args

        super().__init__(iterable)

    def to_group(self):
        """Build a `rich.console.Group` and return it.

        ##### Examples #####

        ```python
        >>> Grouper("hey", "ho").to_group()
        <rich.console.Group object at ...>

        ```
        """
        return Group(*(r for r in self.renderables()))

    def renderables(self) -> Generator[RenderableType, None, None]:
        """Yield each of the renderable entries (each entry that is not `None`).

        ##### Examples #####

        ```python
        >>> list(Grouper(None, "hey", None, "ho").renderables())
        ['hey', 'ho']

        ```
        """
        for entry in self.data:
            if entry is not None:
                yield entry

    def renderable_count(self) -> int:
        """Count how many renderables are in the `Grouper` (how many entries
        are not `None`).

        ##### Examples #####

        ```python
        >>> Grouper("hey", None, "ho").renderable_count()
        2

        ```

        """
        return sum(1 for entry in self.data if entry is not None)

    def __bool__(self) -> bool:
        """The boolean-ness of `Grouper` depends on how many _renderables_ it
        has in it (`None` entries are not counted towards "truthy-ness").

        ##### Examples #####

        ```python
        >>> bool(Grouper())
        False

        >>> bool(Grouper(None, None, None))
        False

        >>> bool(Grouper(None, "hey", None))
        True

        ```
        """
        return any(entry is not None for entry in self.data)

    def compact(self) -> None:
        """**Mutate** the builder by removing all `None` entries."""
        for index, entry in enumerate(self.data):
            if entry is None:
                self.data.pop(index)

    def join(self: TGrouper, separator: RenderableType) -> TGrouper:
        """
        ##### Examples #####

        ```python
        >>> Grouper("a", None, "b", "c", None).join("and")
        ['a', 'and', 'b', 'and', 'c']

        ```
        """
        return self.__class__(intersperse(separator, self.renderables()))
