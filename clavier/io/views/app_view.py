from typing import TYPE_CHECKING, Protocol, TypeVar

import splatlog

from ..view import View

if TYPE_CHECKING:
    from clavier.app import App


class AppViewData(Protocol):
    app: "App"


TAppViewData = TypeVar("TAppViewData", bound=AppViewData)


class AppView(View[TAppViewData]):
    _log = splatlog.LoggerProperty()

    @property
    def app(self) -> "App":
        return self.data.app
