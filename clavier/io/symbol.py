import sys
import logging

from rich.console import RichCast, RenderableType
from rich.emoji import Emoji, NoEmoji
from clavier.io.render_error import RenderError

LOG = logging.getLogger(__name__)


class Symbol(RichCast):
    @classmethod
    def render(cls, src: str) -> RenderableType:
        if len(src) == 1:
            # Strings of length 1 already qualify, so simply return them
            return src
        if src[0] == ":" and src[-1] == ":":
            # Indicator for Emoji, like ":package:"
            try:
                return Emoji(src[1:-1])
            except NoEmoji:
                return RenderError(
                    "`src` looked like emoji, but construction failed",
                    exc_info=sys.exc_info(),
                )
        return RenderError(f"Not a recognized Symbol source format: {src!r}")

    _src: str
    _render: RenderableType

    def __init__(self, src: str):
        self._src = src
        self._render = self.__class__.render(self._src)
        if isinstance(self._render, RenderError):
            LOG.warning(
                self._render.message,
                src=self._src,
                exc_info=self._render.exc_info,
            )

    @property
    def src(self) -> str:
        return self._src

    def __rich__(self):
        return self._render
