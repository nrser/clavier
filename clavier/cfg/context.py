from contextvars import Context, ContextVar, copy_context, Token
from typing import Any, Iterable

import splatlog

from .config import Config
from .container import Container
from .key import Key


class ContextualConfig(Config):
    _log = splatlog.LoggerProperty()

    def __init__(self, context_var: ContextVar[Config]):
        self._context_var = context_var

    def _get_parent_(self) -> Config:
        return self._context_var.get()

    def _own_keys_(self) -> Iterable[Key]:
        return ()

    def _has_own_(self, key: Key) -> bool:
        return False

    def _get_own_(self, key: Key) -> Any:
        raise KeyError("Scope does not own any keys")

    def _own_scopes_(self) -> set[Key]:
        return set()

    def _has_own_scope_(self, scope: Key) -> bool:
        return False

    def create_derived_context(self, **meta: Any) -> Context:
        context = copy_context()
        context.run(self.derive_child, **meta)
        return context

    def derive_child(self, **meta: Any) -> Token:
        parent = self._context_var.get()
        child = Container(parent=parent, **meta)
        return self._context_var.set(child)
