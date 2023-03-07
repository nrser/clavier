from argparse import Namespace
import asyncio
from dataclasses import dataclass
import os
from pathlib import Path
import signal
from typing import Any, Callable, Mapping, Sequence
import sys
import readline
import shlex
import threading

from rich.console import Console

from clavier import app, io, cfg, req, etc

RunTask = asyncio.Task[int]
RunFuture = asyncio.Future[int]


# @dataclass(frozen=True)
# class Run:
#     future: RunFuture
#     task: RunTask
#     handle: asyncio.Handle


class AsyncEmbeddedConsole(app.App):
    _signal_handlers: dict[int, Callable[[], object]]
    _out: Console

    # Threading
    _done_event: threading.Event
    _input_thread: threading.Thread
    _tasks: set[RunTask]
    _done_future: asyncio.Future[None]

    def __init__(
        self,
        pkg_name: str,
        description: str | Path,
        cmds: Any,
        prog_name: str | None = None,
        signal_handlers: Mapping[int, Callable[[], object] | str] = {
            signal.SIGINT: "stop",
        },
    ):
        super().__init__(
            pkg_name=pkg_name,
            description=description,
            cmds=cmds,
            prog_name=prog_name,
            autocomplete=False,
            setup_logging=False,
        )

        self._event_loop = asyncio.get_event_loop()
        self._done_event = threading.Event()
        self._input_thread = threading.Thread(
            name="input",
            target=self._read_input,
        )
        self._done_future = self._event_loop.create_future()

        self._signal_handlers = {
            n: getattr(self, h) if isinstance(h, str) else h
            for n, h in signal_handlers.items()
        }

        self._tasks = set()
        self._prompt = f"[{self._parser.prog}] $ "

    def stop(self) -> None:
        self._log.debug("Stopping...")

        # Async stuff...

        for task in self._tasks:
            if not task.done():
                self._log.debug("Canceling task...", task=task)

        if not self._done_future.done():
            self._log.debug("Fulfilling done future...")
            self._done_future.set_result(None)

        for signal_number in self._signal_handlers.keys():
            self._event_loop.remove_signal_handler(signal_number)

        # Threading stuff...

        self._log.debug("Setting done threading.Event...")
        self._done_event.set()

        self._log.debug("Closing sys.stdin...")
        sys.stdin.close()  # This doesn't seem to do _anything_ :/
        # os.close(sys.stdin.fileno()) # this breaks the attached terminal!!!

        # This didn't fail, but didn't do anything either...
        # self._log.debug("Writing \\n to stdin...")
        # stdin_fd_2 = os.dup(sys.stdin.fileno())
        # with os.fdopen(stdin_fd_2, "w") as stdin_2:
        #     stdin_2.write("\n")

        self._log.debug("Joining input thread...")
        self._input_thread.join()

        self._log.debug("All done!")

    def start(self) -> None:
        # NOTE  Right now, seems to work about the same _without_ these
        #       rigged...
        for singal_number, handler in self._signal_handlers.items():
            self._event_loop.add_signal_handler(singal_number, handler)

        self._input_thread.start()

    async def run(self) -> None:
        self.start()

        try:
            await self._done_future
        except (asyncio.CancelledError, KeyboardInterrupt, EOFError) as error:
            self._log.debug(
                "Received interupt while waiting to be done",
                error_type=etc.txt.fmt_type_of(error),
            )
            self.stop()

    def _read_input(self) -> None:
        try:
            while not self._done_event.is_set():
                self._log.debug("Reading input...")

                line = input(self._prompt)

                if not line:
                    continue

                self._log.debug(
                    "Read input, scheduling event loop callback...",
                    input=repr(line),
                )

                context = cfg.current.create_derived_context(
                    name="run",
                    input=line,
                )

                self._event_loop.call_soon_threadsafe(
                    self._handle_input, line, context=context
                )

                self._log.debug("Done reading input.")

        except (asyncio.CancelledError, KeyboardInterrupt, EOFError) as error:
            self._log.debug(
                "Received interupt while reading input (in thread)",
                error_type=etc.txt.fmt_type_of(error),
            )
            self._event_loop.call_soon_threadsafe(self.stop)

    def _handle_input(self, input: str) -> None:
        try:
            argv = shlex.split(input)

            task = self._event_loop.create_task(
                self._async_execute(argv), name=f"run {input!r}"
            )

            self._tasks.add(task)
            task.add_done_callback(self._tasks.discard)

        except (asyncio.CancelledError, KeyboardInterrupt, EOFError) as error:
            self._log.debug(
                "Received interupt while handing input",
                error_type=etc.txt.fmt_type_of(error),
            )
            self.stop()

        except BaseException:
            self._log.exception("Failed to handle input", input=repr(input))

    async def _async_execute(self, argv: Sequence[str]) -> int:
        try:
            request = self._parse(argv)
            return await self._handle_async(request)

        except BaseException as error:
            return self.handle_error(error)

    async def _handle_async(self, request: req.Req) -> int:
        with app.error_context(
            f"executing {etc.txt.fmt(request.target)} (async)",
            expect_system_exit=True,
        ):
            if request.is_async:
                result = await request.target(**request.kwds)
            else:
                result = request.target(**request.kwds)

        view = result if isinstance(result, io.View) else io.View(result)

        return self._render_view(view)
