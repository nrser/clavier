from dataclasses import dataclass, field
from io import StringIO
from textwrap import dedent
from typing import (
    IO,
    Any,
    Callable,
    Generator,
    Iterable,
    NamedTuple,
    Sequence,
    TypeVar,
)
from collections.abc import MutableMapping

from more_itertools import only
from rich.repr import RichReprResult
from markdown_it import MarkdownIt
from markdown_it.tree import SyntaxTreeNode as Node
from markdown_it.renderer import RendererProtocol
from markdown_it.token import Token
from markdown_it.utils import OptionsDict

MD = MarkdownIt("commonmark")

T = TypeVar("T")
Predicate = Callable[[T], Any]


def as_tree(md_src: str) -> Node:
    return Node(MD.parse(md_src))


@dataclass
class Section:
    heading: Node | None = None
    body: list[Node] = field(default_factory=list)

    @property
    def title(self) -> str | None:
        if h := self.heading:
            return only(c.content for c in h.children)

    @property
    def depth(self) -> int:
        if h := self.heading:
            return int(h.tag[1:])
        return 0

    def __rich_repr__(self) -> RichReprResult:
        yield "title", self.title, None
        yield "depth", self.depth, 0
        yield "heading", self.heading, None
        yield "body", self.body


def iter_sections(node: Node) -> Generator[Section, None, None]:
    section: Section = Section()

    for child in node.children:
        if child.type == "heading":
            yield section
            section = Section(child)
        else:
            section.body.append(child)

    yield section


def as_sections(node: Node) -> list[Section]:
    return list(iter_sections(node))


def find_sections_by_title(
    sections: Iterable[Section], title: str
) -> Generator[Section, None, None]:
    for section in sections:
        if (t := section.title) and t.lower() == title:
            yield section


def find_section_by_title(
    sections: Iterable[Section], title: str
) -> Section | None:
    return only(find_sections_by_title(sections, title))


class MdRenderer(RendererProtocol):
    __output__ = "commonmark"

    def render_token_to(self, token: Token, out: IO[str]):
        out.write(token.markup)
        out.write(token.content)
        if children := token.children:
            for child in children:
                self.render_token_to(child, out)
        if token.block:
            out.write("\n\n")

    def render(
        self, tokens: Sequence[Token], options: OptionsDict, env: MutableMapping
    ) -> Any:
        sio = StringIO()

        for token in tokens:
            self.render_token_to(token, sio)

        return sio.getvalue()


# @dataclass(frozen=True)
# class Edit:
#     class Line(NamedTuple):
#         lineno: int
#         text: str

#     src: str
#     node: Node
#     lines: tuple[Line, ...] = field(init=False)
#     cuts: list[range] = field(init=False)

#     def __post_init__(self):
#         object.__setattr__(
#             self,
#             "lines",
#             tuple(self.Line(i, t) for i, t in enumerate(self.src.splitlines())),
#         )
#         object.__setattr__(self, "cuts", [])

#     def cut(self, node: Node):
#         node.parent.


if __name__ == "__main__":
    from inspect import getdoc

    from clavier.srv.entrypoint import build
    from rich import print as p

    def f(x):
        md_src = x if isinstance(x, str) else getdoc(x)
        assert md_src, "no source"

        root = as_tree(md_src)

        sections = as_sections(root)

        p(sections)

        parameters = find_section_by_title(sections, title="parameters")

    f(build)

    f(
        dedent(
            """
            Blah blah.

            # Hey

            ho

            dfdsfsdfgdfs

            ## Let's _see_ what's up

            go

            ### How

            you been
            """
        )
    )
