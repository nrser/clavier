from dataclasses import dataclass
from typing import TYPE_CHECKING, Generic, TypeVar

from rich.console import Console, RenderableType
from rich.text import TextType
from rich.markdown import Markdown

from splatlog.json.default_handlers import TRACEBACK_HANDLER

from clavier import txt

from .sesh_view import SeshView
from ..io_helpers import as_traceback, error_panel
from ..io_consts import OUT, ERR, NEWLINE

if TYPE_CHECKING:
    from clavier.sesh import Sesh

TError = TypeVar("TError", bound=BaseException)


@dataclass(frozen=True)
class RunErrorViewData(Generic[TError]):
    sesh: "Sesh"
    error: TError
    context: str | None


class SeshErrorView(SeshView[RunErrorViewData[TError]]):
    is_backtracing: bool

    def __init__(
        self,
        sesh: "Sesh",
        error: TError,
        context: str | None,
        exit_status: int = 1,
        out: Console = OUT,
        err: Console = ERR,
    ):
        super().__init__(
            RunErrorViewData(
                sesh=sesh,
                error=error,
                context=context,
            ),
            exit_status=exit_status,
            out=out,
            err=err,
        )

        self.is_backtracing = sesh.is_backtracing()

    @property
    def error(self) -> TError:
        return self.data.error

    def get_subtitle(self) -> TextType | None:
        if self.is_backtracing:
            return None

        opts = []

        if setting := self.sesh.get_parser_setting("backtrace"):
            opts.extend(setting.flags)

        for f in (self.sesh.get_app_setting_key, self.sesh.get_lib_setting_key):
            opts.append(f("backtrace", bool).env_name + "=1")

        return "Show trace: " + " | ".join(opts)

    def get_message(self) -> RenderableType:
        match self.error.args:
            case ():
                msg = str(self.error)
            case (str(s),):
                msg = s
            case args:
                msg = " ".join(str(a) for a in args)
        return Markdown(msg)

    def get_context(self) -> TextType | None:
        if self.data.context is None:
            return None
        return f"{txt.fmt_type_of(self.error)} raised when {self.data.context}:"

    def get_title(self) -> TextType | None:
        return txt.fmt_type_of(self.error)

    def render_rich(self) -> None:
        self.err.print(
            error_panel(
                self.get_message(),
                title=self.get_title(),
                subtitle=self.get_subtitle(),
                context=self.get_context(),
            )
        )

        if self.is_backtracing:
            self.err.print(as_traceback(self.error))
            self.err.print(NEWLINE)

    # def render_json(self):
    #     sesh = self.data.sesh
    #     error = self.data.error

    #     payload = {
    #         "status": error.status,
    #         "message": error.message,
    #     }

    #     if (
    #         error.status != 0
    #         and sesh.is_backtracing()
    #         and (tb := error.__traceback__)
    #     ):
    #         payload["traceback"] = TRACEBACK_HANDLER.handle(tb)

    #     self.out.print(json.dumps(payload, indent=2))
