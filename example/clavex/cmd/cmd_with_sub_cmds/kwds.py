from textwrap import dedent
from typing import Any, Mapping

import splatlog
from clavier import arg_par, io
from rich.markdown import Markdown
from rich.pretty import Pretty
from rich.padding import Padding
from rich.rule import Rule

LOG = splatlog.get_logger(__name__)


def add_parser(subparsers: arg_par.Subparsers) -> None:
    parser = subparsers.add_parser(
        "kwds",
        target=run,
        help="A subcommand that accepts all `**kwds`",
    )


class View(io.View[tuple[str, Mapping[str, Any]]]):
    def __init__(self, message: str, kwds: Mapping[str, Any]):
        super().__init__((dedent(message), kwds))

    def render_rich(self) -> None:
        message, kwds = self.data
        self.print(Markdown(message))
        self.print(Padding(Rule("kwds"), (1, 0, 0, 0)))
        self.print(Padding(Pretty(kwds), (1, 4)))


def run(**kwds):
    return View(
        """
        Full Keyword Arguments when Parent Parser Is Command
        ========================================================================

        This command has a `(**kwds) -> ...` signature, which results in it
        receiving _all_ available arguments.

        You can see the default values for the parent command showing up — even
        though they are _not_ valid arguments for this command — due to
        how `argparse` works:

        All ancestor `argparse.ArgumentParser` have their defaults and all the
        defaults of their actions added to the `argparse.Namespace` as it
        "passes through" on it's way to the propper child parser.

        This is annoying, and leads to weird possibilities like

            clavex cmd-with-sub-cmds --list kwds

        that don't really do/mean anything, but for the moment it just sorta is
        what it is.
        """,
        kwds,
    )
