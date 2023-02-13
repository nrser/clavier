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
        "panel.error.title": _S(color="red", bold=True),
        "panel.error.context": _S(italic=True, dim=True),
        "panel.error.subtitle": _S(color="red", dim=True),
        "panel.error.border": _S(color="red"),
    }
)


OUT = Console(theme=THEME, file=sys.stdout)
ERR = Console(theme=THEME, file=sys.stderr)

EMPTY = Group()
NEWLINE = Text("\n", end="")
