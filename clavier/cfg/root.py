from __future__ import annotations
import re
import os
from typing import (
    Any,
    Dict,
    Generator,
    Iterable,
    Iterator,
    List,
    Mapping,
    Optional,
    Tuple,
)
from sortedcontainers import SortedDict

from clavier.cfg.config import Config, ValueState
from clavier.cfg.env import Env
from clavier.cfg.key import Key
from clavier.cfg.scope import ReadScope
from clavier.cfg.changeset import Changeset
from clavier.cfg.layer import Layer, Change, Update
from clavier.etc.coll import bury
from clavier.etc.read_only_mapping import ReadOnlyMapping


class Root(Config):
    ENV_VAR_NAME_SUB_RE = re.compile(r"[^A-Z0-9]+")

    _layers: List[Update]
    _view: Dict[Key, ValueState]
    _env: Env

    def __init__(self):
        self._layers = []
        self._view = SortedDict()
        self._env = Env()

    def configure(self, *prefix, **meta) -> Changeset:
        return Changeset(
            config=self, prefix=prefix, meta={"type": "runtime", **meta}
        )

    def configure_root(self, package, **meta) -> Changeset:
        return self.configure(Key(package).root, **meta)

    def __contains__(self, key: Any) -> bool:
        try:
            key = Key(key)
        except Exception:
            return False
        if key in self._view:
            return True
        for k in self._view:
            if key in k.scopes():
                return True
        return False

    def __getitem__(self, key: Any) -> Any:
        try:
            key = Key(key)
        except KeyError as error:
            raise error
        except Exception as error:
            raise KeyError(f"Not convertible to a Key: {repr(key)}") from error

        if key in self._view:
            return self._view[key].value
        for k in self._view:
            if key in k.scopes():
                return ReadScope(base=self, key=key)

        raise KeyError(f"Config has no key or scope {repr(key)}")

    def __getattr__(self, name):
        try:
            return self[name]
        except AttributeError as error:
            raise error
        except Exception as error:
            raise AttributeError(
                f"Not convertible to a Key: {repr(name)}"
            ) from error

    def __iter__(self) -> Iterator[Key]:
        return iter(self._view)

    def __len__(self) -> int:
        return len(self._view)

    def get(self, key: Any, default: Any = None) -> Any:
        if key in self:
            return self[key]
        return default

    def items(self) -> Generator[Tuple[Key, Any], None, None]:
        for key, snapshot in self._view.items():
            yield (key, snapshot.value)

    def keys(self) -> Iterable[Key]:
        return self._view.keys()

    def values(self) -> Generator[Any, None, None]:
        for snapshot in self._view.values():
            yield snapshot.value

    def view(self) -> Mapping[Key, ValueState]:
        return ReadOnlyMapping(self._view)

    # Specific methods

    def update(self, changes, meta) -> None:
        update = Update(changes, meta)
        for key, change in update.changes.items():
            if self._env.register(key, type(change.value)):
                # Key is represented in the env, set it in the view
                self._view[key] = ValueState(
                    value=self._env[key],
                    layer=self._env,
                )
            else:
                # Key is not in the env, so add the change value
                self._view[key] = ValueState(
                    value=change.value,
                    layer=update,
                )

        self._layers.insert(0, update)

    def layers(
        self, include_env: Optional[bool] = None
    ) -> Generator[Layer, None, None]:
        if include_env is True or (include_env is None and len(self.env) > 0):
            yield self._env
        yield from self._layers

    def to_dict(self, *, deep: bool = False):
        if deep:
            dct = {}
            for key, value in self.items():
                bury(dct, key, value)
            return dct
        return {str(key): value for key, value in self.items()}
