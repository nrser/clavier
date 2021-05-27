from typing import *
import os
from os.path import isabs, basename
import subprocess
from pathlib import Path
import json
from shutil import rmtree

from .io import OUT, ERR, fmt, fmt_cmd
from . import log as logging

TOpts = Mapping[Any, Any]
TOptsStyle = Literal["=", " "]
_TPath = Union[Path, str]

LOG = logging.getLogger(__name__)
DEFAULT_OPTS_STYLE: TOptsStyle = "="
DEFAULT_OPTS_SORT = True


@overload
def _path_for(path: _TPath, optional: bool = False) -> Path:
    pass


@overload
def _path_for(path: None, *, optional: Literal[True] = True) -> None:
    pass


@overload
def _path_for(path: _TPath, *, optional: Literal[True] = True) -> Path:
    pass


def _path_for(path, *, optional=False):
    if path is None:
        if optional is True:
            return None
        raise TypeError(
            "`path` may not be `None` unless `optional=True` is given"
        )
    if isinstance(path, Path):
        return path
    return Path(path)


def _transform_value(value, rel_to):
    if rel_to is None or not isinstance(value, Path):
        return value
    try:
        return str(value.relative_to(rel_to))
    except:
        return str(value)

def _iter_opt(
    flag: str,
    value: Any,
    style: TOptsStyle,
    is_short: bool,
    rel_to: Optional[Path] = None,
) -> Generator[str, None, None]:
    """Private helper for `iter_opts`."""

    value = _transform_value(value, rel_to)

    if value is None or value is False:
        # Special case #1 — value is `None` or `False`
        #
        # We omit these entirely.
        #
        pass
    elif value is True:
        # Special case #2 — value is `True`
        #
        # We emit the bare flag, like `-x` or `--blah`.
        #
        yield flag
    elif isinstance(value, (list, tuple)):
        # Special case #3 — value is a `list` or `tuple`
        #
        # We handle these by emitting the option multiples times, once for each
        # inner value.
        #
        for item in value:
            yield from _iter_opt(flag, item, style, is_short)
    elif is_short or style == " ":
        # General case #1 — space-separated
        #
        # _Short_ (single-character) flags and values are _always_ space-
        # sparated.
        #
        # _All_ flags and values are space-separated when the `style` is `" "`.
        #
        yield flag
        yield str(value)
    else:
        # General case #2 — flag=value format
        #
        # When no other branch has matched, we're left with `=`-separated flag
        # and value.
        #
        yield f"{flag}={value}"


def flat_opts(
    opts: TOpts,
    *,
    style: TOptsStyle = DEFAULT_OPTS_STYLE,
    sort: bool = DEFAULT_OPTS_SORT,
    rel_to: Optional[Path] = None,
) -> Generator[str, None, None]:
    """
    Examples:

    1.  Short opt with a list (or tuple) value:
        
        >>> list(flat_opts({'x': [1, 2, 3]}))
        ['-x', '1', '-x', '2', '-x', '3']

    2.  Long opt with a list (or tuple) value:

        >>> list(flat_opts({'blah': [1, 2, 3]}))
        ['--blah=1', '--blah=2', '--blah=3']

    3.  Due to the recursive, yield-centric nature, nested lists work as well:

            >>> list(flat_opts({'blah': [1, 2, [[3], 4], 5] }))
            ['--blah=1', '--blah=2', '--blah=3', '--blah=4', '--blah=5']

        Neat, huh?!

    Blah.
    """

    # Handle `None` as a legit value, making life easier on callers assembling
    # commands
    if opts is None:
        return

    # Sort key/value pairs if needed
    items = sorted(opts.items()) if sort else list(opts.items())

    for name, value in items:
        name_s = str(name)
        is_short = len(name_s) == 1
        flag = f"-{name_s}" if is_short else f"--{name_s}"
        yield from _iter_opt(flag, value, style, is_short, rel_to)


def flat_args(
    args,
    *,
    opts_style: TOptsStyle = DEFAULT_OPTS_STYLE,
    opts_sort: bool = DEFAULT_OPTS_SORT,
    rel_to: Optional[Path] = None,
):
    for arg in args:
        arg = _transform_value(arg, rel_to)
        if isinstance(arg, (str, bytes)):
            yield arg
        elif isinstance(arg, Mapping):
            yield from flat_opts(
                arg, style=opts_style, sort=opts_sort, rel_to=rel_to
            )
        elif isinstance(arg, Sequence):
            yield from flat_args(
                arg, opts_style=opts_style, opts_sort=opts_sort, rel_to=rel_to,
            )
        else:
            yield str(arg)


