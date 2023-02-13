from typing import TYPE_CHECKING, Protocol, TypeVar

import splatlog

from ..view import View

if TYPE_CHECKING:
    from clavier.sesh import Sesh


class SeshViewData(Protocol):
    sesh: "Sesh"


TSeshViewData = TypeVar("TSeshViewData", bound=SeshViewData)


class SeshView(View[TSeshViewData]):
    _log = splatlog.LoggerProperty()

    @property
    def sesh(self) -> "Sesh":
        return self.data.sesh
