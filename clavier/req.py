from argparse import Namespace
import asyncio
from dataclasses import dataclass, field
from inspect import BoundArguments, unwrap
from typing import Any

from clavier.etc.ins import adaptive_bind_mut

from .arg_par.argument_parser import TARGET_NAME, Target, check_target
from . import err


@dataclass(frozen=True)
class Req:
    """A small, immutable structure that encapsulates a _request_ to a Clavier
    app, analogous to common structural representations of HTTP and other
    requests in network servers.

    |    HTTP    |                     Clavier                      |
    | ---------- | ------------------------------------------------ |
    | app/server | `clavier.sesh.Sesh`                              |
    | route      | `clavier.arg_par.argument_parser.ArgumentParser` |
    | handler    | `clavier.arg_par.argument_parser.Target`         |
    | request    | `clavier.req.Req`                                |

    """

    @classmethod
    def get_target(cls, args: Namespace) -> Target:
        """Extracts the request _target_ (handling function) from a `Namespace`
        of arguments (`args`) and checks it is of appropriate type, raising an
        `err.InternalError` if there are any issues.

        ##### See Also #####

        1.  `clavier.arg_par.argument_parser.Target`
        2.  `clavier.arg_par.argument_parser.TARGET_NAME`
        3.  `clavier.arg_par.argument_parser.check_target`

        """
        try:
            return check_target(getattr(args, TARGET_NAME))
        except err.InternalError:
            raise
        except Exception as error:
            raise err.InternalError(
                f"Failed to get target from args {args!r} -- {error}"
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

    #: The raw command line arguments. Typically equivalent to `sys.argv[1:]`.
    argv: tuple[str, ...]

    #: The parsed arguments, typically via `argparse.ArgumentParser.parse_args`.
    args: Namespace

    #: The function the request is to execute, extracted from the `TARGET_NAME`
    #: attribute of the `args`.
    target: Target = field(init=False)

    #: The binding to `target` created from the `args`, which may use none, some
    #: or all of them depending on the `inspect.Signature` of `target`.
    #:
    #: ##### See Also #####
    #:
    #: 1.  `clavier.etc.ins.adaptive_bind`
    #:
    binding: BoundArguments = field(init=False)

    def __post_init__(self):
        object.__setattr__(self, "target", self.get_target(self.args))
        object.__setattr__(
            self,
            "binding",
            adaptive_bind_mut(self.target, self.get_kwds(self.args)),
        )

    @property
    def is_async(self) -> bool:
        return asyncio.iscoroutinefunction(unwrap(self.target))

    def __call__(self) -> Any:
        """Invoke the `target` with the `binding` and return the result."""
        return self.target(*self.binding.args, **self.binding.kwargs)
