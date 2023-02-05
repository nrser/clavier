"""The `Sesh` class."""

from __future__ import annotations
import asyncio
from inspect import unwrap
from typing import (
    Any,
    Dict,
    Union,
    Optional,
)
from pathlib import Path
import argparse
import sys

import splatlog
from rich.console import Console

from . import err, io, cfg
from .arg_par import ArgumentParser

_LOG = splatlog.get_logger(__name__)


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
def _resolve_default_getters(values: Dict[str, Any]) -> None:
    for key in values:
        if callable(values[key]):
            values[key] = values[key](
                **{k: v for k, v in values.items() if not callable(v)}
            )


class Sesh:
    """
    A CLI app session
    """

    _log = splatlog.LoggerProperty()

    pkg_name: str
    _parser: ArgumentParser | None = None
    _args: argparse.Namespace | None = None
    _init_cmds: Any

    def __init__(
        self: Sesh,
        pkg_name: str,
        description: Union[str, Path],
        cmds: Any,
    ):
        self.pkg_name = pkg_name
        self.description = description
        self._init_cmds = cmds

    @property
    def args(self):
        if self._args is None:
            raise err.InternalError("Must `parse()` first to populate `args`")
        return self._args

    @property
    def init_cmds(self) -> Any:
        return self._init_cmds

    @property
    def parser(self) -> ArgumentParser:
        if self._parser is None:
            raise err.InternalError("Must `setup()` first to populate `parser`")
        return self._parser

    def get_setting(self, name: str, default=None) -> Any:
        if self._args is not None:
            return getattr(self._args, name)

        prog_key = cfg.Key(self.pkg_name, name)
        if prog_key in cfg.CFG:
            return cfg.CFG[prog_key]

        self_key = cfg.Key(cfg.SELF_ROOT_KEY, name)
        if self_key in cfg.CFG:
            return cfg.CFG[self_key]

        return default

    def is_backtracing(self) -> bool:
        return bool(self.get_setting("backtrace"))
        # return (
        #     self.get_arg("backtrace", False)
        #     or (
        #         splatlog.get_logger(self.pkg_name).getEffectiveLevel()
        #         is splatlog.DEBUG
        #     )
        #     or self.env("backtrace", False)
        # )

    def setup(
        self,
        verbosity: None | splatlog.Verbosity = None,
        autocomplete: bool = True,
        prog: str | None = None,
    ) -> Sesh:
        if verbosity is None:
            verbosity = self.get_setting("verbosity", 0)

        console = Console(
            file=sys.stderr,
            color_system="truecolor",
            force_terminal=True,
        )

        splatlog.setup(
            console=console,
            verbosity_levels={
                self.pkg_name: (
                    (0, splatlog.WARNING),
                    (1, splatlog.INFO),
                    (2, splatlog.DEBUG),
                ),
                splatlog.root_name(__package__): (
                    (0, splatlog.WARNING),
                    (3, splatlog.INFO),
                    (4, splatlog.DEBUG),
                ),
            },
            verbosity=verbosity,
        )

        self._parser = ArgumentParser.create(
            self.description,
            self.init_cmds,
            autocomplete=autocomplete,
            prog=prog,
        )

        return self

    def parse(self, *args, **kwds) -> Sesh:
        self._args = self.parser.parse_args(*args, **kwds)

        splatlog.set_verbosity(self._args.verbose)

        self._log.debug("Parsed arguments", **self._args.__dict__)
        return self

    def run(self) -> int:
        if not hasattr(self.args, "__target__"):
            self._log.error("Missing __target__ arg", self_args=self.args)
            raise err.InternalError("Missing __target__ arg")

        # Form the call keyword args -- start with a dict of the parsed arguments
        kwds = {**self.args.__dict__}
        # Remove the global argument names
        for key in self.parser.action_dests():
            if key in kwds:
                del kwds[key]
        # And the `__target__` that holds the target function
        del kwds["__target__"]

        # Resolve default getters
        _resolve_default_getters(kwds)

        # pylint: disable=broad-except
        try:
            if asyncio.iscoroutinefunction(unwrap(self.args.__target__)):
                result = asyncio.run(self.args.__target__(**kwds))
            else:
                result = self.args.__target__(**kwds)
        except KeyboardInterrupt:
            return 0
        except Exception as error:
            if self.is_backtracing():
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
            return 1

        if not isinstance(result, io.View):
            result = io.View(result)

        try:
            result.render(self.args.output)
        except KeyboardInterrupt:
            return 0
        except Exception as error:
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
            return 1

        return result.return_code

    # F'ing doc generator can't cope with anything named 'exec' due to using
    # `lib2to3` to parse (`exec` was a keyword in Python 2):
    #
    # https://bugs.python.org/issue44259
    #
    def execute(self):
        sys.exit(self.run())
