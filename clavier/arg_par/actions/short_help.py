from argparse import SUPPRESS, Namespace
from typing import TYPE_CHECKING, Any, Sequence

from .clavier_action import ClavierAction

if TYPE_CHECKING:
    from ..argument_parser import ArgumentParser


class ShortHelp(ClavierAction):
    """Like `argparse._HelpAction`"""

    def __init__(
        self,
        option_strings: Sequence[str],
        dest: str = SUPPRESS,
        default: Any = SUPPRESS,
        help: str | None = None,
    ):
        super().__init__(
            option_strings=option_strings,
            dest=dest,
            default=default,
            nargs=0,
            help=help,
        )

    def __call__(
        self,
        parser: "ArgumentParser",
        namespace: Namespace,
        values: str | Sequence[Any] | None,
        option_string: str | None = None,
    ):
        parser.print_help(short=True)
        parser.exit()
