from __future__ import annotations
from typing import Iterable, TYPE_CHECKING, Sequence
import argparse

import splatlog
from rich.repr import RichReprResult

from clavier import dyn

from .arg_par_helpers import invoke_hook, DEFAULT_HOOK_NAMES
from .actions import ClavierAction

if TYPE_CHECKING:
    from .argument_parser import ArgumentParser, Setting


class Subparsers(argparse._SubParsersAction):
    """
    Extended to use help as description if the later is missing and handle
    passing-down `hook_names`.
    """

    _log = splatlog.LoggerProperty()

    parent_name: str
    hook_names: Iterable[str]
    propagated_actions: tuple[ClavierAction, ...]

    def __init__(
        self,
        *args,
        parent_name: str = "(unknown)",
        hook_names: Sequence[str] = DEFAULT_HOOK_NAMES,
        propagated_actions: tuple[ClavierAction, ...] = (),
        metavar: str | tuple[str, ...] | None = None,
        **kwds,
    ):
        if metavar is None:
            metavar = "COMMAND"

        super().__init__(*args, metavar=metavar, **kwds)
        self.parent_name = parent_name
        self.hook_names = hook_names
        self.propagated_actions = propagated_actions

    @property
    def _splatlog_self_(self) -> str:
        return f"Subparsers(parent_name={self.parent_name!r})"

    def add_parser(self, name: str, **kwds) -> "ArgumentParser":
        self._log.debug("Adding parser...", name=name, kwds=kwds)

        if "help" in kwds and "description" not in kwds:
            kwds["description"] = kwds["help"]

        # This is really just to make the type checker cool wit it
        kwds["hook_names"] = self.hook_names

        parser = super().add_parser(name, **kwds)

        propagated_actions = self.propagated_actions

        self._log.debug(
            "Propagating actions to {!r} parser...",
            name,
            propagated_actions=propagated_actions,
        )

        for action in propagated_actions:
            parser._add_action(action)

        return parser

    def add_children(
        self, module__name__: str, module__path__: Iterable[str]
    ) -> None:
        for module in dyn.children_modules(module__name__, module__path__):
            invoke_hook(module, self.hook_names, self)

    def __rich_repr__(self) -> RichReprResult:
        # Subparsers(option_strings=[], dest='==SUPPRESS==', nargs='A...',
        #   const=None, default=None, type=None, choices={}, help='Select a
        #   command', metavar=None)

        yield "option_strings", self.option_strings
        yield "dest", self.dest
        yield "nargs", self.nargs, None
        yield "metavar", self.metavar, None
        yield "type", self.type, None
        yield "default", self.default, None
        yield "const", self.const, None
        yield "choices", self.choices, None
        yield "required", self.required, False
        yield "help", self.help, None
