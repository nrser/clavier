from contextvars import Context, ContextVar, copy_context, Token
from typing import Any, Iterable


from .config import Config
from .container import Container
from .key import Key


class ContextualConfig(Config):
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

    def create_derived_context(self) -> Context:
        context = copy_context()
        context.run(self.derive_child)
        return context

    def derive_child(self) -> Token:
        parent = self._context_var.get()
        child = Container(parent=parent)
        return self._context_var.set(child)
