from argparse import Namespace
import asyncio
from collections import defaultdict
import signal
from typing import Any, Callable, Mapping, Protocol, TypeAlias
import sys
from inspect import getdoc, signature, unwrap

import splatlog
from rich.console import Console

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

    async def _run(self, args: Namespace):
        if not hasattr(args, "__target__"):
            self._log.error("Missing __target__ arg", args=args)
            raise err.InternalError("Missing __target__ arg")

        # Form the call keyword args -- start with a dict of the parsed arguments
        kwds = {**args.__dict__}
        # Remove the global argument names
        for key in self._parser.action_dests():
            if key in kwds:
                del kwds[key]
        # And the `__target__` that holds the target function
        del kwds["__target__"]

        # Resolve default getters
        _resolve_default_getters(kwds)

        # pylint: disable=broad-except
        try:
            if asyncio.iscoroutinefunction(unwrap(args.__target__)):
                result = await args.__target__(**kwds)
            else:
                result = args.__target__(**kwds)
        except (asyncio.CancelledError, KeyboardInterrupt):
            raise
        except Exception as error:
            if getattr(args, "backtrace", None):
                self._log.error(
                    "[holup]Terminating due to unhandled exception[/holup]...",
                    exc_info=True,
                )
            else:
                self._log.error(
                    "Command [uhoh]FAILED[/uhoh].\n\n"
                    f"{type(error).__name__}: {error}\n\n"
                    "Add `--backtrace` to print stack.",
                )
            return

        if not isinstance(result, io.View):
            result = io.View(result)

        try:
            result.render(args.output)
        except (asyncio.CancelledError, KeyboardInterrupt):
            raise
        except Exception as error:
            if getattr(args, "backtrace", None):
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
            return

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

                if argv:
                    try:
                        args = self._parser.parse_args(argv)
                    except SystemExit as error:
                        pass
                    else:
                        await self._run(args)

        except (asyncio.CancelledError, KeyboardInterrupt):
            self._done = True
            self._log.debug("Interupted, exiting...", exc_info=sys.exc_info())

        finally:
            for signal_number in self._signal_handlers.keys():
                ev.remove_signal_handler(signal_number)

            ev.remove_reader(self._file)
