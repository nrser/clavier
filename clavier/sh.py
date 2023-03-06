from __future__ import annotations
import os
from os.path import isabs, basename
import subprocess
from pathlib import Path
import json
from shutil import rmtree
import shlex
from functools import wraps
from typing import (
    Any,
    Generator,
    Generic,
    Iterable,
    Literal,
    Mapping,
    NoReturn,
    ParamSpec,
    Protocol,
    TypeVar,
    cast,
)

import splatlog

from . import cfg, etc, err
from .io import OUT, ERR, fmt, fmt_cmd
from .etc.ins import accepts_kwd


_CFG = cfg.get_scope(__name__)

Opts = Mapping[Any, Any]
OptsStyle = Literal["=", " ", ""]
OptsLongPrefix = Literal["--", "-"]
_Path = Path | str

T = TypeVar("T")
V = TypeVar("V")
TOpts = TypeVar("TOpts", bound=dict[str, Any])
TOpts_contra = TypeVar("TOpts_contra", bound=dict[str, Any], contravariant=True)
TReturn = TypeVar("TReturn")
TReturn_co = TypeVar("TReturn_co", covariant=True)
TParams = ParamSpec("TParams")


class _ConfigValue(Generic[T]):
    key: cfg.Key[T]

    def __init__(self, *key_parts: cfg.KeyMatter, v_type: type[T]):
        self.key = cfg.Key(*key_parts, v_type=v_type)

    def get(self) -> T:
        return cfg.get(self.key)

    def resolve(self, value) -> T:
        if value is self:
            return self.get()
        return cast(T, value)


CfgKwd = T | _ConfigValue[T]

OPTS_LONG_PREFIX_DEFAULT = _ConfigValue[OptsLongPrefix](
    __name__, "opts.long_prefix", v_type=OptsLongPrefix
)

OPTS_SORT_DEFAULT = _ConfigValue[bool](__name__, "opts.sort", v_type=bool)

OPTS_STYLE_DEFAULT = _ConfigValue[OptsStyle](
    __name__, "opts.style", v_type=OptsStyle
)

REL_PATHS_DEFAULT = _ConfigValue[bool](__name__, "rel_paths", v_type=bool)


class InnerCommandFunction(Protocol[TOpts_contra, TReturn_co]):
    def __call__(
        self,
        cmd: list[bytes | str],
        cwd: Path | None = None,
        **opts: TOpts_contra,
    ) -> TReturn_co:
        ...


# Using a "callback protocol"
# https://stackoverflow.com/a/60667051
class CommandFunction(Protocol[TOpts_contra, TReturn_co]):
    def __call__(
        self,
        *args: object,
        cwd: _Path | None = None,
        opts_long_prefix: CfgKwd[OptsLongPrefix] = OPTS_LONG_PREFIX_DEFAULT,
        opts_sort: CfgKwd[bool] = OPTS_SORT_DEFAULT,
        opts_style: CfgKwd[OptsStyle] = OPTS_STYLE_DEFAULT,
        rel_paths: CfgKwd[bool] = REL_PATHS_DEFAULT,
        **opts: TOpts_contra,
    ) -> TReturn_co:
        ...


_LOG = splatlog.get_logger(__name__)


CompletedProcess = subprocess.CompletedProcess


def render_path(path: Path, rel_to: Path | None) -> str:
    if rel_to is None:
        return str(path)
    return str(etc.path.try_rel(path, rel_to))


def _iter_opt(
    flag: str,
    value: Any,
    style: OptsStyle,
    is_short: bool,
    rel_to: Path | None = None,
) -> Generator[str, None, None]:
    """Private helper for `iter_opts`."""

    if isinstance(value, Path):
        value = render_path(value, rel_to)

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
    elif style == " " or (is_short and style != ""):
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
        yield f"{flag}{style}{value}"


