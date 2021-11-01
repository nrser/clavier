from __future__ import annotations
from typing import Callable, Iterable, Optional
import argparse
from pathlib import Path
import os
from textwrap import dedent

from rich.console import Console
from argcomplete import autocomplete
import splatlog as logging

from . import io, dyn, err
from .rich_fmt import RichFormatter
from .etc import find

DEFAULT_HOOK_NAMES = (
    # Preferred name (v0.1.3+)
    "add_parser",
    # Legacy name (v0.1.2 and prior)
    "add_to",
)


class HelpErrorView(io.ErrorView):
    def render_rich(self):
        io.render_to_console(self.data.format_rich_help())

    def render_json(self):
        raise err.UserError("Help not available as JSON")


class Subparsers(argparse._SubParsersAction):
    """\
    Extended to use help as description if the later is missing and handle
    passing-down `hook_names`.
    """

    hook_names: Iterable[str]

    def __init__(self, *args, hook_names=DEFAULT_HOOK_NAMES, **kwds):
        super().__init__(*args, **kwds)
        self.hook_names = hook_names

    def add_parser(self, name, **kwds) -> ArgumentParser:
        if "help" in kwds and "description" not in kwds:
            kwds["description"] = kwds["help"]
        return super().add_parser(name, hook_names=self.hook_names, **kwds)

    def add_children(self, module__name__, module__path__):
        for module in dyn.children_modules(module__name__, module__path__):
            _invoke_hook(module, self.hook_names, self)


THook = Callable[[Subparsers], None]


def _find_hook_name(obj: object, hook_names: Iterable[str]) -> Optional[str]:
    return find(lambda hook_name: hasattr(obj, hook_name), hook_names)


def _has_hook(obj: object, hook_names: Iterable[str]) -> bool:
    return _find_hook_name(obj, hook_names) is not None


def _invoke_hook(
    obj: object, hook_names: Iterable[str], subparsers: Subparsers
) -> None:
    if name := _find_hook_name(obj, hook_names):
        return getattr(obj, name)(subparsers)


class ArgumentParser(argparse.ArgumentParser):
    @classmethod
    def create(cls, description, cmds, *, hook_names=DEFAULT_HOOK_NAMES):
        if isinstance(description, Path):
            with description.open("r") as file:
                description = file.read()
        elif isinstance(description, str):
            pass
        else:
            raise TypeError("Expected `pathlib.Path` or `str`")

        parser = cls(
            description=description,
            notes=dedent(
                """\
                You can run

                    eval "$(register-python-argcomplete %(prog)s)"

                in your bash shell to enable tab-completion.
                """
            ),
            hook_names=hook_names,
        )

        subparsers = parser.add_subparsers(help="Select a command")

        # Figure out what was passed for the cmds...
        if _has_hook(cmds, hook_names):
            # An object that has one of the hook methods, call that
            _invoke_hook(cmds, hook_names, subparsers)
        elif isinstance(cmds, Iterable):
            # An iterable,
            for cmd in cmds:
                _invoke_hook(cmd, hook_names, subparsers)
        else:
            # It must be a hook itself (legacy form)
            cmds(subparsers)

        autocomplete(parser)
        return parser

    def __init__(
        self,
        *args,
        target=None,
        view=io.View,
        notes=None,
        hook_names=DEFAULT_HOOK_NAMES,
        **kwds,
    ):
        super().__init__(*args, formatter_class=RichFormatter, **kwds)

        self.notes = notes
        self.hook_names = hook_names
        self.register("action", "parsers", Subparsers)

        if target is None:
            self.set_target(self.no_target)
        else:
            self.set_target(target)

        self.add_argument(
            "-B",
            "--backtrace",
            action="store_true",
            help="Print backtraces on error",
        )

        # self.add_argument(
        #     '--log',
        #     type=str,
        #     help="File path to write logs to.",
        # )

        self.add_argument(
            "-V",
            "--verbose",
            action="count",
            help="Make noise.",
        )

        self.add_argument(
            "-O",
            "--output",
            default=view.DEFAULT_FORMAT,
            help=view.help(),
        )

    def add_subparsers(self, **kwds) -> Subparsers:
        kwds["hook_names"] = self.hook_names
        return super().add_subparsers(**kwds)

    def no_target(self):
        return HelpErrorView(self)

    def env_var_name(self, name):
        return self.prog.upper() + "_" + name.upper()

    def env(self, name, default=None):
        return os.environ.get(self.env_var_name(name), default)

    def is_backtracing(self, pkg_name, args):
        return (
            args.backtrace
            or logging.get_pkg_logger(pkg_name).level is logging.DEBUG
            or self.env("backtrace", False)
        )

    def set_target(self, target):
        self.set_defaults(__target__=target)

    def action_dests(self):
        return [
            action.dest
            for action in self._actions
            if action.dest != argparse.SUPPRESS
        ]

    def add_children(self, module__name__, module__path__):
        self.add_subparsers().add_children(module__name__, module__path__)

    def format_rich_help(self):
        formatter = self._get_formatter()

        # usage
        formatter.add_usage(
            self.usage, self._actions, self._mutually_exclusive_groups
        )

        # description
        formatter.start_section("description")
        formatter.add_text(self.description)
        formatter.end_section()

        # positionals, optionals and user-defined groups
        for action_group in self._action_groups:
            formatter.start_section(action_group.title)
            formatter.add_text(action_group.description)
            formatter.add_arguments(action_group._group_actions)
            formatter.end_section()

        if self.notes is not None:
            formatter.start_section("additional notes")
            formatter.add_text(self.notes)
            formatter.end_section()

        # epilog
        formatter.add_text(self.epilog)

        # determine help from format above
        return formatter.format_rich()

    def format_help(self) -> str:
        return io.render_to_string(self.format_rich_help())

    def print_help(self, file=None):
        if file is None:
            console = io.OUT
        elif isinstance(file, Console):
            console = file
        else:
            console = Console(file=file)
        console.print(self.format_rich_help())
