from __future__ import annotations
from collections import namedtuple
import re
import os
from typing import Any, MutableMapping

from sortedcontainers import SortedDict
import yaml

from .key import Key
from .scope import ReadScope
from .changeset import Changeset


class Config:
    ENV_VAR_NAME_SUB_RE = re.compile(r"[^A-Z0-9]+")

    Update = namedtuple("Update", ["changes", "meta"])

    _view: MutableMapping[Key, Any]

    def __init__(self):
        self._view = SortedDict()
        self._updates = []

    def configure(self, *prefix, **meta) -> Changeset:
        return Changeset(config=self, prefix=prefix, meta=meta)

    def configure_root(self, package, **meta) -> Changeset:
        return Changeset(config=self, prefix=Key(package).root, meta=meta)

    def env_has(self, key) -> bool:
        return Key(key).env_name in os.environ

    def env_get(self, key):
        value_s = os.environ[Key(key).env_name]
        return yaml.safe_load(value_s)

    def __contains__(self, key) -> bool:
        key = Key(key)
        if self.env_has(key):
            return True
        if key in self._view:
            return True
        for k in self._view:
            if key in k.scopes():
                return True
        return False

    def __getitem__(self, key):
        key = Key(key)
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

    def get(self, key, default=None):
        key = Key(key)
        if key in self:
            return self[key]
        return default

    def __iter__(self):
        return iter(self._view)

    def update(self, changes, meta) -> None:
        self._view.update(changes)
        self._updates.insert(0, self.Update({**changes}, {**meta}))

    def to_dict(self):
        return {str(key): self[key] for key in self._view}
