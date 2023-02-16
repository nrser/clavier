from argparse import Namespace
import asyncio
from dataclasses import dataclass, field
from inspect import unwrap
from types import MappingProxyType
from typing import Any, Mapping

from .arg_par.argument_parser import TARGET_NAME, Target, check_target
from . import err


@dataclass(frozen=True)
class Req:
    @classmethod
    def get_target(cls, args: Namespace) -> Target:
        try:
            return check_target(getattr(args, TARGET_NAME))
        except err.InternalError:
            raise
        except Exception as error:
            raise err.InternalError(
                f"Failed to get target from args {args!r}"
            ) from error

    @classmethod
    def get_kwds(cls, args: Namespace) -> dict[str, Any]:
        kwds = {k: v for k, v in args.__dict__.items() if k != TARGET_NAME}

        # Resolve "default getters" — argument values (presumably from the
        # default value at `argparse.Action.default` or
        # `argparse.ArgumentParser._defaults`, hence the name) that are
        # `callable` that need to be called to produce the actual argument
        # value.
        #
        # NOTE  This took very little to write, and works for the moment, but it
        #       relies on a bunch of sketch things (beyond being hard to read
        #       and understand quickly):
        #
        #       1.  All values that are callable are considered default getters.
        #
        #       2.  The order that the arguments were added to the
        #           ArgumentParser` is the order we end up iterating in here.
        #
        #           Otherwise there's no definition of the iter-dependency
        #           chains.
        #
        #       3.  Hope nothing else messes with the `values` reference while
        #           we're mutating it.
        #
        for key in kwds:
            if callable(kwds[key]):
                kwds[key] = kwds[key](
                    **{k: v for k, v in kwds.items() if not callable(v)}
                )

        return kwds

    argv: tuple[str, ...]
    args: Namespace
    target: Target = field(init=False)
    kwds: Mapping[str, Any] = field(init=False)

    def __post_init__(self):
        object.__setattr__(self, "target", self.get_target(self.args))
        object.__setattr__(
            self, "kwds", MappingProxyType(self.get_kwds(self.args))
        )

    @property
    def is_async(self) -> bool:
        return asyncio.iscoroutinefunction(unwrap(self.target))
