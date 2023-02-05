from __future__ import annotations
from inspect import signature
from typing import Iterable, TYPE_CHECKING
import argparse
from pathlib import Path
import os
from textwrap import dedent
import sys

from rich.console import Console
import splatlog

from clavier import dyn

from .arg_par_helpers import invoke_hook, DEFAULT_HOOK_NAMES

if TYPE_CHECKING:
    from .argument_parser import ArgumentParser


class Subparsers(argparse._SubParsersAction):
    """
    Extended to use help as description if the later is missing and handle
    passing-down `hook_names`.
    """

    hook_names: Iterable[str]

    def __init__(self, *args, hook_names=DEFAULT_HOOK_NAMES, **kwds):
        super().__init__(*args, **kwds)
        self.hook_names = hook_names

    def add_parser(self, name, **kwds) -> "ArgumentParser":
        if "help" in kwds and "description" not in kwds:
            kwds["description"] = kwds["help"]

        # This is really just to make the type checker cool wit it
        kwds["hook_names"] = self.hook_names

        return super().add_parser(name, **kwds)

    def add_children(
        self, module__name__: str, module__path__: Iterable[str]
    ) -> None:
        for module in dyn.children_modules(module__name__, module__path__):
            invoke_hook(module, self.hook_names, self)
