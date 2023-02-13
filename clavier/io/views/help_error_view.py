from typing import TYPE_CHECKING
from clavier import err

from rich.console import Console

from ..io_consts import OUT, ERR
from ..view import View

if TYPE_CHECKING:
    from clavier.arg_par import ArgumentParser


class HelpErrorView(View["ArgumentParser"]):
    def __init__(
        self,
        data: "ArgumentParser",
        *,
        exit_status: int = 1,
        out: Console = OUT,
        err: Console = ERR,
    ):
        super().__init__(data, exit_status=exit_status, out=out, err=err)

    def render_rich(self):
        if rich_help := self.data.format_rich_help():
            self.out.print(rich_help)

    def render_json(self):
        raise err.UserError("Help not available as JSON")
