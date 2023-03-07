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

from functools import reduce
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

#: The character used to separate _identifiers_ in a
IDENTIFIER_SEPERATOR = "."

#: Patterns and replacements used in `as_snake_case`. They are applied in-order.
_SNAKE_CASE_SUBS = (
    # Adapted from
    #
    # https://stackoverflow.com/a/1176023
    #
    # Added annotations and adaptation descriptions.
    #
    # This generally matched the start of camel-case words, except at the
    # begining of the string. Modified to _not_ insert that underscore if the
    # previous character is '.' or '_'.
    (re.compile(r"([^\._])([A-Z][a-z]+)"), r"\1_\2"),
    # This cleans up multi-underscore runs that happen before a cammel word
    # start?
    (re.compile(r"__([A-Z])"), r"_\1"),
    # This is kinda the reverse of the first one, probably needed due to
    # non-overlapping behavior of `re.sub`?
    (re.compile(r"([a-z0-9])([A-Z])"), r"\1_\2"),
    # Our addition — convert '-' runs to a single '_'
    (re.compile(r"(\-+)"), "_"),
)

_ENV_NAME_SUBS = (
    # Trim anything we can't use from the start (don't create leading '_')
    (re.compile(r"^[^A-Za-z0-9_]+"), ""),
    # Trim anything we can't use from the end (don't create trailing '_')
    (re.compile(r"[^A-Za-z0-9_]+$"), ""),
    # Replace any runs we can't use with a single '_'
    (re.compile(r"[^A-Za-z0-9_]+"), "_"),
)


def as_snake_case(name: str) -> str:
    """Convert a `str` to "snake-case" — lower-case, underscore-separated. The
    general form for Python function and variable names.

    > 📝 NOTE
    >
    > To some extent this operation is not well-defined, and in some cases it
    > requires grammatical understanding of the `name` content to "get it
    > right".
    >
    > This (partial) solution seems about as good-as-it-gets for a simple
    > implementation (it's a few lines, stdlib).
    >
    > Adapted from a response to a Stack Overflow question (multiple authors),
    > see
    >
    > https://stackoverflow.com/a/1176023

    ##### 🏗 Examples #####

    1.  From "cammel-case".

        ```python
        >>> as_snake_case("MyCoolClass")
        'my_cool_class'

        >>> as_snake_case("getHTTPRequest")
        'get_http_request'

        >>> as_snake_case("ILikeCats")
        'i_like_cats'

        ```

    2.  From "kebab-case".

        ```python
        >>> as_snake_case("more-itertools")
        'more_itertools'

        ```

    3.  If `name` is already snake-case it should not be modified.

        ```python
        >>> as_snake_case("_already_snake")
        '_already_snake'

        ```

    4.  Besides "-", other punctuation is kept in place. In particular, the
        `IDENTIFIER_SEPARATOR` "." carries through.

        ```python
        >>> as_snake_case("clavier.arg_par.ArgumentParser")
        'clavier.arg_par.argument_parser'

        ```

        If you need something that can be used as an _identifier_ check out
        `as_identifier`.
    """
    return reduce(
        lambda name, sub: sub[0].sub(sub[1], name), _SNAKE_CASE_SUBS, name
    ).lower()


def as_kebab_case(
    name: str,
    *,
    allow_leading_dash: bool = False,
    allow_trailing_dash: bool = False,
) -> str:
    """
    ##### Examples #####

    ```python
    >>> as_kebab_case("cat_sprayer")
    'cat-sprayer'

    >>> as_kebab_case("_my_name")
    'my-name'

    ```
    """

    kebabbed = as_snake_case(name).replace("_", "-")
    if not allow_leading_dash:
        kebabbed = kebabbed.lstrip("-")
    if not allow_trailing_dash:
        kebabbed = kebabbed.rstrip("-")
    return kebabbed


def is_identifier_path(name: str) -> bool:
    """Return `True` if `name` contains a sequence of _identifiers_ (per
    `str.isidentifier`) seperator by the `IDENTIFIER_SEPERATOR` ".", as used in
    Python module names.

    ##### 🏗 Examples #####

    1.  You know what these generally look like. Each segment needs to be a
        legal variable name.

        ```python
        >>> is_identifier_path("clavier.etc.txt")
        True

        >>> is_identifier_path("more-itertools")
        False

        ```

    2.  The special "dunder" string attributes `__name__`, `__module__`,
        `__package__`, etc. should always be _identifier paths_.

        ```python
        >>> is_identifier_path(__name__)
        True

        >>> is_identifier_path(is_identifier_path.__module__)
        True

        >>> is_identifier_path(__package__)
        True

        ```
    """
    return all(id.isidentifier() for id in name.split(IDENTIFIER_SEPERATOR))


def as_identifier(name: str) -> str:
    id = as_snake_case(name).replace(".", "_")
    if not id.isidentifier():
        raise ValueError(f"can't convert to identifier: {name!r}")
    return id


def as_env_name(name: str) -> str:
    """
    ##### Examples #####

    ```python
    >>> as_env_name("clavier.etc.txt")
    'CLAVIER_ETC_TXT'

    >>> as_env_name("[[a/b/c?]]")
    'A_B_C'

    >>> as_env_name("_CLAVIER_INTERNAL")
    '_CLAVIER_INTERNAL'

    >>> as_env_name("?^%!$@%^$!")
    Traceback (most recent call last):
        ...
    ValueError: no usable characters in `name`;
        converted '?^%!$@%^$!' -> ''

    >>> as_env_name("?^%!$___@%^$!")
    Traceback (most recent call last):
        ...
    ValueError: no usable characters in `name`;
        converted '?^%!$___@%^$!' -> '___'

    ```
    """
    env_name = reduce(
        lambda name, sub: sub[0].sub(sub[1], name), _ENV_NAME_SUBS, name
    ).upper()

    if env_name == "" or set(env_name) == {"_"}:
        raise ValueError(
            "no usable characters in `name`; "
            f"converted {name!r} -> {env_name!r}"
        )

    return env_name


def squish(string: str) -> str:
    """
    Like the ol' Rails method, condense any whitespace runs into a single space
    and strip any leading and trailing whitespace.

    Basically, useful for normalizing shell-command-like strings that are
    written out in multiple lines.

    Doesn't have any sense of "literal whitespace" inside the `string`, so you
    can't really use it if you need to preserve whitespace in values or
    whatever.

    ##### 🏗 Examples #####

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

    ##### 🏗 Examples #####

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