def render_opts(
    opts: Opts,
    *,
    long_prefix: CfgKwd[OptsLongPrefix] = OPTS_LONG_PREFIX_DEFAULT,
    sort: CfgKwd[bool] = OPTS_SORT_DEFAULT,
    style: CfgKwd[OptsStyle] = OPTS_STYLE_DEFAULT,
    rel_to: Path | None = None,
) -> Generator[str, None, None]:
    """
    Render a mapping of option names to values to a (yielded) sequence of
    strings.

    Examples:

    ### Style Examples ###

    1.  By default, `=` is used to separate "long options" and their values,
        while "short options" (single-character options) are always separate
        tokens from their values:

            >>> list(render_opts({"a": 1, "bee": 2}))
            ['-a', '1', '--bee=2']

    2.  Use space-separated option names and values:

            >>> list(render_opts({'blah': 1, 'meh': 2}, style=" "))
            ['--blah', '1', '--meh', '2']

    3.  Use a single `-` prefix on long options ("X toolkit" style):

            >>> list(render_opts({'blah': 1, 'meh': 2}, long_prefix='-'))
            ['-blah=1', '-meh=2']

    4.  Use that weird "no-separator" style you sometimes see:

            >>> list(render_opts({'x': 123, 'y': 456}, style=""))
            ['-x123', '-y456']

    ### List Value Examples ###

    1.  Short opt with a list (or tuple) value:

        >>> list(render_opts({'x': [1, 2, 3]}))
        ['-x', '1', '-x', '2', '-x', '3']

    2.  Long opt with a list (or tuple) value:

        >>> list(render_opts({'blah': [1, 2, 3]}))
        ['--blah=1', '--blah=2', '--blah=3']

    3.  Due to the recursive, yield-centric nature, nested lists work as well:

            >>> list(render_opts({'blah': [1, 2, [[3], 4], 5]}))
            ['--blah=1', '--blah=2', '--blah=3', '--blah=4', '--blah=5']

        Neat, huh?!

    ### Relative Path Examples ###

    1.  As with positional arguments, `pathlib.Path` option values can be
        rendered relative to a `rel_to` directory. Only paths that are
        descendants of `rel_to` will be relativized (no `../` transformations).

            >>> list(
            ...     render_opts(
            ...         {
            ...             'input': Path("/tmp/blah.json"),
            ...             'output': Path("/dev/null"),
            ...         },
            ...         rel_to=Path("/tmp")
            ...     )
            ... )
            ['--input=blah.json', '--output=/dev/null']
    """

    # Handle `None` as a legit value, making life easier on callers assembling
    # commands
    if opts is None:
        return

    _style = OPTS_STYLE_DEFAULT.resolve(style)
    _long_prefix = OPTS_LONG_PREFIX_DEFAULT.resolve(long_prefix)
    _sort = OPTS_SORT_DEFAULT.resolve(sort)

    # Sort key/value pairs if needed
    items = sorted(opts.items()) if _sort else list(opts.items())

    for name, value in items:
        name_s = str(name)
        is_short = len(name_s) == 1
        flag = f"-{name_s}" if is_short else f"{_long_prefix}{name_s}"
        yield from _iter_opt(flag, value, _style, is_short, rel_to)


def render_args(
    args: Iterable[object],
    *,
    opts_long_prefix: CfgKwd[OptsLongPrefix] = OPTS_LONG_PREFIX_DEFAULT,
    opts_sort: CfgKwd[bool] = OPTS_SORT_DEFAULT,
    opts_style: CfgKwd[OptsStyle] = OPTS_STYLE_DEFAULT,
    rel_to: Path | None = None,
) -> Generator[str | bytes, None, None]:
    """
    Render `args` to sequence of `str` (and/or `bytes`, if any values passed in
    are `bytes`).

    `args` entries are handled by type:

    1.  `str` and `bytes` -- passed through.
    2.  `pathlib.Path` -- passed (along with `rel_to`) through `render_path`.
    3.  `typing.Mapping` -- understood as options, passed through `render_opts`.
    4.  `typing.Iterable` -- recurred into.
    5.  Other -- converted to a string with `str()`.
    """

    for arg in args:
        if isinstance(arg, (str, bytes)):
            yield arg
        elif isinstance(arg, Path):
            yield render_path(arg, rel_to)
        elif isinstance(arg, Mapping):
            yield from render_opts(
                arg,
                long_prefix=opts_long_prefix,
                style=opts_style,
                sort=opts_sort,
                rel_to=rel_to,
            )
        elif isinstance(arg, Iterable):
            yield from render_args(
                arg,
                opts_long_prefix=opts_long_prefix,
                opts_style=opts_style,
                opts_sort=opts_sort,
                rel_to=rel_to,
            )
        else:
            yield str(arg)


