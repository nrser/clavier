##############################################################################
# ❗❗ WARNING ❗❗
#
# This was the original prototype client for the `clavier.srv` server, before
# the Rust one (in the top-level `endpoint` directory) was written.
#
# The Rust one is tremendously faster, and, that being the whole goal of
# `clavier.srv`, this client is no longer in use, and won't be maintained or
# updated.
#
# It's simply here for reference at the moment, should I need it (2023-02-19).
#
##############################################################################

import pickle
import signal
import socket
from pathlib import Path
import sys
from time import perf_counter, sleep
import os
from typing import Callable, Iterable, NoReturn, Sequence
from argparse import ArgumentParser


from .config import Config, MAX_DATA_LENGTH, INT_STRUCT


WORK_DIR = Path(__file__).parents[1]
FWD_SIGNAL_NUMS: tuple[int, ...] = (signal.SIGINT,)

RESET_SERVER_ARGS = ("-_R", "-_RESET")
START_SERVER_ARGS = ("-_S", "-_START")


class ForwardSignals:
    _sock: socket.socket
    _signal_numbers: list[int]
    _prev_handlers: list[Callable | int | signal.Handlers | None]

    def __init__(self, sock: socket.socket, signal_numbers: Iterable[int]):
        self._sock = sock
        self._signal_numbers = list(signal_numbers)
        self._prev_handlers = []

    def _forward_signal(self, signal_number: int, stack_frame):
        self._sock.send(INT_STRUCT.pack(int(signal_number)))

    def __enter__(self):
        for signal_number in self._signal_numbers:
            self._prev_handlers.append(signal.getsignal(signal_number))
            signal.signal(signal_number, self._forward_signal)

    def __exit__(self, type, value, traceback):
        for index, signal_number in enumerate(self._signal_numbers):
            signal.signal(signal_number, self._prev_handlers[index])


def info(*values: object) -> None:
    print("[info]", *values, file=sys.stderr)


def err(*values: object) -> None:
    print("[error]", *values, file=sys.stderr)


def kill(config: Config) -> NoReturn:
    from .server import Server, WontDieError

    if not config.pid_file_path.exists():
        info(f"Server not running -- no pid file at {config.pid_file_path}")
        sys.exit(0)

    try:
        Server.destroy(config)
    except WontDieError as error:
        err(error)
        sys.exit(1)

    sys.exit(0)


def wait_for_socket_file(
    config: Config, attempts: int = 10, poll: float = 0.1
) -> None:
    t_start = perf_counter()

    for _ in range(attempts):
        if config.socket_file_path.exists():
            return
        sleep(poll)

    delta_t = perf_counter() - t_start

    raise RuntimeError(
        f"Socket file never showed up, tried {attempts} times over "
        f"{delta_t:.3f} seconds (look for {config.socket_file_path}"
    )


def wait_for_socket_connect(
    config: Config,
    sock: socket.socket,
    attempts: int = 100,
) -> None:
    address = str(config.socket_file_path)
    t_start = perf_counter()

    last_error = None

    for _ in range(attempts):
        try:
            sock.connect(address)
        except (ConnectionRefusedError, FileNotFoundError) as error:
            last_error = error
        else:
            return

    delta_t = perf_counter() - t_start

    raise RuntimeError(
        f"Failed to connect to server socket at {address}, "
        f"tried {attempts} times over {delta_t:.3f} seconds"
    ) from last_error


def main(config: Config, argv: Sequence[str] | None = None) -> NoReturn:
    if argv is None:
        argv = sys.argv

    parser = ArgumentParser(
        prog=config.name,
        description=f"""
            This is help for the client frontend for Clavier-based CLI
            `{config.name}`. This is not the `{config.name}` CLI itself, just
            the entry-point wrapper, the code for which can be found at
            `{__name__}:main`. Listed below are the special options that this
            wrapper consumes and acts upon. ALl other arguments are passed
            through to the `{config.name}` CLI.
        """,
        add_help=False,
    )

    parser.add_argument(
        "-_R",
        "--_RESTART",
        dest="restart",
        action="store_true",
        default=False,
        help="""
            Restart the CLI server before processing the current request,
            reloading any code changes.

            If the server is not running this has no effect, as it's
            started automatically.
        """,
    )

    parser.add_argument(
        "-_K",
        "--_KILL",
        dest="kill",
        action="store_true",
        default=False,
        help="""
            Terminate the server and exit with code 0.
        """,
    )

    parser.add_argument(
        "-_N",
        "--_NOOP",
        dest="noop",
        action="store_true",
        default=False,
        help="""
            Don't send a command to the server; simply exit with code 0 after
            starting the server (if it's not already running).
        """,
    )

    parser.add_argument("-_H", "--_HELP", action="help")

    srv_args, argv_out = parser.parse_known_args(argv)

    if srv_args.kill:
        kill(config)

    if srv_args.restart or (not config.pid_file_path.exists()):
        from .server import Server

        Server.create(config)

        if srv_args.noop:
            sys.exit(0)

        wait_for_socket_file(config)

    elif srv_args.noop:
        sys.exit(0)

    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
        wait_for_socket_connect(config, sock)

        payload = (os.getcwd(), dict(os.environ), argv_out)

        data = pickle.dumps(payload)

        if len(data) > MAX_DATA_LENGTH:
            raise ValueError(
                "Noo much data ({} bytes, max is {})".format(
                    len(data), MAX_DATA_LENGTH
                )
            )

        fds = [0, 1, 2]

        if "_ARGCOMPLETE" in os.environ:
            fds.append(8)
            fds.append(9)

        with ForwardSignals(sock, FWD_SIGNAL_NUMS):
            socket.send_fds(sock, [data], fds)
            data = sock.recv(INT_STRUCT.size)

        exit_status = INT_STRUCT.unpack(data)[0]

    os.closerange(0, max(fds) + 1)
    os._exit(exit_status)
