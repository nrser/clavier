from __future__ import annotations
import atexit
from io import TextIOWrapper
import os
import signal
import socket
import sys
from socketserver import UnixStreamServer, ForkingMixIn
import threading
from time import monotonic_ns, sleep
from types import FrameType
from typing import Any, cast
from clavier.sesh import Sesh

import splatlog
from rich.console import Console
from rich.text import Text
from rich.style import Style

from .config import Config, MAX_DATA_LENGTH
from .request_handler import Request, RequestHandler

MAX_FDS = 5


class Server(ForkingMixIn, UnixStreamServer):
    _log = splatlog.LoggerProperty()

    @classmethod
    def create(cls, config: Config) -> None:
        # NOTE  0 is assumed to be an invalid pid
        if pid := config.read_pid():
            cls.destory(pid)

        try:
            pid = os.fork()
            if pid:
                return
        except OSError as e:
            sys.stderr.write(
                "fork #1 failed: %d (%s)\n" % (e.errno, e.strerror)
            )
            sys.exit(1)

        # decouple from parent environment
        os.chdir(config.work_dir)
        os.setsid()

        # You're _supposed to_ reset the `umask` when daemonizing, but I think
        # it's more intuitive if the server just runs with the same umask as
        # the terminal that started it
        # os.umask(0)

        # do second fork
        try:
            pid = os.fork()
            if pid:
                sys.exit(0)
        except OSError as e:
            sys.stderr.write(
                "fork #2 failed: %d (%s)\n" % (e.errno, e.strerror)
            )
            sys.exit(1)

        # We are now in the detached server daemon process!

        # Setup the pid file and register to remote it at exit
        pid = os.getpid()

        with config.pid_file_path.open("w+", encoding="utf-8") as pid_file:
            pid_file.write(f"{pid}\n")

        atexit.register(os.remove, config.pid_file_path)

        # Redirect standard file descriptors to /dev/null; we'll use logging
        # only for output
        dev_null = os.open(os.devnull, os.O_RDWR)
        for fd in (0, 1, 2):
            os.dup2(dev_null, fd)

        # Setup logging
        with config.server_log_path.open("a+", encoding="utf-8") as log_file:
            console = Console(
                file=log_file,
                color_system="truecolor",
                force_terminal=True,
            )

            handler = splatlog.RichHandler(console=console)

            srv_logger = splatlog.get_logger("clavier.srv")
            srv_logger.setLevel(config.server_log_level)
            # Don't propagate logs! Otherwise they'll end up hitting the root
            # logger that the CLI sets up
            srv_logger.logger.propagate = False
            srv_logger.addHandler(handler)

            # Remove the socket file if it exists
            if config.socket_file_path.exists():
                os.remove(config.socket_file_path)

            with Server(config) as server:
                server._log.info("Created server")

                signal.signal(signal.SIGTERM, server.terminate)
                server._log.info(f"Serving at {config.pid_file_path}")

                server.serve_forever(poll_interval=0.25)

                server._log.info("Done serving.")

        sys.exit(0)

    @classmethod
    def destory(
        cls, pid: int, attempts: int = 5, wait_scalar: float = 0.1
    ) -> None:
        assert attempts > 0, "Must make at least 1 attempt"
        assert wait_scalar > 0, "wait_scalar must be positive"

        total_wait = 0

        for attempt_index in range(attempts + 1):
            try:
                os.kill(pid, signal.SIGTERM)
            except OSError:
                # pid is not alive, we're done
                return

            wait = wait_scalar * (2**attempt_index)
            total_wait += wait

            sleep(wait)

        raise RuntimeError(
            f"Failed to kill server at pid {pid} "
            f"(made {attempts} over {total_wait} seconds)"
        )

    _config: Config
    _main_pid: int
    _cached_sesh: Sesh | None = None

    def __init__(self, config: Config):
        super().__init__(str(config.socket_file_path), RequestHandler)

        self._config = config
        self._main_pid = os.getpid()

        if config.cache_sesh is True:
            try:
                self._cached_sesh = config.get_sesh()
            except:
                self._log.exception("Failed to create cached session")

    @property
    def _splatlog_self_(self) -> Text:
        pid = os.getpid()
        if pid == self._main_pid:
            role = "Daemon"
            color = "red"
        else:
            role = "Child"
            color = "blue"

        return Text.assemble(
            (role, Style(color=color, bold=True)),
            " ",
            (str(pid), Style(color="cyan", bold=True)),
        )

    @property
    def config(self) -> Config:
        return self._config

    def get_sesh(self) -> Sesh:
        if sesh := self._cached_sesh:
            return sesh
        return self._config.get_sesh()

    def terminate(
        self, signal_number: int, stack_frame: FrameType | None
    ) -> Any:
        # NOTE  See note on `BaseServer.shutdown`:
        #
        #       > Blocks until the loop has finished. This must be called while
        #       > serve_forever() is running in another thread, or it will
        #       > deadlock.
        #
        threading.Thread(target=self.shutdown).start()

    # socketserver.BaseServer API
    # ------------------------------------------------------------------------

    def finish_request(self, request: Request, client_address: Any) -> None:
        # This method gets called pretty soon after fork, so we insert code
        # here to fix up the `_splatlog_self_`
        pid = os.getpid()
        if self._main_pid != pid:
            cast(splatlog.SelfLogger, self._log).set_identity(
                self._splatlog_self_
            )
            self._log.debug("Finishing request (in child)")

        super().finish_request(request, client_address)  # type: ignore

    def get_request(self) -> tuple[Request, Any]:
        self._log.debug("Getting request...")

        sock, client_addr = self.socket.accept()
        t_start_ns = monotonic_ns()

        data, fds, _flags, _addr = socket.recv_fds(
            sock, MAX_DATA_LENGTH, MAX_FDS
        )

        request = Request(data, fds, sock, t_start_ns)

        self._log.debug(f"Got request", data_bytes=len(data), fds=fds)

        return request, client_addr

    def shutdown(self) -> None:
        self._log.debug("Shutdown requested...")
        super().shutdown()

    def server_close(self) -> None:
        self._log.debug(f"Closing server...")
        super().server_close()

        path = self._config.socket_file_path

        if path.exists():
            self._log.debug("Removing socket file...", path=path)

            try:
                os.remove(path)
            except:
                self._log.exception("Failed to remove socket file", path=path)
            else:
                self._log.debug("Socket file removed.")

        else:
            self._log.warning("Socket file not found", path=path)

        self._log.debug(f"Server closed.")

    def close_request(self, request: Request) -> None:
        self._log.debug(f"Closing request...")

        request.socket.close()

        if request.fds:
            self._log.debug("Closing file descriptors...")
            os.closerange(min(request.fds), max(request.fds) + 1)
        else:
            self._log.debug("No file descriptors to close.")

        self._log.debug(f"Request closed.")

    def handle_error(self, request, client_address):
        """Handle an error gracefully.  May be overridden.

        The default is to print a traceback and continue.

        """
        self._log.error(
            "Exception occurred during processing of request from {}",
            client_address,
            exc_info=sys.exc_info(),
        )
