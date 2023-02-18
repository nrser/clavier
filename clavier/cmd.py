import argparse
from collections import defaultdict
from dataclasses import dataclass
from inspect import getdoc, isclass, signature
from types import NoneType, UnionType
from typing import (
    Any,
    Callable,
    ParamSpec,
    Protocol,
    TypeVar,
    Union,
    cast,
    TYPE_CHECKING,
    get_args,
    get_origin,
)

from rich.repr import RichReprResult

from clavier import arg_par, txt

TParams = ParamSpec("TParams")
TReturn = TypeVar("TReturn")

if TYPE_CHECKING:
    from clavier.arg_par.subparsers import Subparsers

TParams = ParamSpec("TParams")
TReturn_co = TypeVar("TReturn_co", covariant=True)


class CmdFn(Protocol[TParams, TReturn_co]):
    def __call__(
        self, *args: TParams.args, **kwds: TParams.kwargs
    ) -> TReturn_co:
        ...

    def add_parser(self, subparsers: "Subparsers") -> None:
        ...


ParserArgumentType = Callable[[str], Any] | argparse.FileType | None


def is_union(annotation: Any) -> bool:
    return isinstance(annotation, UnionType) or get_origin(annotation) is Union


@dataclass(frozen=True)
class ActionUnionType:
    union: Any

    def __call__(self, value: str):
        for member in get_args(self.union):
            if callable(member):
                if member is NoneType:
                    if value == "":
                        return None
                else:
                    try:
                        return member(value)
                    except:
                        pass
        raise ValueError(f"unable to cast {value!r} to {txt.fmt(self.union)}")

    def __rich_repr__(self) -> RichReprResult:
        yield self.union


def as_action_type(annotation: Any) -> ParserArgumentType:
    match annotation:
        case None:
            return None
        case t if isclass(t):
            return t
        case u if is_union(u):
            return ActionUnionType(u)
    raise ValueError(f"not sure how to turn into action type: {annotation!r}")


def as_cmd(fn: Callable[TParams, TReturn]) -> CmdFn[TParams, TReturn]:
    def add_parser(subparsers: arg_par.Subparsers) -> None:
        parser = subparsers.add_parser(
            fn.__name__,
            target=fn,
            help=getdoc(fn),
        )

        params = signature(fn).parameters.values()

        first_char_counts = defaultdict(lambda: 0)
        for p in params:
            first_char_counts[p.name[0]] += 1
        unique_first_chars = {c for c, n in first_char_counts.items() if n == 1}

        prefix = "-" if "-" in parser.prefix_chars else parser.prefix_chars[0]

        for p in signature(fn).parameters.values():
            args: list[str] = []
            kwds: dict[str, Any] = {}

            if p.annotation is bool:
                kwds["action"] = "store_true"
            else:
                kwds["type"] = as_action_type(p.annotation)

            match p.kind:
                case p.POSITIONAL_ONLY | p.POSITIONAL_OR_KEYWORD:
                    args.append(p.name)
                case p.KEYWORD_ONLY:
                    if p.name[0] in unique_first_chars:
                        args.append(f"{prefix}{p.name[0]}")
                    args.append(prefix * 2 + p.name)
                case p.VAR_KEYWORD:
                    pass
                case p.VAR_POSITIONAL:
                    args.append(p.name)
                    kwds["nargs"] = "*"
                case wtf:
                    raise ValueError(f"Unexpected Parameter.kind: {p.kind!r}")

            parser.add_argument(*args, **kwds)

    setattr(fn, "add_parser", add_parser)

    return cast(CmdFn[TParams, TReturn], fn)
