from __future__ import annotations
from dataclasses import dataclass
import json
import os
from pathlib import Path
import pickle
import signal
import socket
from socketserver import BaseRequestHandler
import sys
import threading
from time import monotonic_ns
from typing import TYPE_CHECKING, Any, Literal, NamedTuple, TypedDict

import splatlog
from rich.console import Console

from .config import INT_STRUCT
from clavier import err

if TYPE_CHECKING:
    from .server import Server


MS_TO_NS = 10**6


class Request(NamedTuple):
    data: bytes
    fds: list[int]
    socket: socket.socket
    t_start_ns: int


class ReplaceProcess(TypedDict):
    env: dict[str, str] | None
    cwd: str | None
    program: str
    args: list[str] | None


@dataclass
class Response:
    exit_status: int
    replace_process: ReplaceProcess | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "exit_status": self.exit_status,
            "replace_process": self.replace_process,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict())

    def to_bytes(self) -> bytes:
        return bytes(self.to_json(), encoding="utf-8")


class RequestHandler(BaseRequestHandler):
    _log = splatlog.LoggerProperty()

    if TYPE_CHECKING:
        server: "Server"
        request: Request

    _cwd: str | None = None
    _env: dict[str, str] | None = None
    _argv: list[str] | None = None
    _response: Response
    _done_event: threading.Event | None = None
    _thread: threading.Thread | None = None

    def setup(self) -> None:
        self._response = Response(exit_status=0)

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

    @property
    def args(self) -> list[str] | None:
        if self._argv is None:
            return None
        return self._argv[1:]

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
                if len(data) == INT_STRUCT.size:
                    signal_number = INT_STRUCT.unpack(data)[0]
                    self._log.info(
                        "Raising signal", signal_number=signal_number
                    )
                    signal.raise_signal(signal_number)

    def _try_parse_with_pickle(
        self,
    ) -> tuple[Literal[True], None] | tuple[Literal[False], Exception]:
        self._log.debug("Trying to parse with `pickle`...")
        try:
            cwd, env, argv = pickle.loads(self.request.data)

        except pickle.UnpicklingError as error:
            self._log.debug("Un-pickleing failed.")
            return (False, error)

        self._cwd = cwd
        self._env = env
        self._argv = argv

        self._log.debug("Successfully parsed with `pickle`.")

        return (True, None)

    def _try_parse_with_json(
        self,
    ) -> tuple[Literal[True], None] | tuple[Literal[False], Exception]:
        self._log.debug("Trying to parse with `json`...")
        try:
            payload = json.loads(self.request.data.decode("utf-8"))

            self._cwd = payload["cwd"]
            self._env = payload["env"]
            self._argv = payload["argv"]

        except Exception as error:
            self._log.debug("JSON parsing failed.")
            return (False, error)

        self._log.debug("Successfully parsed with `json`.")

        return (True, None)

    def _parse_request(self):
        errors: list[tuple[str, Exception]] = []

        for parser in (self._try_parse_with_pickle, self._try_parse_with_json):
            match parser():
                case (True, _):
                    return
                case (False, error):
                    errors.append((parser.__name__, error))

        for name, error in errors:
            self._log.error("{} failed", name, exc_info=error)

        raise RuntimeError("All parse methods failed, see logs for details.")

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

        app = self.server.get_app()

        if "_ARGCOMPLETE" in self.env:
            self._log.debug("Setting up argcomplete...")

            with os.fdopen(self.request.fds[3], "wb") as output_stream:
                import argcomplete

                finder = argcomplete.CompletionFinder()
                finder(
                    app.parser,
                    exit_method=sys.exit,
                    output_stream=output_stream,
                )

        self._log.debug(f"Starting CLI...")
        self._response.exit_status = app.execute()

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
                    self._response.exit_status = i
                case str(s):
                    self._response.exit_status = 1

        except err.ReplaceProcess as replace_process:
            self._response.replace_process = ReplaceProcess(
                program=replace_process.program,
                args=replace_process.args,
                cwd=replace_process.cwd,
                env=replace_process.env,
            )

        except BaseException:
            message = "Error raised while handling request"

            # This will log to the _server_ log, as we're in the `clavier.srv`
            # namespace.
            self._log.exception(message)

            # We'd also like to try to tell the user something by writing to
            # their stderr
            try:
                with os.fdopen(self.request.fds[2], "w") as stderr:
                    console = Console(
                        file=stderr,
                        color_system="truecolor",
                        force_terminal=True,
                    )

                    console.print(message)
                    console.print_exception()
            except:
                pass

            self._response.exit_status = 1

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

            response_json = self._response.to_json()
            response_bytes = bytes(response_json, encoding="utf-8")
            response_size = len(response_bytes)

            self.request.socket.send(INT_STRUCT.pack(response_size))
            self.request.socket.send(response_bytes)

            self._log.debug(
                f"Sent response",
                response=self._response,
                json=response_json,
                size=response_size,
                bytes=response_bytes.hex(),
            )

            t_end_ns = monotonic_ns()
            handle_ms = (t_end_ns - t_start_ns) // MS_TO_NS
            total_ms = (t_end_ns - self.request.t_start_ns) // MS_TO_NS

            self._log.info(
                "Request handled",
                args=self.args,
                exit_status=self._response.exit_status,
                handle_ms=handle_ms,
                total_ms=total_ms,
            )
