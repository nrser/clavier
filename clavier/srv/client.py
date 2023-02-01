import pickle
import signal
import socket
from pathlib import Path
import sys
from time import sleep
import os
from typing import Callable, Iterable, NoReturn


from .config import Config, MAX_DATA_LENGTH, INT_STRUCT


WORK_DIR = Path(__file__).parents[1]
FWD_SIGNAL_NUMS: tuple[int, ...] = (signal.SIGINT,)
RESET_SERVER_ARGS = ("-_R", "-_RESET")


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


def main(config: Config) -> NoReturn:
    reset = False

    if any(arg in RESET_SERVER_ARGS for arg in sys.argv):
        sys.argv = [arg for arg in sys.argv if arg not in RESET_SERVER_ARGS]
        reset = True

    if reset or (not config.pid_file_path.exists()):
        from .server import Server

        Server.create(config)

    while not config.socket_file_path.exists():
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
