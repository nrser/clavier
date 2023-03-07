import json
import os
from pathlib import Path
import sys
import shutil
from typing import Any, Mapping, Sequence
from clavier.etc import txt
import distutils.spawn
from types import MappingProxyType

import tomli
import splatlog

from clavier import App, cmd, sh, io, cfg, etc, err, arg_par

_LOG = splatlog.get_logger(__name__)

CLAVIER_PKG_ROOT = Path(__file__).parents[2]
ENTRYPOINT_PKG_ROOT = CLAVIER_PKG_ROOT / "entrypoint"

DEFAULT_WORK_DIR = Path.cwd()
# DEFAULT_PYTHON_EXE = Path(sys.executable)
# DEFAULT_PYTHON_PATH = tuple(Path(path) for path in sys.path if path != "")
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
                txt.fmt(int),
                txt.fmt_type_of(pkg_name),
                txt.fmt(pkg_name),
            )
        )

    return pkg_name


def get_default_name() -> str:
    cwd = Path.cwd()
    dir = cwd

    while dir.parent != dir:
        path = dir / "pyproject.toml"

        if path.is_file():
            try:
                with path.open("rb") as file:
                    pyproject = tomli.load(file)
                name = pyproject["tool"]["poetry"]["name"]

                if isinstance(name, str):
                    return name
            except:
                pass

        dir = dir.parent

    raise err.UserError(
        "Failed to find a pyproject.toml to get a default name from, "
        "please provide an explicit `--name`"
    )


def resolve_exe(exe: str) -> str:
    if resolved := distutils.spawn.find_executable(exe):
        return resolved

    raise RuntimeError(f"exe not found: {exe!r}")


def add_build_parser(subparsers: arg_par.Subparsers) -> None:
    # Run this like (?)
    #
    #   poetry run python -m clavier.srv.entrypoint build \
    #       --name cat-sprayer \
    #       --work-dir . \
    #       --install-dir ./bin \
    #       --start-env CLAVIER_SRV=true \
    #       --start-cwd . \
    #       -- poetry run blah --_NOOP
    #

    parser = subparsers.add_parser(
        "build",
        target=build,
        help="""
            Build an _entrypoint_ executable. Configuration is compiled in from
            the arguments (so that the executable doesn't have to read anything
            to execute).
        """,
    )

    parser.add_argument(
        "start_cmd",
        nargs="*",
    )

    parser.add_argument(
        "-n",
        "--name",
        help="""
            Name of the target executable, which is typically the name of
            the Clavier app it's being built for.

            This needs to match the name of the Calvier app that the _entrypoint_
            targets, since it's used in the PID and socket file names.
        """,
    )

    parser.add_argument(
        "-d",
        "--work-dir",
        type=Path,
        help="""
            Directory to find `.<name>.pid` and `.<name>.sock` in. needs to
            match the configuration on the server.
        """,
    )

    parser.add_argument(
        "--start-cwd",
        type=Path,
        help="""
            Optional directory to run the server command in. Useful with
            `poetry`. If absent, the `--work-dir` will be used.
        """,
    )

    parser.add_argument(
        "--start-env",
        action=arg_par.actions.SetItem,
        help="""
            Additional environment variables to set when _starting_ the server.

            > 📝 NOTE
            >
            > These variables will be cleared when a request is handled, as the
            > handling process replaces it's env with the env of the caller.
            >
        """,
    )

    parser.add_argument(
        "-i",
        "--install-dir",
        type=Path,
        help="""
            Optionally "install" the entrypoint binary to a directory. Just
            moves it there.
        """,
    )

    parser.add_argument(
        "--run-dotenv",
        type=Path,
        help="""
            Optional `.env` file for the entrypoint to load _every_ time it
            executes a command. So, obviously, it will add latency.

            This is needed if you count on `poetry-dotenv-plugin` to load env
            vars from `.env` file (like compiler flags, library paths, etc...
            lookin' at you macOS).
        """,
    )


def build(
    start_cmd: Any,
    name: str | None = None,
    work_dir: Path = DEFAULT_WORK_DIR,
    start_cwd: Path | None = None,
    start_env: Mapping[str, str] = {},
    install_dir: Path | None = None,
    run_dotenv: Path | None = None,
):
    """Build an _entrypoint_ executable. Configuration is compiled in from the
    arguments (so that the executable doesn't have to read anything to execute).
    """

    name = name or get_default_name()

    work_dir = work_dir.resolve()
    work_dir.mkdir(parents=True, exist_ok=True)

    if start_cwd is None:
        resolved_start_cwd = work_dir
    else:
        resolved_start_cwd = start_cwd.resolve()

        assert resolved_start_cwd.is_dir(), (
            "`--start-cwd` must be a directory, given {} that resolved to {}"
        ).format(start_cwd, resolved_start_cwd)

    program, *args = start_cmd

    start_cmd = {
        "env": start_env,
        "cwd": str(resolved_start_cwd),
        "program": resolve_exe(program),
        "args": args,
    }

    pid_path = str(work_dir / f".{name}.pid")
    socket_path = str(work_dir / f".{name}.sock")

    _LOG.info(
        "Building endpoint...",
        pid_path=pid_path,
        socket_path=socket_path,
        start_cmd=start_cmd,
        run_dotenv=run_dotenv,
    )

    env = {
        "ENTRYPOINT_PID_PATH": pid_path,
        "ENTRYPOINT_SOCKET_PATH": socket_path,
        "ENTRYPOINT_START_CMD_JSON": json.dumps(start_cmd),
    }

    if run_dotenv is not None:
        run_dotenv = run_dotenv.resolve()

        assert run_dotenv.is_file(), ("Run .env file not found at {}").format(
            run_dotenv
        )

        env["ENTRYPOINT_DOTENV_PATH"] = str(run_dotenv)

    _LOG.debug("Build environment additions", env=env)

    sh.run(
        ["cargo", "build", "--release"],
        cwd=ENTRYPOINT_PKG_ROOT,
        env=(os.environ | env),
    )

    _LOG.info("Successfully built.")

    if install_dir is not None:
        dest = install_dir / name
        src = ENTRYPOINT_PKG_ROOT / "target" / "release" / entrypoint_pkg_name()

        shutil.move(src, dest)

        _LOG.info("Moved binary to {}", dest)


def main(argv: Sequence[str] | None = None) -> int:
    name = __spec__.name
    app = App(
        # Need to do this 'cause `__name__` is set to "__main__" when running
        # via `python -m clavier.srv.entrypoint`
        pkg_name=name,
        description="""
            Generate an _entrypoint_ executable that talks to a Clavier app
            running in _server mode_ (see `clavier.srv`)
        """,
        cmds=add_build_parser,
    )

    with cfg.changeset(io.rel, src=name) as rel:
        rel.to = Path.cwd()

    return app.execute(argv)


if __name__ == "__main__":
    sys.exit(main())
