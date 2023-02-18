import os
from pathlib import Path
from subprocess import run
import sys
import shutil
from typing import Callable, Sequence
from more_itertools import always_iterable

from clavier import Sesh, cmd, sh

CLAVIER_PKG_ROOT = Path(__file__).parents[2]
ENTRYPOINT_PKG_ROOT = CLAVIER_PKG_ROOT / "entrypoint"
ENTRYPOINT_PKG_NAME = "clavier-srv-entrypoint"


def default_python_exe() -> Path:
    # return str(Path(sys.executable).resolve())
    return Path(sys.executable)


def default_python_path() -> list[Path]:
    return [Path(e) for e in sys.path if e != ""]
    path = []
    for entry in sys.path:
        if entry == "":
            # Turns out `poetry run` puts the project directory on the path,
            # it's just _last_ and I didn't notice it at first.
            # path.append(str(Path.cwd()))
            pass
        else:
            path.append(entry)
    return path


def default_work_dir() -> Path:
    return Path.cwd()


def default_install_dir() -> Path:
    return Path.cwd() / "bin"


def _get_dir_path(
    arg: str | Path | None, default: Path | Callable[[], Path]
) -> Path:
    match arg:
        case None:
            return default() if callable(default) else default
        case Path():
            return arg
        case str(s):
            return Path(s)
    raise TypeError("bad dir")


@cmd.as_cmd
def build(
    name: str,
    *,
    work_dir: Path = default_work_dir(),
    python_exe: Path = default_python_exe(),
    python_path: str | list[Path] = default_python_path(),
):
    """Build an _entrypoint_ executable. Configuration is compiled in from the
    arguments (so that the executable doesn't have to read anything to execute).

    ##### Parameters #####

    -   `name` — Name of the target executable, which is typically the name of
        the Clavier app it's being built for.

        This needs to match the name of the Calvier app that the _entrypoint_
        targets, since it's used in the PID and socket file names.

    -   `work_dir` — Where the Clavier app server will "live", i.e. store it's
        PID and socket files.

        If `None` this defaults to the current directory (see
        `default_work_dir`).

    -   `python_exe` — What `python` executable to use when starting the server.

        This defaults to the `python` executable that is currently being used,
        via `sys.executable` (see `default_python_exe`).

        If you run `poetry run python -m clavier.srv.entrypoint` from your app's
        project you should get the correct `python` by default.

    -   `python_path` — The `PYTHONPATH` environment variable to set when when
        starting the server. This defaults to the current Python path via
        `sys.path` (see `default_python_path`).

        If you run `poetry run python -m clavier.srv.entrypoint` from your app's
        project you should get the correct Python path by default.
    """

    work_dir_p: Path = (
        default_work_dir() if work_dir is None else Path(work_dir)
    ).resolve()

    work_dir_p.mkdir(parents=True, exist_ok=True)

    sh.run(
        ["cargo", "build", "--release"],
        cwd=ENTRYPOINT_PKG_ROOT,
        env=(
            os.environ
            | {
                "ENTRYPOINT_NAME": name,
                "ENTRYPOINT_WORK_DIR": str(work_dir_p),
                "ENTRYPOINT_PYTHON_EXE": str(python_exe),
                "ENTRYPOINT_PYTHON_PATH": ":".join(
                    str(p) for p in always_iterable(python_path)
                ),
            }
        ),
    )


@cmd.as_cmd
def install(name: str, install_dir: Path = default_install_dir()):
    install_dir_p = (
        default_install_dir() if install_dir is None else Path(install_dir)
    ).resolve()

    install_dir_p.mkdir(parents=True, exist_ok=True)

    dest = install_dir_p / name
    src = ENTRYPOINT_PKG_ROOT / "target" / "release" / ENTRYPOINT_PKG_NAME

    shutil.copyfile(src, dest)
    shutil.copymode(src, dest)


@cmd.as_cmd
def create(
    name: str,
    work_dir: Path = default_work_dir(),
    python_exe: Path = default_python_exe(),
    python_path: str | list[Path] = default_python_path(),
    install_dir: Path = default_install_dir(),
):
    build(
        name, work_dir=work_dir, python_exe=python_exe, python_path=python_path
    )
    install(name, install_dir)


def main(argv: Sequence[str] | None = None) -> int:
    sesh = Sesh(
        pkg_name=__name__,
        description="""
            Generate an _entrypoint_ executable that talks to a Clavier app
            running in _server mode_ (see `clavier.srv`)
        """,
        cmds=(create, build, install),
        prog_name=__name__,
    )

    return sesh.execute(argv)


if __name__ == "__main__":
    sys.exit(main())
