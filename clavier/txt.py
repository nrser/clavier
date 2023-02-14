"""\
I *hate* writing modules like this... but, I always seem to end up with one
after some amount of time.

They're never what I want, maybe because what I want is to not have to write
this kind of code. Doesn't everyone have to print shit out? Like, exceptions?

I also constantly debate if these modules are even worth existing, or if I
should add the same tedious crap at the site of every `raise` that someone
might have to read.

So... here it is. Once again.

This module prints things... as plain, markdown-ish strings. It doesn't depend
on anything outside the standard library, and should probably stay that way.

> ❗❗ WARNING ❗❗
>
> This module is used in already bad situations, like formatting error messages.
>
> As such, it must **_NOT_** depend on any other parts of the package, and
> it must **_NOT_** raise exceptions unless there is a logic error that needs
> to be fixed.
>
"""

from typing import Sequence, Callable, Any, Iterable, Union
import inspect
from pathlib import Path
import shlex
import os

import splatlog

from rich.console import Console
from rich.pretty import Pretty
from rich.padding import Padding

_CONSOLE = Console(
    file=open(os.devnull, "w"),
    force_terminal=False,
    width=80,
)

fmt = splatlog.lib.fmt
fmt_type_of = splatlog.lib.fmt_type_of


def fmt_pretty(obj: object) -> str:
    with _CONSOLE.capture() as capture:
        _CONSOLE.print(Padding(Pretty(obj), (0, 4)))
    return capture.get()


def tick(value) -> str:
    return f"`{value}`"


def fmt_class(cls) -> str:
    if cls.__module__ == "builtins":
        return tick(cls.__name__)
    return tick(f"{cls.__module__}.{cls.__name__}")


def fmt_path(path: Path) -> str:
    return tick(path)


def fmt_cmd(
    cmd: Iterable[str], *, code_width: int = 80, indent: Union[str, int] = "  "
):
    if isinstance(indent, int):
        indent = " " * indent
    lines = [""]
    for token in cmd:
        quoted = shlex.quote(token)
        if len(lines[-1]) + 1 + len(quoted) > code_width - 2:
            lines[-1] += " \\"
            lines.append(indent)
        if not lines[-1].isspace():
            lines[-1] += " "
        lines[-1] += quoted
    return "\n".join(lines)


def coordinate(
    seq: Sequence,
    conjunction: str,
    *,
    to_s: Callable[[Any], str] = fmt,
    sep: str = ",",
) -> str:
    """\
    Examples:

    1.  Empty list

        >>> fmt_list([])
        '[empty]'

    2.  List with a single item

        >>> fmt_list([1])
        '1'

    3.  List with two items

        >>> fmt_list([1, 2])
        '1 and 2'

    4.  List with more than two items

        >>> fmt_list([1, 2, 3])
        '1, 2 and 3'

    5.  Defaults to `repr` to cast to string

        >>> fmt_list(['a', 'b', 'c'])
        "'a', 'b' and 'c'"

    6.  Providing an alternative cast function

        >>> fmt_list(['a', 'b', 'c'], lambda x: f"`{x}`")
        '`a`, `b` and `c`'
    """
    length = len(seq)
    if length == 0:
        return "[empty]"
    if length == 1:
        return to_s(seq[0])
    return f" {conjunction} ".join(
        (f"{sep} ".join(map(to_s, seq[0:-1])), to_s(seq[-1]))
    )
