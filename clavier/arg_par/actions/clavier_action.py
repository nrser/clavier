from abc import ABCMeta
from argparse import Action, SUPPRESS, Namespace
from copy import deepcopy
from typing import TYPE_CHECKING, Any, Optional, Sequence, TypeVar, Union

import splatlog


if TYPE_CHECKING:
    from ..argument_parser import ArgumentParser


TClavierAction = TypeVar("TClavierAction", bound="ClavierAction")


class ClavierAction(Action, metaclass=ABCMeta):
    """Abstract base class extending `argparse.Action` to add a few features:

    1.  Propagation — Automatic copying of the action to subparsers.
    2.  Logging — Adds a `splatlog.LoggerProperty`.

    """

    _log = splatlog.LoggerProperty()

    _owner: Optional["ArgumentParser"]
    _propagate: bool
    _is_inherited: bool

    def __init__(
        self,
        *args,
        propagate: bool = False,
        owner: Optional["ArgumentParser"] = None,
        **kwds
    ):
        super().__init__(*args, **kwds)
        self._owner = owner
        self._propagate = propagate
        self._is_inherited = False

    @property
    def _splatlog_self_(self) -> Any:
        return ", ".join(self.option_strings)

    @property
    def owner(self) -> Optional["ArgumentParser"]:
        return self._owner

    @property
    def propagate(self) -> bool:
        return self._propagate

    @property
    def is_inherited(self) -> bool:
        return self._is_inherited

    def clone_child(self: TClavierAction) -> TClavierAction:
        child = deepcopy(self)
        child._is_inherited = True
        return child
