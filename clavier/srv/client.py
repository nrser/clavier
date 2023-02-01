import pickle
import signal
import socket
from pathlib import Path
import sys
from time import sleep
import os
from types import FrameType, TracebackType
from typing import Any, Callable, Iterable, NoReturn, TypeAlias, Union

import splatlog
from rich.console import Console

from .config import Config, MAX_DATA_LENGTH, INT_STRUCT, GetSesh


SignalHandler: TypeAlias = Union[
    Callable[[int, FrameType | None], Any], int, signal.Handlers, None
]

_LOG = splatlog.get_logger(__name__)
WORK_DIR = Path(__file__).parents[1]
FWD_SIGNAL_NUMS: tuple[int, ...] = (signal.SIGINT,)
RESET_SERVER_ARGS = ("-_R", "-_RESET")


class ForwardSignals:
    _sock: socket.socket
    _signal_numbers: list[int]
    _prev_handlers: list[SignalHandler]

    def __init__(self, sock: socket.socket, signal_numbers: Iterable[int]):
        self._sock = sock
        self._signal_numbers = list(signal_numbers)
        self._prev_handlers = []

    def _forward_signal(
        self, signal_number: int, stack_frame: FrameType | None
    ) -> Any:
        self._sock.send(INT_STRUCT.pack(int(signal_number)))

    def __enter__(self):
        for signal_number in self._signal_numbers:
            self._prev_handlers.append(signal.getsignal(signal_number))
            signal.signal(signal_number, self._forward_signal)

    def __exit__(
        self,
        type: type[BaseException],
        value: BaseException,
        traceback: TracebackType | None,
    ) -> None:
        for index, signal_number in enumerate(self._signal_numbers):
            signal.signal(signal_number, self._prev_handlers[index])


def process_argv() -> bool:
    if any(arg in RESET_SERVER_ARGS for arg in sys.argv):
        sys.argv = [arg for arg in sys.argv if arg not in RESET_SERVER_ARGS]
        return True
    return False


def main(config: Config) -> NoReturn:
    with config.client_log_path.open("a+", encoding="utf-8") as log_file:
        console = Console(
            file=log_file,
            color_system="truecolor",
            force_terminal=True,
        )

        handler = splatlog.RichHandler(console=console)

        root_logger = splatlog.get_logger(splatlog.root_name(__name__))
        # TODO  Some way to control this...
        root_logger.setLevel(splatlog.DEBUG)
        # Don't propagate logs! Otherwise they'll end up hitting the root
        # logger that the CLI sets up
        root_logger.logger.propagate = False
        root_logger.addHandler(handler)

        reset = False

        if any(arg in RESET_SERVER_ARGS for arg in sys.argv):
            sys.argv = [arg for arg in sys.argv if arg not in RESET_SERVER_ARGS]
            reset = True

        if reset or (not config.pid_file_path.exists()):
            from .server import Server

            _LOG.debug("Creating server...")
            Server.create(config)

        while not config.socket_file_path.exists():
            _LOG.debug("Waiting for socket file to be created...")
            sleep(0.25)

        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
            while True:
                try:
                    sock.connect(str(config.socket_file_path))
                except (ConnectionRefusedError, FileNotFoundError):
                    pass
                else:
                    break

            payload = (os.getcwd(), dict(os.environ), sys.argv)

            data = pickle.dumps(payload)

            if len(data) > MAX_DATA_LENGTH:
                raise ValueError(
                    "Noo much data ({} bytes, max is {})".format(
                        len(data), MAX_DATA_LENGTH
                    )
                )

            # fds = [f.fileno() for f in (sys.stdin, sys.stdout, sys.stderr)]
            fds = [0, 1, 2]

            if "_ARGCOMPLETE" in os.environ:
                _LOG.debug("Argcomplete! Appending fds 8 and 9...")
                fds.append(8)
                fds.append(9)

            with ForwardSignals(sock, FWD_SIGNAL_NUMS):
                _LOG.debug(
                    "Sending request...",
                    cwd=payload[0],
                    argv=payload[2],
                    fds=fds,
                )
                socket.send_fds(sock, [data], fds)

                _LOG.debug("Waiting for response...")
                data = sock.recv(INT_STRUCT.size)

            exit_status = INT_STRUCT.unpack(data)[0]

            _LOG.debug(f"Received exit status", exit_status=exit_status)

        _LOG.debug("Closing file desriptors", fds=fds)
        os.closerange(0, max(fds) + 1)
        _LOG.debug(
            "File descriptors closed; closing log and exiting.",
            exit_status=exit_status,
        )

    os._exit(exit_status)
