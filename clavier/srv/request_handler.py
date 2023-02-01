from __future__ import annotations
import os
import pickle
import signal
import socket
from socketserver import BaseRequestHandler
import sys
import threading
from time import monotonic_ns
from typing import TYPE_CHECKING, Any, NamedTuple

import splatlog

from .config import INT_STRUCT

if TYPE_CHECKING:
    from .server import Server


MS_TO_NS = 10**6


class Request(NamedTuple):
    data: bytes
    fds: list[int]
    socket: socket.socket


class RequestHandler(BaseRequestHandler):
    _log = splatlog.LoggerProperty()

    if TYPE_CHECKING:
        server: "Server"
        request: Request

    _cwd: str | None = None
    _env: dict[str, str] | None = None
    _argv: list[str] | None = None
    _exit_status: int = 0
    _done_event: threading.Event | None = None
    _thread: threading.Thread | None = None

    @property
    def _splatlog_self_(self):
        return self.server._splatlog_self_

    @property
    def cwd(self) -> str:
        if self._cwd is None:
            raise AttributeError(
                "must call _parse_request to make cwd available"
            )
        return self._cwd

    @property
    def env(self) -> dict[str, str]:
        if self._env is None:
            raise AttributeError(
                "must call _parse_request to make env available"
            )
        return self._env

    @property
    def argv(self) -> list[str]:
        if self._argv is None:
            raise AttributeError(
                "must call _parse_request to make argv available"
            )
        return self._argv

    def _signal_thread(
        self, sock: socket.socket, done_event: threading.Event
    ) -> None:
        sock.settimeout(0.01)

        while not done_event.is_set():
            try:
                data = sock.recv(INT_STRUCT.size)
            except socket.timeout:
                pass
            else:
                signal_number = INT_STRUCT.unpack(data)[0]
                self._log.info("Raising signal", signal_number=signal_number)
                signal.raise_signal(signal_number)

    def _parse_request(self):
        self._log.debug("Parsing request (un-pickling)...")
        cwd, env, argv = pickle.loads(self.request.data)
        self._cwd = cwd
        self._env = env
        self._argv = argv
        self._log.debug("Request parsed.")

    def _set_stdio(self) -> None:
        if len(self.request.fds) < 3:
            raise ValueError(
                "Expected at least 3 file descriptors (stdin, stdout, stderr), "
                f"received {len(self.request.fds)}: {self.request.fds}"
            )

        self._log.debug(f"Setting stdio fds...")
        for fd, stdio in zip(
            self.request.fds, (sys.stdin, sys.stdout, sys.stderr)
        ):
            os.dup2(fd, stdio.fileno())

        self._log.debug("Stdio set.")

    def _unset_stdio(self) -> None:
        self._log.debug("Unsetting stdio...")

        # ...and why not..?
        for stdio in (sys.stdout, sys.stderr):
            stdio.flush()

        dev_null = os.open(os.devnull, os.O_RDWR)
        for fd in (0, 1, 2):
            os.dup2(dev_null, fd)

        self._log.debug("Stdio unset.")

    def _set_environment(self) -> None:
        self._log.debug("Setting env...")
        os.environ.clear()
        os.environ.update(self.env)

        self._log.debug("Setting argv...", argv=self.argv)
        sys.argv = self.argv

        self._log.debug("Changing directory...", cwd=self.cwd)
        os.chdir(self.cwd)

    def _start_signal_thread(self) -> None:
        self._log.debug("Starting signal handler thread...")
        self._done_event = threading.Event()
        self._thread = threading.Thread(
            name="signal_handler",
            target=self._signal_thread,
            kwargs=dict(
                sock=self.request.socket,
                done_event=self._done_event,
            ),
        )
        self._thread.start()
        self._log.debug("Signal handler thread started.", thread=self._thread)

    def _handle(self) -> None:
        self._parse_request()
        self._set_stdio()
        self._set_environment()
        self._start_signal_thread()

        sesh = self.server.get_sesh()

        if "_ARGCOMPLETE" in self.env:
            self._log.debug("Setting up argcomplete...")

            with os.fdopen(self.request.fds[3], "wb") as output_stream:
                import argcomplete

                finder = argcomplete.CompletionFinder()
                finder(
                    sesh.parser,
                    exit_method=sys.exit,
                    output_stream=output_stream,
                )

        self._log.debug(f"Starting CLI...")
        sesh.parse().execute()

    def handle(self) -> None:
        t_start_ns = monotonic_ns()

        try:
            self._handle()

        except SystemExit as exit:
            self._log.debug(f"CLI exited via SystemExit", code=exit.code)
            match exit.code:
                case None:
                    pass
                case int(i):
                    self._exit_status = i
                case str(s):
                    self._exit_status = 1

        except BaseException:
            self._log.exception(f"CLI raised unexpected error")
            self._exit_status = 1

        finally:
            if done_event := self._done_event:
                self._log.debug("Setting done event...")
                done_event.set()

            if thread := self._thread:
                self._log.debug("Joining thread...")
                thread.join()
                self._log.debug("Signal thread done.")

            try:
                self._unset_stdio()
            except:
                self._log.exception("Failed to un-set stdio!")

            self._log.debug(
                f"Sending exit status...", exit_status=self._exit_status
            )
            self.request.socket.send(INT_STRUCT.pack(self._exit_status))

            delta_ms = (monotonic_ns() - t_start_ns) // MS_TO_NS

            self._log.info(
                "Request handled",
                delta_ms=delta_ms,
                exit_status=self._exit_status,
            )
