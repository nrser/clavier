"""I *hate* writing modules like this... but, I always seem to end up with one
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
> As such, it must **_NOT_** depend on any parts of the package outside
> `clavier.etc`, and it must **_NOT_** raise exceptions unless there is a logic
> error that needs to be fixed.
>
"""

from typing import Callable, Any, Iterable, Union
from pathlib import Path
import shlex
import os
import re

import splatlog.lib.text
from splatlog.lib.text import (
    FmtOpts,
    fmt as splat_fmt,
)

from rich.console import Console
from rich.pretty import Pretty
from rich.padding import Padding

from more_itertools import intersperse, collapse

from .iter import append

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


def tick(value) -> str:
    return "`" + str(value) + "`"


def fmt_pretty(obj: object) -> str:
    with _CONSOLE.capture() as capture:
        _CONSOLE.print(Padding(Pretty(obj), (0, 4)))
    return capture.get()


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


@FmtOpts.provide
def fmt(x: Any, opts: FmtOpts[str]) -> str:
    match x:
        case str(s):
            return s
        case Path() as path:
            return fmt_path(path)
        case other:
            return splat_fmt(other)


def join(
    *iterable: Any,
    seperator: str = ", ",
    coordinator: str | None = " and ",
    to_s: Callable[[Any], str] = fmt,
    oxford: bool = False,
    empty: str = "",
) -> str:
    """
    Joins items into a textual list suitable for prose, including a
    [coordinating conjunction][] between the last two items (_penultimate_ and
    _ultimate_), should there be two or more.

    [coordinating conjunction]: https://en.wikipedia.org/wiki/Conjunction_(grammar)#Coordinating_conjunctions

    Hilariously, this function _is not even used_ at this time, but I wrote it
    at some point, and fixed it at another, and wished it was there more times
    than I'd like to admit, so here it is, may it be remembered and used.

    ##### Examples #####

    1.  Common use case.

        ```python
        >>> join("a", "b", "c")
        'a, b and c'

        ```

    2.  `iterable` is processed with `more_itertools.collapse`, allowing
        nesting.

        ```python
        >>> join("a", ("b", "c"), (c for c in "def"))
        'a, b, c, d, e and f'

        ```

    3.  Switch the [coordinating conjunction][]. Note that you need to add
        spaces around it if you want to have spaces around it in the output.

        ```python
        >>> join("a", "b", "c", coordinator=" or ")
        'a, b or c'

        ```

        You can omit the penultimate/ultimate coordinator as well

        ```python
        >>> join("a", "b", "c", coordinator=None)
        'a, b, c'

        ```

    4.  Switch the seperator. Note that you need to add a trailing space if you
        want them to be there in the output.

        ```python
        >>> join("a", "b", "c", "d", seperator="、 ")
        'a、 b、 c and d'

        ```

    5.  Use an "oxford"-style seperator before the coordinating conjunction (
        techincally, this is called the [serial comma][] but I'll never
        remember that).

        ```python
        >>> join("a", "b", "c", oxford=True)
        'a, b, and c'

        ```

        [serial comma]: https://en.wikipedia.org/wiki/Serial_comma

    6.  Change the `to_s` function that converts item to strings (default is
        `fmt`).

        ```python
        >>> join("a", "b", "c", to_s=repr)
        "'a', 'b' and 'c'"

        ```

    7.  Empty list return the `empty` argument, which defaults to the empty
        string.

        ```python
        >>> empty_list = []

        >>> join(empty_list)
        ''

        >>> join(empty_list, empty="(none)")
        '(none)'

        ```

    8.  List with a single item just applies `to_s` to it.

        ```python
        >>> join(1)
        '1'

        ```

    9.  List with just two items joins them with the `coordinator`.

        ```python
        >>> join(1, 2)
        '1 and 2'

        ```
    """
    if coordinator is None:
        return seperator.join(to_s(i) for i in collapse(iterable))

    items = list(collapse(iterable))

    match items:
        case []:
            return empty
        case [only]:
            return to_s(only)
        case [penult, utl]:
            return to_s(penult) + coordinator + to_s(utl)
        case [*rest, penult, utl]:
            return seperator.join(
                append(
                    (to_s(i) for i in rest),
                    to_s(penult)
                    + (seperator if oxford else "")
                    + coordinator
                    + to_s(utl),
                )
            )
    assert False, "unreachable"