def prepare(
    *args: object,
    cwd: _Path | None = None,
    rel_paths: CfgKwd[bool] = REL_PATHS_DEFAULT,
    opts_long_prefix: CfgKwd[OptsLongPrefix] = OPTS_LONG_PREFIX_DEFAULT,
    opts_sort: CfgKwd[bool] = OPTS_SORT_DEFAULT,
    opts_style: CfgKwd[OptsStyle] = OPTS_STYLE_DEFAULT,
) -> list[str | bytes]:
    """
    Prepare `args` to be passed `subprocess.run` or similar functions.

    Contextualizes the relative path capabilities of `render_args` and
    `render_opts` to the working directory, which can either be provided as
    `cwd` or assumed to be the current directory.

    Relative path conversion is controlled by the `rel_paths` flag.

    ## Examples ##

    >>> prepare(
    ...     "kubectl",
    ...     {"namespace": "blah"},
    ...     "logs",
    ...     {"follow": True},
    ...     "some-pod",
    ... )
    ['kubectl', '--namespace=blah', 'logs', '--follow', 'some-pod']

    """
    _rel_paths = REL_PATHS_DEFAULT.resolve(rel_paths)

    # Normalize str cwd path to Path
    if isinstance(cwd, str):
        cwd = Path(cwd)
    if _rel_paths is True:
        rel_to = Path.cwd() if cwd is None else cwd
    else:
        rel_to = None
    return list(
        render_args(
            args,
            rel_to=rel_to,
            opts_long_prefix=opts_long_prefix,
            opts_sort=opts_sort,
            opts_style=opts_style,
        )
    )


def command_function(
    fn: InnerCommandFunction[TOpts, TReturn],
) -> CommandFunction[TOpts, TReturn]:
    """
    Decorator helper to run `prepare` and do a bit more common normalization
    for `get`, `run` etc.
    """

    # Does the wrapped function accept an `encoding` keyword?
    accepts_encoding = accepts_kwd(fn, "encoding")

    @wraps(fn)
    def wrapper(
        *args: object,
        cwd: _Path | None = None,
        opts_long_prefix: CfgKwd[OptsLongPrefix] = OPTS_LONG_PREFIX_DEFAULT,
        opts_sort: CfgKwd[bool] = OPTS_SORT_DEFAULT,
        opts_style: CfgKwd[OptsStyle] = OPTS_STYLE_DEFAULT,
        rel_paths: CfgKwd[bool] = REL_PATHS_DEFAULT,
        **opts,
    ):
        # Normalize str cwd path to Path
        if isinstance(cwd, str):
            cwd = Path(cwd)

        # If the wrapped function accepts an `encoding` keyword and there
        # isn't one in `opts` then default it from the `CONFIG`
        if accepts_encoding and "encoding" not in opts:
            opts["encoding"] = _CFG[{"encoding": str}]

        cmd = prepare(
            *args,
            cwd=cwd,
            opts_long_prefix=opts_long_prefix,
            opts_sort=opts_sort,
            opts_style=opts_style,
            rel_paths=rel_paths,
        )

        return fn(cmd, cwd=cwd, **opts)

    return wrapper


def join(*args, **opts) -> str:
    """
    Render `args` to a single string with `prepare` -> `shlex.join`. Returned
    string _should_ be suitable for pasting in a shell.

    ## Parameters ##

    Same as `prepare`.
    """
    return shlex.join((str(arg) for arg in prepare(*args, **opts)))


