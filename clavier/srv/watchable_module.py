from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
import sys
from importlib.machinery import ModuleSpec
import site
from types import ModuleType
from typing import Iterable, TypeVar

from clavier import etc

SITE_PACKAGES = [Path(s).resolve() for s in site.getsitepackages()]
SYS_BASE_PREFIX = Path(sys.base_prefix).resolve()


TWatchableModule = TypeVar("TWatchableModule", bound="WatchableModule")


@dataclass(frozen=True)
class WatchableModule:
    #: Known `importlib.machinery.ModuleSpec.origin` values that are _not_ file
    #: system paths, and therefore represent unwatchable module sources.
    #:
    #: There were found empircally, but 'built-in' can be seen at
    #: `builtins.__spec__.origin` and 'frozen' can be found seen at
    #: `zipimport.__spec__.origin` (as of Python 3.10, 2023-02-20).
    #:
    KNOWN_NON_PATH_ORIGINS = frozenset(("built-in", "frozen"))

    @classmethod
    def of(
        cls: type[TWatchableModule], module: object
    ) -> TWatchableModule | None:
        if (
            isinstance(module, ModuleType)
            and (spec := module.__spec__)
            and (origin := spec.origin)
            and (origin not in cls.KNOWN_NON_PATH_ORIGINS)
            and Path(origin).exists()
        ):
            return cls(module=module, spec=spec)

    @classmethod
    def of_loaded(
        cls: type[TWatchableModule],
        exclude_sys_base: bool = False,
        exclude_site_packages: bool = False,
    ) -> list[TWatchableModule]:
        loaded: list[TWatchableModule] = []

        for module in sys.modules.values():
            if (
                (wm := cls.of(module))
                and (exclude_sys_base is False or wm.is_in_sys_base is False)
                and (
                    exclude_site_packages is False
                    or wm.is_in_site_packages is False
                )
            ):
                loaded.append(wm)

        return loaded

    @classmethod
    def root_set_of_loaded(
        cls,
        exclude_sys_base: bool = False,
        exclude_site_packages: bool = False,
    ) -> set[WatchableModule]:
        watchable_modules = cls.of_loaded(
            exclude_site_packages=exclude_site_packages,
            exclude_sys_base=exclude_sys_base,
        )
        roots: set[WatchableModule] = set()

        def add(wm_new: WatchableModule):
            to_rm = set()

            for wm_root in roots:
                if wm_new in wm_root:
                    # If the new module is "contained" in _any_ module in the
                    # root set then we're done with it, it's not a root
                    return

                # If the root is "contained" in the new module then we need to
                # remove that root because it turns out it's not one
                if wm_root in wm_new:
                    to_rm.add(wm_root)

            # Remove the elements we discovered are not root, if any
            if to_rm:
                roots.difference_update(to_rm)

            # Add the new module
            roots.add(wm_new)

        for wm_new in watchable_modules:
            add(wm_new)

        return roots

    module: ModuleType
    spec: ModuleSpec
    origin: Path = field(init=False)

    def __post_init__(self):
        if not (spec_origin := self.spec.origin):
            raise ValueError(
                f"module spec must have origin; `{self.name}` has `origin`: "
                f"{self.spec.origin!r}"
            )

        if spec_origin in self.KNOWN_NON_PATH_ORIGINS:
            raise ValueError(
                "module spec can not have origin in {}; {} has spec origin {!r}".format(
                    etc.txt.fmt(self.KNOWN_NON_PATH_ORIGINS),
                    self.name,
                    spec_origin,
                )
            )

        origin = Path(spec_origin).resolve()

        if not origin.exists():
            raise ValueError(
                f"module spec must existing path as origin; `{self.name}` has "
                f"`origin`: {spec_origin!r}"
            )

        object.__setattr__(self, "origin", origin)

    @property
    def name(self) -> str:
        return self.module.__name__

    @property
    def dir(self) -> Path:
        return self.origin.parent

    @property
    def is_in_sys_base(self) -> bool:
        return etc.path.is_rel(self.origin, SYS_BASE_PREFIX)

    @property
    def is_in_site_packages(self) -> bool:
        return any(etc.path.is_rel(self.origin, p) for p in SITE_PACKAGES)

    def __contains__(self, other: object) -> bool:
        if not isinstance(other, self.__class__):
            return NotImplemented

        return other.name.startswith(f"{self.name}.") and etc.path.is_rel(
            other.origin, self.dir
        )

    def __hash__(self) -> int:
        return hash(self.name)
