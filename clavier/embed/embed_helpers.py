from collections import defaultdict
from inspect import getdoc, signature
from typing import Any, Callable, ParamSpec, Protocol, TypeVar, cast

from clavier import arg_par

from .embed_typings import CmdFn

TParams = ParamSpec("TParams")
TReturn = TypeVar("TReturn")


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
            kwds: dict[str, Any] = {"type": p.annotation}
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