@command_function
def get(
    cmd: list[bytes | str],
    cwd: Path | None = None,
    format: str | None = None,
    **opts,
) -> Any:
    _LOG.debug(
        "Getting system command output...",
        cmd=fmt_cmd(cmd),
        cwd=cwd,
        format=format,
        **opts,
    )

    # https://docs.python.org/3.8/library/subprocess.html#subprocess.check_output
    output = subprocess.check_output(cmd, cwd=cwd, **opts)

    if format is None:
        return output
    elif format == "strip":
        return output.strip()
    elif format == "json":
        return json.loads(output)
    else:
        _LOG.warning(
            "Unknown `format`", format=format, expected=[None, "strip", "json"]
        )
        return output


@command_function
def run(
    cmd: list[bytes | str],
    cwd: Path | None = None,
    check: bool = True,
    input: str | bytes | Path | None = None,
    **opts,
) -> CompletedProcess:
    _LOG.info(
        "Running system command...",
        cmd=fmt_cmd(cmd),
        **opts,
    )

    # https://docs.python.org/3.8/library/subprocess.html#subprocess.run
    if isinstance(input, Path):
        with input.open("r", encoding="utf-8") as file:
            return subprocess.run(
                cmd,
                check=check,
                input=file.read(),
                **opts,
            )
    else:
        return subprocess.run(cmd, cwd=cwd, check=check, input=input, **opts)


def test(*args, **kwds) -> bool:
    """
    Run a command and return whether or not it succeeds (has
    `subprocess.CompletedProcess.returncode` equal to `0`).

    >>> test("true", shell=True)
    True

    >>> test("false", shell=True)
    False
    """
    return run(*args, check=False, **kwds).returncode == 0


@command_function
def replace(
    cmd: list[bytes | str],
    cwd: Path | None = None,
    env: Mapping | None = None,
    **opts,  # Unused
) -> NoReturn:
    """Replace the current process with a new command.

    This uses the "exec" family of functions under-the-hood: `os.execv`,
    `os.execvp` and `os.execvpe`. All of Clavier is "Unix-only", but it may be
    worth noting that this functionality is specific to Unix.

    In the case that the app is running in server process (`clavier.srv`), this
    command will
    """

    # https://docs.python.org/3.9/library/os.html#os.execl
    for console in (OUT, ERR):
        console.file.flush()

    if len(cmd) == 0:
        raise ValueError("`cmd` can not be empty; ")

    # TODO  Arg must be string, this is prob not the right thing to do...
    proc_name = basename(str(cmd[0]))

    _LOG.debug(
        "Replacing current process with system command...",
        cmd=fmt_cmd(cmd),
        env=env,
        cwd=cwd,
    )

    program, *args = cmd
    raise err.ReplaceProcess(
        program=str(program),
        args=[str(arg) for arg in args],
        cwd=None if cwd is None else str(cwd),
        env=None if env is None else {str(k): str(v) for k, v in env.items()},
    )

    # if cwd is not None:
    #     os.chdir(cwd)

    # if env is None:
    #     if isabs(cmd[0]):
    #         os.execv(cmd[0], cmd)
    #     else:
    #         os.execvp(proc_name, cmd)
    # else:
    #     if isabs(cmd[0]):
    #         os.execve(cmd[0], cmd, env)
    #     else:
    #         os.execvpe(proc_name, cmd, env)


def file_absent(path: Path, name: str | None = None):
    if name is None:
        name = fmt(path)
    if path.exists():
        _LOG.info(f"[holup]Removing {name}...[/holup]", path=path)
        if path.is_dir():
            rmtree(path)
        else:
            os.remove(path)
    else:
        _LOG.info(f"[yeah]{name} already absent.[/yeah]", path=path)


def dir_present(path: Path, desc: str | None = None):
    if desc is None:
        desc = fmt(path)
    if path.exists():
        if path.is_dir():
            _LOG.debug(
                f"[yeah]{desc} directory already exists.[/yeah]", path=path
            )
        else:
            raise RuntimeError(f"{path} exists and is NOT a directory")
    else:
        _LOG.info(f"[holup]Creating {desc} directory...[/holup]", path=path)
        os.makedirs(path)
