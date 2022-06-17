from types import TracebackType
from typing import Optional

from rich.console import RichCast

from clavier.typ import TExcInfo


class RenderError(RichCast):
    RENDER = "�"
    NO_MESSAGE = "(no message)"

    _message: Optional[str]
    _error: Optional[BaseException]
    _exc_info: Optional[TExcInfo]

    def __init__(
        self,
        message: Optional[str] = None,
        error: Optional[BaseException] = None,
        exc_info: Optional[TExcInfo] = None,
    ):
        self._message = message
        self._error = error
        self._exc_info = exc_info

    @property
    def error(self) -> Optional[BaseException]:
        if self._error is not None:
            return self._error
        if self._exc_info is not None and self._exc_info[1] is not None:
            return self._exc_info[1]
        return None

    @property
    def message(self) -> str:
        if self._message is not None:
            return self._message
        error = self.error
        if error is not None:
            return f"{type(error).__name__}: {error}"
        return self.__class__.NO_MESSAGE

    @property
    def exc_info(self) -> Optional[TExcInfo]:
        if self._exc_info is not None:
            return self._exc_info
        if (
            self._error is not None
            and hasattr(self._error, "__traceback__")
            and isinstance(self._error.__traceback__, TracebackType)
        ):
            return (type(self._error), self._error, self._error.__traceback__)
        return None

    def __rich__(self) -> str:
        return self.__class__.RENDER