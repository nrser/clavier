from typing import TYPE_CHECKING
from clavier import io, err

from rich.console import Console

if TYPE_CHECKING:
    from ..argument_parser import ArgumentParser


class HelpErrorView(io.View["ArgumentParser"]):
    def __init__(
        self,
        data: "ArgumentParser",
        *,
        return_code: int = 1,
        out: Console = io.OUT,
        err: Console = io.ERR,
    ):
        super().__init__(data, return_code=return_code, out=out, err=err)

    def render_rich(self):
        io.render_to_console(self.data.format_rich_help())

    def render_json(self):
        raise err.UserError("Help not available as JSON")
