import sys

from rich.console import Console, Group
from rich.theme import Theme
from rich.text import Text
from rich.style import Style as _S

THEME = Theme(
    {
        "good": "bold green",
        "yeah": "bold green",
        "on": "bold green",
        "bad": "bold red",
        "uhoh": "bold red",
        "holup": "bold yellow",
        "todo": "bold yellow",
        "h": "bold blue",
        "rule.h": "blue",
        # Error Panel
        # ====================================================================
        "panel.error.title": _S(color="red", bold=True),
        "panel.error.context": _S(italic=True, dim=True),
        "panel.error.subtitle": _S(color="red", dim=True),
        "panel.error.border": _S(color="red"),
        # Help (On-Demand Documentation)
        # ====================================================================
        #
        # Actions (Arguments, Options and Subcommands)
        # --------------------------------------------------------------------
        "help.action.info.name": _S(color="white", italic=True, dim=True),
        "help.action.str_value": _S(color="green"),
        # "help.action.label": _S(bgcolor="#282C34"),
        "help.action.label.name": _S(
            color="white",
            dim=True,
            italic=True,
        ),
        ### Invocation ###
        "help.action.invocation.flag": _S(color="yellow", bold=True),
        "help.action.invocation.metavar": _S(color="red", bold=True),
        "help.header.text": _S(color="red", bold=True),
        "help.header.rule": _S(color="#272822"),
        "prog": _S(bgcolor="cyan", color="white", bold=True),
        #
        # ====================================================================
        "path.part": _S(color="green"),
        "path.sep": _S(color="magenta"),
        "path.cont": _S(color="white", dim=True),
    }
)

OUT = Console(theme=THEME, file=sys.stdout)
ERR = Console(theme=THEME, file=sys.stderr)

EMPTY = Group()
NEWLINE = Text("\n", end="")
