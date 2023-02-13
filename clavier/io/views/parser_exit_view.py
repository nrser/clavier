from dataclasses import dataclass
import json
from typing import TYPE_CHECKING
from clavier import err

from rich.console import Console, RenderableType
from rich.text import TextType
import splatlog
from splatlog.json.default_handlers import TRACEBACK_HANDLER

from ..io_consts import NEWLINE, OUT, ERR
from .sesh_error_view import SeshErrorView

if TYPE_CHECKING:
    from clavier.sesh import Sesh


class ParserExitView(SeshErrorView[err.ParserExit]):
    _log = splatlog.LoggerProperty()

    def __init__(
        self,
        sesh: "Sesh",
        error: err.ParserExit,
        context: str | None,
        out: Console = OUT,
        err: Console = ERR,
    ):
        super().__init__(
            sesh=sesh,
            error=error,
            context=context,
            exit_status=error.status,
            out=out,
            err=err,
        )

    def get_title(self) -> TextType | None:
        return "Parser Error"

    def get_message(self) -> RenderableType:
        return (
            str(self.error.message)
            if self.error.message
            else f"(no message, exit status: {self.error.status!r})"
        )

    def render_rich(self) -> None:
        if self.exit_status == 0:
            if message := self.error.message:
                self.out.print(message)
            return

        super().render_rich()
