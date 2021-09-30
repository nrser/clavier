from __future__ import annotations
from collections import namedtuple
import re
import os
from typing import Any
from sortedcontainers import SortedDict

from .key import Key
from .scope import ReadScope
from .changeset import Changeset


class Config:
    ENV_VAR_NAME_SUB_RE = re.compile(r"[^A-Z0-9]+")

    Update = namedtuple("Update", ["changes", "meta"])

    def __init__(self):
        self._view = SortedDict()
        self._updates = []

    def configure(self, *prefix, **meta) -> Changeset:
        return Changeset(config=self, prefix=prefix, meta=meta)

    def configure_root(self, package, **meta) -> Changeset:
        return Changeset(config=self, prefix=Key(package).root, meta=meta)

    def env_has(self, key) -> bool:
        return key in self._view and Key(key).env_name in os.environ

    def env_get(self, key):
        value_s = os.environ[Key(key).env_name]
        typ = type(self._view[key])
        if typ is str:
            return value_s
        else:
            try:
                return typ(value_s)
            except Exception:
                return value_s

    def __contains__(self, key: Any) -> bool:
        try:
            key = Key(key)
        except Exception:
            return False
        return key in self._view

    def __getitem__(self, key: Any) -> Any:
        try:
            key = Key(key)
        except KeyError as error:
            raise error
        except Exception as error:
            raise KeyError(f"Not convertible to a Key: {repr(key)}") from error

        if self.env_has(key):
            return self.env_get(key)
        if key in self._view:
            return self._view[key]
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

    def __iter__(self):
        return iter(self._view)

    def update(self, changes, meta) -> None:
        self._view.update(changes)
        self._updates.insert(0, self.Update({**changes}, {**meta}))

    def to_dict(self):
        return {str(key): self[key] for key in self._view}
