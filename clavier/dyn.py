"""
Functions for doing _dynamic_ things, like iterating all of the immediate child
modules (useful for loading sub-commands).
"""

import os
import sys
import importlib.util
import pkgutil
from typing import Iterable
from clavier import cfg

import splatlog

_LOG = splatlog.get_logger(__name__)


def get_child_module(name, package):
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
    spec.loader.exec_module(module)

    return module


@_LOG.inject
def children_modules(
    parent__name__: str,
    parent__path__: Iterable[str],
    *,
    log: splatlog.SplatLogger = _LOG,
):
    for _loader, name, _is_pkg in pkgutil.walk_packages(parent__path__):
        # We only want the direct descendants, so filter out anything with
        # "." in it's name
        if "." not in name:
            try:
                yield get_child_module(name, parent__name__)
            except Exception:
                log_fn = (
                    log.exception
                    if cfg.CFG.get((cfg.SELF_ROOT_KEY, "backtrace"), False)
                    else log.warning
                )

                log_fn(
                    (
                        "Failed to import module `%s.%s`; "
                        "some commands may not be available"
                    ),
                    parent__name__,
                    name,
                )
