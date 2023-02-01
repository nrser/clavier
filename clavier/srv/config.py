from dataclasses import dataclass, field
from pathlib import Path
import struct
from typing import Callable
import builtins
import logging

from clavier.sesh import Sesh

MAX_DATA_LENGTH = 65536

# Single C `int` structure, used for process exit status, signals.
#
# Even though exit status pretty much should be in [0, 127], but just use a
# signed integer to not worry about it.
#
INT_STRUCT = struct.Struct("i")

GetSesh = Callable[[], Sesh]


@dataclass(frozen=True)
class Config:
    # Required fields

    name: str
    work_dir: Path
    get_sesh: GetSesh

    # Optional fields

    cache_sesh: bool = False
    server_log_level: int = logging.INFO

    # Generated fields, see `__post_init__`

    pid_file_path: Path = field(init=False)
    socket_file_path: Path = field(init=False)

    server_log_path: Path = field(init=False)

    def __post_init__(self):
        set_ = builtins.object.__setattr__
        set_(self, "pid_file_path", self.work_dir / f".{self.name}.pid")
        set_(self, "socket_file_path", self.work_dir / f".{self.name}.sock")
        set_(
            self, "server_log_path", self.work_dir / f".{self.name}.server.log"
        )

    def read_pid(self) -> int | None:
        """
        Read process ID from `pid_file_path`, returning `None` if:

        1.  The file does not exist.
        2.  We failed to read it.
        3.  The
        """
        if not self.pid_file_path.exists():
            return None

        try:
            with self.pid_file_path.open("r", encoding="utf-8") as file:
                pid_str = file.read()
        except (SystemExit, KeyboardInterrupt):
            raise
        except BaseException:
            return None

        try:
            pid = int(pid_str.strip())
        except (SystemExit, KeyboardInterrupt):
            raise
        except BaseException:
            return None

        return pid
