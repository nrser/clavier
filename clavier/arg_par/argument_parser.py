from __future__ import annotations
from dataclasses import dataclass
from inspect import signature
from typing import Any, Callable, Iterable, NoReturn, Sequence, TypeGuard, cast
import argparse
from pathlib import Path
import os
from gettext import gettext as _
from clavier.arg_par.actions import ClavierAction, StoreSetting

from rich.console import Console
import splatlog
from splatlog.lib.text import fmt, fmt_type_of

from clavier import io, err, cfg, txt

from .rich_help_formatter import RichHelpFormatter

from .arg_par_helpers import DEFAULT_HOOK_NAMES, has_hook, invoke_hook
from .subparsers import Subparsers


Target = Callable[..., Any]

TARGET_NAME = "__target__"


def is_target(value: Any) -> TypeGuard[Target]:
    return isinstance(value, Callable)


def check_target(value: Any) -> Target:
    if is_target(value):
        return value

    raise TypeError(
        f"{TARGET_NAME!r} value is not `typing.Callable`; "
        f"found {fmt_type_of(value)}: {fmt(value)}"
    )


@dataclass(frozen=True)
class Setting:
    key: cfg.Key
    flags: tuple[str, ...]
    action: type[argparse.Action] | str | None = None
    propagate: bool = False
    help: str | None = None


class ArgumentParser(argparse.ArgumentParser):
    _log = splatlog.LoggerProperty()

    @classmethod
    def create(
        cls,
        description,
        cmds,
        *,
        prog: str | None = None,
        hook_names=DEFAULT_HOOK_NAMES,
        autocomplete: bool = True,
        **kwds,
    ):
        if isinstance(description, Path):
            with description.open("r") as file:
                description = file.read()
        elif isinstance(description, str):
            pass
        else:
            raise TypeError("Expected `pathlib.Path` or `str`")

        parser = cls(
            prog=prog,
            description=description,
            # notes=dedent(
            #     """\
            #     You can run
            #         eval "$(register-python-argcomplete %(prog)s)"
            #     in your bash shell to enable tab-completion.
            #     """
            # ),
            hook_names=hook_names,
            **kwds,
        )

        subparsers = parser.add_subparsers(help="Select a command")

        # Figure out what was passed for the cmds...
        if has_hook(cmds, hook_names):
            # An object that has one of the hook methods, call that
            invoke_hook(cmds, hook_names, subparsers)
        elif isinstance(cmds, Iterable):
            # An iterable,
            for cmd in cmds:
                invoke_hook(cmd, hook_names, subparsers)
        else:
            # It must be a hook itself (legacy form)
            cmds(subparsers)

        if autocomplete:
            import argcomplete

            argcomplete.autocomplete(parser)

        return parser

    notes: str | None
    hook_names: Sequence[str]
    settings: tuple[Setting, ...]

    def __init__(
        self,
        *args,
        target=None,
        view: type[io.View] = io.View,  # TODO What was this for?
        notes: str | None = None,
        hook_names: Sequence[str] = DEFAULT_HOOK_NAMES,
        settings: Iterable[Setting] = (),
        **kwds,
    ):
        super().__init__(*args, formatter_class=RichHelpFormatter, **kwds)

        self.notes = notes
        self.hook_names = hook_names
        self.settings = tuple(settings)
        self.register("action", "parsers", Subparsers)

        if target is None:
            self.set_target(self.no_target)
        else:
            self.set_target(target)

        for setting in settings:
            self.add_setting(setting)

    def add_setting(self, setting: Setting) -> StoreSetting:
        wrapped_action = self._registry_get(
            "action", setting.action, setting.action
        )

        action = self.add_argument(
            *setting.flags,
            action=StoreSetting,
            key=setting.key,
            wrapped_action=wrapped_action,
            propagate=setting.propagate,
            help=setting.help,
        )

        if not isinstance(action, StoreSetting):
            raise err.ReturnTypeError(
                function=self.add_argument,
                expected_type=StoreSetting,
                return_value=action,
                when="called with `action={return_type}`",
            )

        return action

    def add_subparsers(self, **kwds) -> Subparsers:
        kwds["hook_names"] = self.hook_names

        kwds["propagated_actions"] = [
            a
            for a in self._actions
            if isinstance(a, ClavierAction) and a.propagate
        ]

        subparsers = super().add_subparsers(**kwds)

        if not isinstance(subparsers, Subparsers):
            raise err.ReturnTypeError(
                function=self.add_argument,
                expected_type=StoreSetting,
                return_value=subparsers,
                when="called with `action={expected_type}`",
            )

        return subparsers

    def no_target(self):
        return io.views.HelpErrorView(self)

    def env_var_name(self, name):
        return self.prog.upper() + "_" + name.upper()

    def env(self, name, default=None):
        return os.environ.get(self.env_var_name(name), default)

    def get_target(self) -> Target:
        # same as: `return self.get_default("__target__")`
        return check_target(self._defaults[TARGET_NAME])

    def set_target(self, target: Target) -> None:
        # same as: `self.set_defaults(__target__=target)`
        self._defaults["__target__"] = check_target(target)

        self.set_defaults(
            **{
                parameter.name: parameter.default
                for parameter in signature(target).parameters.values()
                if parameter.default is not parameter.empty
            }
        )

    def action_dests(self):
        return [
            action.dest
            for action in self._actions
            if action.dest != argparse.SUPPRESS
        ]

    def add_children(self, module__name__, module__path__):
        self.add_subparsers().add_children(module__name__, module__path__)

    def _get_formatter(self) -> RichHelpFormatter:
        formatter = super()._get_formatter()
        if not isinstance(formatter, RichHelpFormatter):
            raise TypeError(
                "expected formatter to be a {}, found a {}: {}".format(
                    splatlog.lib.fmt(RichHelpFormatter),
                    splatlog.lib.fmt_type_of(formatter),
                    splatlog.lib.fmt(formatter),
                )
            )
        return formatter

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

        # positional, optional and user-defined groups
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

    def error(self, message: str) -> NoReturn:
        """Prints a usage message incorporating the message to stderr and
        exits.

        If you override this in a subclass, it should not return -- it
        should either exit or raise an exception.
        """
        # self.print_usage(sys.stderr)
        # args = {"prog": self.prog, "message": message}
        self.exit(2, _(message))

    def exit(self, status: int = 0, message: str | None = None) -> NoReturn:
        raise err.ParserExit(status, message)
