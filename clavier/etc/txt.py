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
from pathlib import Path
import shlex
import os
import re

import splatlog.lib.text

from rich.console import Console
from rich.pretty import Pretty
from rich.padding import Padding

_CONSOLE = Console(
    file=open(os.devnull, "w"),
    force_terminal=False,
    width=80,
)

fmt = splatlog.lib.text.fmt
fmt_type_of = splatlog.lib.text.fmt_type_of


_SQUISH_RE = re.compile(r"\s+")


def squish(string: str) -> str:
    """
    Like the ol' Rails method, condense any whitespace runs into a single space
    and strip any leading and trailing whitespace.

    Basically, useful for normalizing shell-command-like strings that are
    written out in multiple lines.

    Doesn't have any sense of "literal whitespace" inside the `string`, so you
    can't really use it if you need to preserve whitespace in values or
    whatever.

    ##### Examples #####

    ```python

    >>> squish('''
    ...     appsrc
    ...        emit-signals=true
    ...        is-live=true
    ...    ! videoscale
    ... ''')
    'appsrc emit-signals=true is-live=true ! videoscale'

    ```
    """

    return _SQUISH_RE.sub(" ", string).strip()


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


def conjoin(
    seq: Sequence,
    conjunction: str,
    *,
    to_s: Callable[[Any], str] = fmt,
    sep: str = ",",
) -> str:
    """
    ##### Examples #####

    1.  Empty list

        ```python
        >>> conjoin([], "and")
        '[empty]'

        ```

    2.  List with a single item

        ```python
        >>> conjoin([1], "and")
        '1'

        ```

    3.  List with two items

        ```python
        >>> conjoin([1, 2], "and")
        '1 and 2'

        ```

    4.  List with more than two items

        ```python
        >>> conjoin([1, 2, 3], "and")
        '1, 2 and 3'

        ```

    5.  Defaults to `repr` to cast to string

        ```python
        >>> conjoin(['a', 'b', 'c'], "and")
        "'a', 'b' and 'c'"

        ```

    6.  Providing an alternative cast function

        ```python
        >>> conjoin(['a', 'b', 'c'], "and", to_s=lambda x: f"`{x}`")
        '`a`, `b` and `c`'

        ```
    """
    length = len(seq)
    if length == 0:
        return "[empty]"
    if length == 1:
        return to_s(seq[0])
    return f" {conjunction} ".join(
        (f"{sep} ".join(map(to_s, seq[0:-1])), to_s(seq[-1]))
    )
