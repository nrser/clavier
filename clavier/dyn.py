"""
Functions for doing _dynamic_ things, like iterating all of the immediate child
modules (useful for loading sub-commands).
"""

import os
import sys
import importlib.util
import pkgutil
from types import ModuleType
from typing import Any, Generator, Iterable
from clavier import cfg

import splatlog

_LOG = splatlog.get_logger(__name__)

_BACKTRACE_KEY = cfg.Key(cfg.SELF_ROOT_KEY, "backtrace")


def get_child_module(name, package) -> ModuleType:
    absolute_name = f"{package}.{name}"
    try:
        return sys.modules[absolute_name]
    except KeyError:
        pass

    spec = importlib.util.find_spec(f".{name}", package)

    if spec is None:
        raise ModuleNotFoundError(
            f"No module named {absolute_name!r}", name=absolute_name
        )

    module = importlib.util.module_from_spec(spec)
    sys.modules[absolute_name] = module

    if loader := spec.loader:
        loader.exec_module(module)
    else:
        raise AttributeError(f"{spec!r} missing `loader` (found `None`)")

    return module


@cfg.inject
def children_modules(
    config: Any,
    parent__name__: str,
    parent__path__: Iterable[str],
) -> Generator[ModuleType, None, None]:
    for _loader, name, _is_pkg in pkgutil.walk_packages(parent__path__):

        # We only want the direct descendants, so filter out anything with
        # "." in it's name
        if "." not in name:
            try:
                yield get_child_module(name, parent__name__)

            except Exception:
                if config.on_error != "warn":
                    raise

                log_args = (
                    (
                        "Failed to import module `{!s}.{!s}; "
                        "some commands may not be available."
                    ),
                    parent__name__,
                    name,
                )

                if cfg.CFG.get(_BACKTRACE_KEY, False):
                    _LOG.exception(*log_args)
                else:
                    _LOG.warning(*log_args)
