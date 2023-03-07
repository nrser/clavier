from dataclasses import dataclass, field
from pathlib import Path
import struct
from typing import Callable, Literal
import builtins
import logging

from clavier.app import App

MAX_DATA_LENGTH = 65536
DEFAULT_KILL_ATTEMPTS = 5
DEFAULT_KILL_WAIT_SCALAR = 0.1

# Single C `int` structure, used for process exit status, signals.
#
# Even though exit status pretty much should be in [0, 127], but just use a
# signed integer to not worry about it.
#
INT_STRUCT = struct.Struct("i")

GetApp = Callable[[], App]


@dataclass(frozen=True)
class Config:
    # Required fields

    name: str
    work_dir: Path
    get_app: GetApp

    # Optional fields

    cache_app: bool = False
    server_log_level: int = logging.INFO
    terminate_attempts: int = 5
    terminate_backoff_base: float = 0.1

    server_log_color_system: Literal[
        "auto", "standard", "256", "truecolor"
    ] | None = "truecolor"
    server_log_force_terminal: bool = True
    server_log_width: int = 80

    # Generated fields, see `__post_init__`

    pid_file_path: Path = field(init=False)
    socket_file_path: Path = field(init=False)

    server_log_path: Path = field(init=False)

    def __post_init__(self):
        assert (
            self.terminate_attempts > 0
        ), f"`terminate_attempts` must be > 0, given {self.terminate_attempts!r}"

        assert (
            self.terminate_backoff_base > 0
        ), f"`terminate_backoff_base` must be > 0, given {self.terminate_backoff_base}"

        set_ = builtins.object.__setattr__
        set_(self, "pid_file_path", self.work_dir / f".{self.name}.pid")
        set_(self, "socket_file_path", self.work_dir / f".{self.name}.sock")
        set_(
            self, "server_log_path", self.work_dir / f".{self.name}.server.log"
        )

    def try_read_pid(self) -> int | None:
        try:
            return self.read_pid()
        except (SystemExit, KeyboardInterrupt):
            raise
        except:
            return None

    def read_pid(self) -> int:
        """
        Read process ID from `pid_file_path`, returning `None` if:

        1.  The file does not exist.
        2.  We failed to read it.
        3.  The
        """

        with self.pid_file_path.open("r", encoding="utf-8") as file:
            return int(file.read().strip())
