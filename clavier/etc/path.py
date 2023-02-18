import os
from pathlib import Path
from typing import AnyStr

from . import err

#: The things you can use as paths, in the general sense.
#:
#: Using same name and definition as PyLance, which looks like it comes from
#: [typeshed][]?
#:
#: Of course, it's worth noting that `pathlib.Path` satisfies `os.PathLike`, so
#: it fits in here.
#:
#: [typeshed]: https://github.com/python/typeshed
#:
StrPath = str | os.PathLike[AnyStr]


def as_path(p: StrPath) -> Path:
    match p:
        case Path():
            return p
        case str(s):
            return Path(s)
        case os.PathLike() as pl:
            return Path(os.fspath(pl))
        case wtf:
            raise err.ArgTypeError(
                name="p",
                expected_type=(Path | str | os.PathLike),
                value=p,
            )


#: A shortcut to `as_path`.
as_p = as_path


def is_rel(path: StrPath, to: StrPath | None = None) -> bool:
    """Is `path` relative to `to`?

    If `to` is `None` then `pathlib.Path.cwd` is used in its place.
    """

    path_p = as_p(path)

    try:
        path_p.relative_to(to if to else Path.cwd())
    except ValueError:
        return False
    return True


def try_rel(path: StrPath, to: StrPath | None = None) -> Path:
    """Try to relativize `path` against `to`, returning a `pathlib.Path` version
    of `path` if it is not relative to `to`.

    If `to` is `None` then `pathlib.Path.cwd` is used in its place.
    """

    path_p = as_p(path)

    try:
        return path_p.relative_to(to if to else Path.cwd())
    except ValueError:
        return path_p
