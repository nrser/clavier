from __future__ import annotations
import atexit
import os
from pathlib import Path
import signal
import socket
import sys
from socketserver import UnixStreamServer, ForkingMixIn
import threading
from time import monotonic_ns, perf_counter, sleep
from types import FrameType
from typing import Any, cast


from watchfiles import Change, watch
import splatlog
from rich.console import Console
from rich.text import Text
from rich.style import Style

from clavier.sesh import Sesh
from .config import Config, MAX_DATA_LENGTH
from .request_handler import Request, RequestHandler
from .watchable_module import WatchableModule

MAX_FDS = 5


class WontDieError(Exception):
    pass


def is_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def terminate(pid: int, attempts: int = 5, backoff_base: float = 0.1) -> None:
    assert attempts > 0, "Must make at least 1 attempt"
    assert backoff_base > 0, "backoff_base must be positive"

    if not is_alive(pid):
        return

    t_start = perf_counter()

    for attempt_index in range(attempts):
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError:
            # pid is not alive, we're done
            return

        # Give it 50ms to die. Just randomly picked this number.
        sleep(0.05)

        # If it's dead we're done!
        if not is_alive(pid):
            return

        # Otherwise sleep for a bit (exponential back-off)
        wait = backoff_base * (2**attempt_index)

        sleep(wait)

    delta_t = perf_counter() - t_start

    raise WontDieError(
        f"Failed to terminate server at pid {pid} "
        f"(made {attempts} over {delta_t:.3f} seconds)"
    )


class Server(ForkingMixIn, UnixStreamServer):
    _log = splatlog.LoggerProperty()

    @classmethod
    def create(cls, config: Config) -> None:
        # Kill the server if it's already running
        cls.destroy(config)

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

        # Only allow user, applies to socket file created
        os.umask(0o077)

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

        with config.pid_file_path.open("x", encoding="utf-8") as pid_file:
            pid_file.write(f"{pid}\n")

        atexit.register(os.remove, config.pid_file_path)

        # Redirect standard file descriptors to /dev/null; we'll use logging
        # only for output
        dev_null = os.open(os.devnull, os.O_RDWR)
        for fd in (0, 1, 2):
            os.dup2(dev_null, fd)

        # Setup logging
        with config.server_log_path.open("a", encoding="utf-8") as log_file:
            console = Console(
                file=log_file,
                color_system=config.server_log_color_system,
                force_terminal=config.server_log_force_terminal,
                width=config.server_log_width,
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

                server.watch_files()

                signal.signal(signal.SIGTERM, server._handle_terminate)
                server._log.info(f"Serving at {config.pid_file_path}")

                server.serve_forever(poll_interval=0.25)

                server._log.info("Done serving.")

        sys.exit(0)

    @classmethod
    def destroy(cls, config: Config) -> None:
        if pid := config.try_read_pid():
            terminate(
                pid, config.terminate_attempts, config.terminate_backoff_base
            )

        try:
            os.remove(config.pid_file_path)
        except FileNotFoundError:
            pass

        try:
            os.remove(config.socket_file_path)
        except FileNotFoundError:
            pass

    _config: Config
    _main_pid: int
    _cached_sesh: Sesh | None = None
    _watch_modules: set[WatchableModule]
    _watch_files_stop_event: threading.Event
    _watch_files_thread: threading.Thread
    _files_changed_event: threading.Event

    def __init__(self, config: Config):
        super().__init__(str(config.socket_file_path), RequestHandler)

        self._config = config
        self._main_pid = os.getpid()

        if config.cache_sesh is True:
            try:
                self._cached_sesh = config.get_sesh()
            except:
                self._log.exception("Failed to create cached session")

        self._watch_files_stop_event = threading.Event()
        self._files_changed_event = threading.Event()

        self._watch_modules = WatchableModule.root_set_of_loaded(
            exclude_sys_base=True,
            exclude_site_packages=True,
        )
        self._watch_files_thread = threading.Thread(
            name="Server._watch_files",
            target=self._watch_files,
        )

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

    def _handle_terminate(
        self, signal_number: int, stack_frame: FrameType | None
    ) -> Any:
        # NOTE  See note on `BaseServer.shutdown`:
        #
        #       > Blocks until the loop has finished. This must be called while
        #       > serve_forever() is running in another thread, or it will
        #       > deadlock.
        #
        threading.Thread(target=self.shutdown).start()

    def watch_files(self) -> None:
        self._log.debug(
            "Starting file watch...",
            dirs=[str(p) for p in self._watch_dirs],
        )
        self._watch_files_thread.start()

    @property
    def _watch_dirs(self) -> list[Path]:
        return sorted({wm.dir for wm in self._watch_modules})

    def _watch_filter(self, change: Change, file: str) -> bool:
        return file.endswith(".py")

    def _watch_files(self):
        for changes in watch(
            *self._watch_dirs,
            watch_filter=self._watch_filter,
            stop_event=self._watch_files_stop_event,
        ):
            self._log.debug("Watched file changes", changes=changes)
            self._files_changed_event.set()

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

        self._log.debug("Stopping file watch...")
        self._watch_files_stop_event.set()
        self._watch_files_thread.join()
        self._log.debug("File watch stopped.")

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

    def service_actions(self) -> None:
        super().service_actions()

        if self._files_changed_event.is_set():
            self._log.info("Files changed, shutting down...")
            threading.Thread(target=self.shutdown).start()