def flatten_args(args, **opts):
    return list(flat_args(args, **opts))


def prepare(
    args, *, chdir: Optional[_TPath] = None, rel_paths: bool = False, **opts
):
    if rel_paths is True:
        rel_to = Path.cwd() if chdir is None else Path(chdir)
    else:
        rel_to = None
    return list(flat_args(args, rel_to=rel_to, **opts))


# pylint: disable=redefined-builtin
def get(*args, chdir=None, format=None, encoding="utf-8", **opts) -> Any:
    log = LOG.getChild("get")

    if isinstance(chdir, Path):
        chdir = str(chdir)

    cmd = flatten_args(args)

    log.debug(
        "Getting system command output...",
        cmd=fmt_cmd(cmd),
        chdir=chdir,
        fmt=fmt,
        encoding=encoding,
        **opts,
    )
    # https://docs.python.org/3.8/library/subprocess.html#subprocess.run
    output = subprocess.check_output(cmd, encoding=encoding, cwd=chdir, **opts)

    if format is None:
        return output
    elif format == "strip":
        return output.strip()
    elif format == "json":
        return json.loads(output)
    else:
        log.warn("Unknown `format`", format=format, expected=[None, "json"])
        return output


@LOG.inject
def run(
    log,
    *args,
    chdir: Union[None, Path, str] = None,
    check: bool = True,
    encoding: str = "utf-8",
    input=None,
    opts_style: TOptsStyle = DEFAULT_OPTS_STYLE,
    opts_sort: bool = DEFAULT_OPTS_SORT,
    rel_paths: bool = False,
    **opts,
) -> None:
    cmd = prepare(
        args,
        opts_style=opts_style,
        opts_sort=opts_sort,
        chdir=chdir,
        rel_paths=rel_paths,
    )

    if isinstance(chdir, Path):
        chdir = str(chdir)

    if log is None:
        log = LOG.getChild("get")

    log.info(
        "Running system command...",
        cmd=fmt_cmd(cmd),
        chdir=chdir,
        encoding=encoding,
        **opts,
    )

    if isinstance(input, Path):
        with input.open("r", encoding="utf-8") as file:
            subprocess.run(
                cmd,
                check=check,
                cwd=chdir,
                encoding=encoding,
                input=file.read(),
                **opts,
            )
    else:
        subprocess.run(
            cmd, check=check, cwd=chdir, encoding=encoding, input=input, **opts
        )


def replace(
    exe: str,
    *args,
    env: Optional[Mapping] = None,
    chdir: Optional[Union[str, Path]] = None,
    opts_style: TOptsStyle = DEFAULT_OPTS_STYLE,
    opts_sort: bool = DEFAULT_OPTS_SORT,
) -> NoReturn:
    # https://docs.python.org/3.9/library/os.html#os.execl
    for console in (OUT, ERR):
        console.file.flush()
    proc_name = basename(exe)
    cmd = flatten_args((exe, *args), opts_style=opts_style, opts_sort=opts_sort)
    LOG.getChild("exec").debug(
        "Replacing current process with system command...",
        cmd=cmd,
        env=env,
        chdir=chdir,
    )
    if chdir is not None:
        os.chdir(chdir)
    if env is None:
        if isabs(exe):
            os.execv(exe, cmd)
        else:
            os.execvp(proc_name, cmd)
    else:
        if isabs(exe):
            os.execve(exe, cmd, env)
        else:
            os.execvpe(proc_name, cmd, env)


def file_absent(path: Path, name: Optional[str] = None):
    log = LOG.getChild("file_absent")
    if name is None:
        name = fmt(path)
    if path.exists():
        log.info(f"[holup]Removing {name}...[/holup]", path=path)
        if path.is_dir():
            rmtree(path)
        else:
            os.remove(path)
    else:
        log.info(f"[yeah]{name} already absent.[/yeah]", path=path)


def dir_present(path: Path, desc: Optional[str] = None):
    log = LOG.getChild("dir_present")
    if desc is None:
        desc = fmt(path)
    if path.exists():
        if path.is_dir():
            log.debug(
                f"[yeah]{desc} directory already exists.[/yeah]", path=path
            )
        else:
            raise RuntimeError(f"{path} exists and is NOT a directory")
    else:
        log.info(f"[holup]Creating {desc} directory...[/holup]", path=path)
        os.makedirs(path)


if __name__ == "__main__":
    import doctest

    doctest.testmod()
