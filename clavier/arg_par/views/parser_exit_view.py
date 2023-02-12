from dataclasses import dataclass
import json
from typing import TYPE_CHECKING
from clavier import io, err

from rich.console import Console
from rich.text import Text
import splatlog
from splatlog.json.default_handlers import TRACEBACK_HANDLER

if TYPE_CHECKING:
    from clavier.sesh import Sesh


@dataclass(frozen=True)
class _Data:
    error: err.ParserExit
    sesh: "Sesh"


class ParserExitView(io.View[_Data]):
    _log = splatlog.LoggerProperty()

    def __init__(
        self,
        sesh: "Sesh",
        error: err.ParserExit,
        out: Console = io.OUT,
        err: Console = io.ERR,
    ):
        super().__init__(
            _Data(sesh=sesh, error=error),
            return_code=error.status,
            out=out,
            err=err,
        )

    def render_rich(self):
        sesh = self.data.sesh
        error = self.data.error

        # NOTE  Single call site at this time (2023-02-04); factored-out into
        #       a separate method to make caller (`run``) easier to read.
        #
        self._log.debug(
            "Handling `ParserExit`...",
            status=error.status,
            message=error.message,
        )

        if error.status == 0:
            if message := error.message:
                self.out.print(message)
            return

        is_bt = sesh.is_backtracing()

        message = (
            str(error.message)
            if error.message
            else f"(no message, exit status {error.status})"
        )

        subtitle = None

        if not is_bt:
            bt_key = sesh.get_app_setting_key("backtrace", bool)
            subtitle = Text(
                f"Set {bt_key.env_name}=1 to print trace",
                "panel.error.subtitle",
            )

        self.err.print(
            io.error_panel(
                Text.from_markup(message),
                title="Parser Error",
                subtitle=subtitle,
                context="Failed to parse arguments",
            )
        )

        if is_bt:
            self.err.print(io.as_traceback(error))
            self.err.print(io.NEWLINE)

    def render_json(self):
        sesh = self.data.sesh
        error = self.data.error

        payload = {
            "status": error.status,
            "message": error.message,
        }

        if (
            error.status != 0
            and sesh.is_backtracing()
            and (tb := error.__traceback__)
        ):
            payload["traceback"] = TRACEBACK_HANDLER.handle(tb)

        self.out.print(json.dumps(payload, indent=2))
