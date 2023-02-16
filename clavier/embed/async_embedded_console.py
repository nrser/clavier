from argparse import Namespace
import asyncio
from dataclasses import dataclass
from pathlib import Path
import signal
from typing import Any, Callable, Mapping, Sequence
import sys
import readline
import shlex
import threading

from rich.console import Console

from clavier import arg_par, io, err, sesh, cfg, txt, req

from .embed_typings import FileDescriptorLike

RunTask = asyncio.Task[int]
RunFuture = asyncio.Future[int]


# @dataclass(frozen=True)
# class Run:
#     future: RunFuture
#     task: RunTask
#     handle: asyncio.Handle


class AsyncEmbeddedConsole(sesh.Sesh):
    _queue: asyncio.Queue[str]
    _read_task: asyncio.Task | None = None
    _dequeue_task: asyncio.Task | None = None
    _run_task: RunTask | None = None
    _run_future: RunFuture | None = None
    _run_handle: asyncio.Handle | None = None
    _file: FileDescriptorLike
    _signal_handlers: dict[int, Callable[[], object]]
    _out: Console
    _parser: arg_par.ArgumentParser
    _done: bool = False

    def __init__(
        self,
        pkg_name: str,
        description: str | Path,
        cmds: Any,
        prog_name: str | None = None,
        file: FileDescriptorLike = sys.stdin,
        signal_handlers: Mapping[int, Callable[[], object] | str] = {
            signal.SIGINT: "cancel",
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

        self._queue = asyncio.Queue()

        self._file = file
        self._signal_handlers = {
            n: getattr(self, h) if isinstance(h, str) else h
            for n, h in signal_handlers.items()
        }

        # TODO  Parameterize this?
        self._out = io.OUT
        self._tasks = set()

    def cancel(self) -> None:
        self._log.debug("Cancelling...")
        self._done = True

        if handle := self._run_handle:
            handle.cancel()

        for t in (self._dequeue_task, self._read_task, self._run_task):
            if t is not None and (not t.done()):
                t.cancel()

    def _read_input(self) -> None:
        try:
            self._log.debug("Reading input...")

            line = input()
            self._log.debug("Read input, putting in queue...", input=repr(line))

            self._read_task = asyncio.ensure_future(self._queue.put(line))

            self._log.debug("Done reading input.", read_task=self._read_task)
        except EOFError:
            self.cancel()

    async def loop(self):
        self._log.debug("Setting up loop...")

        prompt = f"{self._parser.prog} $ "

        ev = asyncio.get_event_loop()

        ev.add_reader(self._file, self._read_input)

        for signal_number, handler in self._signal_handlers.items():
            ev.add_signal_handler(signal_number, handler)

        try:
            self._log.debug("Entering loop...")

            self._out.print("Input command (enter `help` for help):")

            while not self._done:
                self._out.print(prompt, end="")
                self._log.debug("Executing queue.get...")
                self._dequeue_task = asyncio.ensure_future(self._queue.get())

                self._log.debug("Awaiting queue.get...")
                input = await self._dequeue_task
                argv = shlex.split(input.strip())

                self._log.debug(
                    "Got input from queue", input=repr(input), argv=argv
                )

                if argv:
                    await self.run(argv, event_loop=ev)

        except (asyncio.CancelledError, KeyboardInterrupt, EOFError):
            self._done = True
            self._log.debug("Interupted, exiting...", exc_info=sys.exc_info())

        finally:
            for signal_number in self._signal_handlers.keys():
                ev.remove_signal_handler(signal_number)

            ev.remove_reader(self._file)

    def run(
        self,
        argv: Sequence[str],
        *,
        event_loop: asyncio.AbstractEventLoop | None = None,
    ) -> asyncio.Future[int]:
        # Get the event loop if one wasn't provided
        ev = asyncio.get_event_loop() if event_loop is None else event_loop

        if self._run_future is not None:
            raise err.InternalError(
                "{}._run_future is already set".format(txt.fmt_type_of(self))
            )

        # Create a future that will be fulfilled with the exit status. We do
        # this because we want to execute the target in a new derived context,
        # which is possible via `asyncio.AbstractEventLoop.call_soon`, so we
        # will set a result on the future on the other side of that.
        self._run_future = ev.create_future()

        # Derive a context to execute the request in. We are already in the
        # context of the top-level `sesh.Sesh`, so this will copy that context.
        context = cfg.current.create_derived_context(
            src=txt.fmt(self.run),
            argv=tuple(argv),
        )

        self._run_handle = ev.call_soon(
            self._create_run_task, argv, context=context
        )

        return self._run_future

    def _create_run_task(self, argv: Sequence[str]) -> None:
        self._run_handle = None

        if self._run_task is not None:
            raise err.InternalError(
                f"already a run task running: {self._run_task!r}"
            )

        self._run_task = asyncio.create_task(self._execute_async(argv))
        self._run_task.add_done_callback(self._run_task_done)

    def _run_task_done(self, task: RunTask) -> None:
        if self._run_task is not task:
            raise err.InternalError(
                "`task` argument is not `{}._run_task`".format(
                    txt.fmt_type_of(self)
                )
            )

        self._run_task = None

        if self._run_future is None:
            raise err.InternalError(
                "no `()._run_future` to respond to".format(
                    txt.fmt_type_of(self)
                )
            )

        try:
            self._run_future.set_result(task.result())
        except BaseException as error:
            self._run_future.set_exception(error)

        self._run_future = None

    async def _execute_async(self, argv: Sequence[str]) -> int:
        try:
            request = self._parse(argv)
            return await self._handle_async(request)

        except BaseException as error:
            return self.handle_error(error)

    async def _handle_async(self, request: req.Req) -> int:
        with sesh.error_context(
            f"executing {txt.fmt(request.target)}", expect_system_exit=True
        ):
            if request.is_async:
                result = await request.target(**request.kwds)
            else:
                result = request.target(**request.kwds)

        view = result if isinstance(result, io.View) else io.View(result)

        return self._render_view(view)
