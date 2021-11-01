from typing import *
import os
from os.path import isabs, basename
import subprocess
from pathlib import Path
import json
from shutil import rmtree
import shlex
from functools import wraps
import splatlog as logging

from .cfg import CFG
from .io import OUT, ERR, fmt, fmt_cmd

TOpts = Mapping[Any, Any]
TOptsStyle = Literal["=", " ", ""]
TOptsLongPrefix = Literal["--", "-"]
_TPath = Union[Path, str]


CONFIG = CFG.clavier.sh
LOG = logging.getLogger(__name__)
DEFAULT_OPTS_STYLE: TOptsStyle = "="
DEFAULT_OPTS_SORT = True

Result = subprocess.CompletedProcess


def render_path(path: Path, rel_to: Optional[Path]) -> str:
    if rel_to is None:
        return str(path)
    return str(path.relative_to(rel_to))


def _iter_opt(
    flag: str,
    value: Any,
    style: TOptsStyle,
    is_short: bool,
    rel_to: Optional[Path] = None,
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
    opts: TOpts,
    *,
    long_prefix: TOptsLongPrefix = CONFIG.opts.long_prefix,
    sort: bool = CONFIG.opts.sort,
    style: TOptsStyle = CONFIG.opts.style,
    rel_to: Optional[Path] = None,
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

    # Sort key/value pairs if needed
    items = sorted(opts.items()) if sort else list(opts.items())

    for name, value in items:
        name_s = str(name)
        is_short = len(name_s) == 1
        flag = f"-{name_s}" if is_short else f"{long_prefix}{name_s}"
        yield from _iter_opt(flag, value, style, is_short, rel_to)


def render_args(
    args: Iterable[Any],
    *,
    opts_long_prefix: TOptsLongPrefix = CONFIG.opts.long_prefix,
    opts_sort: bool = CONFIG.opts.sort,
    opts_style: TOptsStyle = CONFIG.opts.style,
    rel_to: Optional[Path] = None,
) -> Generator[Union[str, bytes], None, None]:
    """\
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
    *args,
    cwd: Optional[_TPath] = None,
    rel_paths: bool = CONFIG.rel_paths,
    **opts,
) -> List[str]:
    """\
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
    # Normalize str cwd path to Path
    if isinstance(cwd, str):
        cwd = Path(cwd)
    if rel_paths is True:
        rel_to = Path.cwd() if cwd is None else cwd
    else:
        rel_to = None
    return list(render_args(args, rel_to=rel_to, **opts))


def join(*args, **opts) -> str:
    """\
    Render `args` to a single string with `prepare` -> `shlex.join`. Returned
    string _should_ be suitable for pasting in a shell.

    ## Parameters ##

    Same as `prepare`.
    """
    return shlex.join(prepare(*args, **opts))


def prepare_wrap(fn: Callable) -> Callable:
    """\
    Decorator helper to run `prepare` and do a bit more common normalization
    for `get`, `run` etc.
    """

    @wraps(fn)
    def _prepare_wrapper(
        *args,
        cwd: Optional[_TPath] = None,
        encoding: Optional[str] = CONFIG.encoding,
        opts_long_prefix: TOptsLongPrefix = CONFIG.opts.long_prefix,
        opts_sort: bool = CONFIG.opts.sort,
        opts_style: TOptsStyle = CONFIG.opts.style,
        rel_paths: bool = CONFIG.rel_paths,
        **opts,
    ):
        # Normalize str cwd path to Path
        if isinstance(cwd, str):
            cwd = Path(cwd)
        cmd = prepare(
            *args,
            cwd=cwd,
            opts_long_prefix=opts_long_prefix,
            opts_sort=opts_sort,
            opts_style=opts_style,
            rel_paths=rel_paths,
        )
        return fn(*cmd, cwd=cwd, encoding=encoding, **opts)

    return _prepare_wrapper


# pylint: disable=redefined-builtin
@LOG.inject
@prepare_wrap
def get(
    *cmd,
    log=LOG,
    format: Optional[str] = None,
    **opts,
) -> Any:
    log.debug(
        "Getting system command output...",
        cmd=fmt_cmd(cmd),
        format=format,
        **opts,
    )

    # https://docs.python.org/3.8/library/subprocess.html#subprocess.check_output
    output = subprocess.check_output(cmd, **opts)

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
@prepare_wrap
def run(
    *cmd,
    log=LOG,
    check: bool = True,
    input: Union[None, str, bytes, Path] = None,
    **opts,
) -> subprocess.CompletedProcess:
    log.info(
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
        return subprocess.run(cmd, check=check, input=input, **opts)


@LOG.inject
def test(*args, **kwds) -> bool:
    """\
    Run a command and return whether or not it succeeds (has
    `subprocess.CompletedProcess.returncode` equal to `0`).

    >>> test("true", shell=True)
    True

    >>> test("false", shell=True)
    False
    """
    return run(*args, check=False, **kwds).returncode == 0


@LOG.inject
@prepare_wrap
def replace(
    *cmd,
    log=LOG,
    # Used, but defaulted in `prepare_cmd`, so needs to be accepted here
    encoding: Optional[str] = None,
    env: Optional[Mapping] = None,
    cwd: Optional[Union[str, Path]] = None,
) -> NoReturn:
    # https://docs.python.org/3.9/library/os.html#os.execl
    for console in (OUT, ERR):
        console.file.flush()
    proc_name = basename(cmd[0])
    log.debug(
        "Replacing current process with system command...",
        cmd=fmt_cmd(cmd),
        env=env,
        cwd=cwd,
    )
    if cwd is not None:
        os.chdir(cwd)
    if env is None:
        if isabs(cmd[0]):
            os.execv(cmd[0], cmd)
        else:
            os.execvp(proc_name, cmd)
    else:
        if isabs(cmd[0]):
            os.execve(cmd[0], cmd, env)
        else:
            os.execvpe(proc_name, cmd, env)


@LOG.inject
def file_absent(path: Path, name: Optional[str] = None, log=LOG):
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


@LOG.inject
def dir_present(path: Path, desc: Optional[str] = None, log=LOG):
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
