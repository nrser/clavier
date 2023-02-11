from argparse import Namespace
import asyncio
from collections import defaultdict
from contextlib import contextmanager
import signal
from typing import Any, Callable, Mapping, Protocol, TypeAlias
import sys
from inspect import getdoc, signature, unwrap

import splatlog
from rich.console import Console
from rich.panel import Panel
from rich.style import Style
from rich.padding import Padding

from clavier import arg_par, io, err

from .embed_typings import FileDescriptorLike


# NOTE  This took very little to write, and works for the moment, but it relies
#       on a bunch of sketch things (beyond being hard to read and understand
#       quickly):
#
#       1.  All values that are callable are considered default getters.
#
#       2.  The order that the arguments were added to the `ArgumentParser`
#           is the order we end up iterating in here.
#
#           Otherwise there's no definition of the iter-dependency chains.
#
#       3.  Hope nothing else messes with the `values` reference while we're
#           mutating it.
#
def _resolve_default_getters(values: dict[str, Any]) -> None:
    for key in values:
        if callable(values[key]):
            values[key] = values[key](
                **{k: v for k, v in values.items() if not callable(v)}
            )


class AsyncEmbeddedConsole:
    _log = splatlog.LoggerProperty()

    _queue: asyncio.Queue[str]
    _read_task: asyncio.Task | None = None
    _dequeue_task: asyncio.Task | None = None
    _file: FileDescriptorLike
    _signal_handlers: dict[int, Callable[[], object]]
    _out: Console
    _parser: arg_par.ArgumentParser
    _done: bool = False
    _args: Namespace | None = None

    def __init__(
        self,
        parser: arg_par.ArgumentParser,
        file: FileDescriptorLike = sys.stdin,
        signal_handlers: Mapping[int, Callable[[], object] | str] = {
            signal.SIGINT: "cancel"
        },
    ):
        self._queue = asyncio.Queue()

        self._parser = parser
        self._file = file
        self._signal_handlers = {
            n: getattr(self, h) if isinstance(h, str) else h
            for n, h in signal_handlers.items()
        }

        # TODO  Parameterize this!
        self._out = Console(file=sys.stdout, theme=io.THEME)

    def cancel(self) -> None:
        self._log.debug("Cancelling...")
        self._done = True

        for t in (self._dequeue_task, self._read_task):
            if t is not None and (not t.done()):
                t.cancel()

    def _read_input(self) -> None:
        self._log.debug("Reading input...")

        input = sys.stdin.readline()
        self._log.debug("Read input, putting in queue...", input=repr(input))

        self._read_task = asyncio.ensure_future(self._queue.put(input))

        self._log.debug("Done reading input.", read_task=self._read_task)

    async def loop(self):
        self._log.debug("Setting up loop...")

        ev = asyncio.get_event_loop()

        ev.add_reader(self._file, self._read_input)

        for signal_number, handler in self._signal_handlers.items():
            ev.add_signal_handler(signal_number, handler)

        try:
            self._log.debug("Entering loop...")

            while not self._done:
                self._out.print("Input command (enter `help` for help):")

                self._log.debug("Executing queue.get...")
                self._dequeue_task = asyncio.ensure_future(self._queue.get())

                self._log.debug("Awaiting queue.get...")
                input = await self._dequeue_task
                argv = input.strip().split()

                self._log.debug(
                    "Got input from queue", input=repr(input), argv=argv
                )

                await self.run(argv)

        except (asyncio.CancelledError, KeyboardInterrupt):
            self._done = True
            self._log.debug("Interupted, exiting...", exc_info=sys.exc_info())

        finally:
            for signal_number in self._signal_handlers.keys():
                ev.remove_signal_handler(signal_number)

            ev.remove_reader(self._file)

    # The `Sesh`` stuff
    # ========================================================================
    #
    # Things that overlap with `Sesh`, and ideally would be consolidated largely
    # or completely.
    #

    def is_backtracing(self) -> bool:
        if self._args is None:
            return False
        return getattr(self._args, "backtrace", False)

    async def run(self, argv: list[str]) -> None:
        try:
            await self._run_internal(argv)

        except (asyncio.CancelledError, KeyboardInterrupt) as error:
            # Bubble this up so the process can exit
            #
            self._log.debug("Interupted, re-raising", error=error)
            raise

        except err.ParserExit as error:
            self._handle_parser_exit(error)

        except SystemExit as error:
            level = splatlog.DEBUG if error.code == 0 else splatlog.ERROR

            self._log.log(
                level,
                "System exit during arg parsing !!!",
                parsed_args=self._args,
                code=error.code,
                exc_info=True,
            )

        except err.InternalError as error:
            # Internal error (in code / logic) are always printed,
            # regardless of backtrace setting. It's a developer tool afterall,
            # and someone needs to fix it.
            #
            self._log.exception("`run` encountered an internal error")

        except Exception as error:
            # Catch-all
            #
            if self.is_backtracing():
                self._log.error(
                    "[holup]Terminting due to view rendering error[/holup]...",
                    exc_info=True,
                )
            else:
                self._log.error(
                    "Command [uhoh]FAILED[/uhoh].\n\n"
                    f"{type(error).__name__}: {error}\n\n"
                    "Add `--backtrace` to print stack.",
                )

        self._args = None

    def _handle_parser_exit(self, error: err.ParserExit) -> None:
        # NOTE  Single call site at this time (2023-02-04); factored-out into
        #       a separate method to make caller (`run``) easier to read.
        #
        self._log.debug(
            "Handling `ParserExit`...",
            status=error.status,
            message=error.message,
        )

        if error.status == 0:
            if message := error.message:
                io.OUT.print(message)
            return

        is_bt = self.is_backtracing()

        if is_bt:
            self._log.exception(
                "Failed to parse arguments",
                status=error.status,
                message=error.message,
            )

        message = "(no message)" if (not error.message) else error.message

        io.ERR.print("Failed to parse arguments", style=Style(italic=True))
        io.ERR.print(
            Padding(
                Panel(
                    message,
                    title="ERROR",
                    border_style=Style(color="red"),
                    padding=(1, 2),
                ),
                (1, 0),
            )
        )

        if not is_bt:
            io.ERR.print(
                "Enabled backtrace logging with `--backtrace` flag",
                style=Style(italic=True),
            )

    async def _run_internal(self, argv: list[str]) -> None:
        if not argv:
            # Ignore empty lines (user spamming return key)
            return

        args = self._parser.parse_args(argv)

        # Set here and unset in surrounding `run` so that the exception handlers
        # there have access to it.
        self._args = args

        # Form the call keyword args -- start with a dict of the parsed arguments
        kwds = {**args.__dict__}

        # Remove the global argument names
        for key in self._parser.action_dests():
            if key in kwds:
                del kwds[key]

        # And the `__target__` that holds the target function
        try:
            target = kwds.pop("__target__")
        except KeyError:
            raise err.InternalError("Missing __target__ arg")

        # Resolve default getters
        _resolve_default_getters(kwds)

        if asyncio.iscoroutinefunction(unwrap(target)):
            result = await target(**kwds)
        else:
            result = target(**kwds)

        if not isinstance(result, io.View):
            result = io.View(result)

        result.render(args.output)