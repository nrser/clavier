import os
from pathlib import Path
from subprocess import run
import sys
import shutil
from typing import Callable, Sequence
import tomli

from more_itertools import always_iterable

from clavier import Sesh, cmd, sh, io, txt

CLAVIER_PKG_ROOT = Path(__file__).parents[2]
ENTRYPOINT_PKG_ROOT = CLAVIER_PKG_ROOT / "entrypoint"

DEFAULT_WORK_DIR = Path.cwd()
DEFAULT_PYTHON_EXE = Path(sys.executable)
DEFAULT_PYTHON_PATH = tuple(Path(path) for path in sys.path if path != "")
DEFAULT_INSTALL_DIR = Path.cwd() / "bin"


def entrypoint_pkg_name() -> str:
    cargo_config_path = ENTRYPOINT_PKG_ROOT / "Cargo.toml"

    with cargo_config_path.open("rb") as file:
        cargo_config = tomli.load(file)

    pkg_name = cargo_config["package"]["name"]

    if not isinstance(pkg_name, str):
        raise TypeError(
            "expected {}:package.name to be a {}; found {}: {}".format(
                io.fmt_path(cargo_config_path),
                txt.fmt_type_of(pkg_name),
                txt.fmt(pkg_name),
            )
        )

    return pkg_name


@cmd.as_cmd
def build(
    name: str,
    *,
    work_dir: Path = DEFAULT_WORK_DIR,
    python_exe: Path = DEFAULT_PYTHON_EXE,
    python_path: str | list[Path] | tuple[Path, ...] = DEFAULT_PYTHON_PATH,
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
    work_dir = work_dir.resolve()
    work_dir.mkdir(parents=True, exist_ok=True)

    sh.run(
        ["cargo", "build", "--release"],
        cwd=ENTRYPOINT_PKG_ROOT,
        env=(
            os.environ
            | {
                "ENTRYPOINT_NAME": name,
                "ENTRYPOINT_WORK_DIR": str(work_dir),
                "ENTRYPOINT_PYTHON_EXE": str(python_exe),
                "ENTRYPOINT_PYTHON_PATH": ":".join(
                    str(p) for p in always_iterable(python_path)
                ),
            }
        ),
    )


@cmd.as_cmd
def install(name: str, *, install_dir: Path = DEFAULT_INSTALL_DIR):
    install_dir = install_dir.resolve()

    install_dir.mkdir(parents=True, exist_ok=True)

    dest = install_dir / name
    src = ENTRYPOINT_PKG_ROOT / "target" / "release" / entrypoint_pkg_name()

    shutil.copyfile(src, dest)
    shutil.copymode(src, dest)


@cmd.as_cmd
def create(
    name: str,
    *,
    work_dir: Path = DEFAULT_WORK_DIR,
    python_exe: Path = DEFAULT_PYTHON_EXE,
    python_path: str | list[Path] | tuple[Path, ...] = DEFAULT_PYTHON_PATH,
    install_dir: Path = DEFAULT_INSTALL_DIR,
):
    build(
        name, work_dir=work_dir, python_exe=python_exe, python_path=python_path
    )
    install(name, install_dir=install_dir)


def main(argv: Sequence[str] | None = None) -> int:
    sesh = Sesh(
        # Need to do this 'cause `__name__` is set to "__main__" when running
        # via `python -m clavier.srv.entrypoint`
        pkg_name=__spec__.name,
        description="""
            Generate an _entrypoint_ executable that talks to a Clavier app
            running in _server mode_ (see `clavier.srv`)
        """,
        cmds=(create, build, install),
    )

    return sesh.execute(argv)


if __name__ == "__main__":
    sys.exit(main())
