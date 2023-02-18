import argparse
from collections import defaultdict
from dataclasses import dataclass, field
from inspect import getdoc, isclass, signature
import re
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
from more_itertools import only

from rich.repr import RichReprResult

from clavier import arg_par, txt, etc

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


ActionType = Callable[[str], Any] | argparse.FileType | None


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


def is_union(annotation: Any) -> bool:
    return isinstance(annotation, UnionType) or get_origin(annotation) is Union


def as_action_type(annotation: Any) -> ActionType:
    match annotation:
        case None:
            return None
        case t if isclass(t):
            return t
        case u if is_union(u):
            return ActionUnionType(u)
    raise ValueError(f"not sure how to turn into action type: {annotation!r}")


NAME_RE = re.compile(r"(?P<lead>[\-\*]\s+)\`?(?P<name>\w+)\`?(?:\s+[\-—]\s+)")

TDocstring = TypeVar("TDocstring", bound="Docstring")


@dataclass(frozen=True)
class Docstring:
    @classmethod
    def of(cls: type[TDocstring], obj: object) -> TDocstring | None:
        if src := getdoc(obj):
            return cls(src=src)

    src: str
    src_lines: tuple[str, ...] = field(init=False)
    cuts: list[range] = field(init=False)

    def __post_init__(self):
        object.__setattr__(self, "src_lines", tuple(self.src.splitlines()))
        object.__setattr__(self, "cuts", [])

    def cut(self, node: etc.md.Node) -> list[str] | None:
        if node_map := node.map:
            start, stop = node_map
            rng = range(start, stop)
            self.cuts.append(rng)
            return list(self.src_lines[start:stop])

    def iter_lines(self):
        for i, line in enumerate(self.src_lines):
            if not any(i in rng for rng in self.cuts):
                yield line

    def __str__(self) -> str:
        return "".join(self.iter_lines())


def parse_docstring(obj: object) -> tuple[str | None, dict[str, str]]:
    if ds := Docstring.of(obj):

        root = etc.md.as_tree(ds.src)
        sections = etc.md.as_sections(root)

        if (
            (
                params_section := only(
                    s
                    for s in sections
                    if s.title and s.title.lower() == "parameters"
                )
            )
            and (
                params_list := only(
                    n for n in params_section.body if n.type == "bullet_list"
                )
            )
            and (heading_node := params_section.heading)
        ):
            ds.cut(heading_node)
            for node in params_section.body:
                ds.cut(node)

            items = {}

            for list_item in params_list.children:
                if (item_lines := ds.cut(list_item)) and (
                    m := NAME_RE.match(item_lines[0])
                ):
                    lead_len = len(m.group("lead"))
                    rm_lead_re = re.compile(r"^[\-\s]{" + str(lead_len) + r"}")
                    new_lines = []
                    for i, line in enumerate(item_lines):
                        if i == 0:
                            new_lines.append(line[m.end() :])
                        else:
                            new_lines.append(rm_lead_re.sub("", line))

                    items[m.group("name")] = "\n".join(new_lines)

            return str(ds), items

    return None, {}


def as_cmd(fn: Callable[TParams, TReturn]) -> CmdFn[TParams, TReturn]:
    def add_parser(subparsers: arg_par.Subparsers) -> None:
        help, params_help = parse_docstring(fn)

        parser = subparsers.add_parser(
            fn.__name__,
            target=fn,
            help=help,
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

            kwds["help"] = params_help.get(p.name)

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


if __name__ == "__main__":
    from rich import print as p

    from clavier.srv.entrypoint import build

    p(parse_docstring(build))
