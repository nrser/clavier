from argparse import Action, SUPPRESS
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path
from typing import TYPE_CHECKING, Generator, Mapping, NamedTuple, Sequence
from clavier.etc.iter import intersperse

from splatlog.lib.rich import enrich

from rich.text import Text
from rich.console import Group, RenderableType as _RT
from rich.table import Table
from rich.pretty import Pretty
from rich.measure import Measurement
from rich.padding import Padding
from rich.style import Style as _S

from clavier import io, txt

from clavier.arg_par.actions import ClavierAction
from clavier.arg_par.subparsers import Subparsers
from clavier.io.enriched_path import EnrichedPath

if TYPE_CHECKING:
    from .rich_help_formatter import RichHelpFormatter


class _InfoTableRow(NamedTuple):
    name: _RT
    value: _RT


@dataclass
class RichActionFormatter:
    formatter: "RichHelpFormatter"
    action: Action
    depth: int

    @cached_property
    def invocation(self) -> _RT:
        return self.formatter._format_action_invocation(self.action)

    @cached_property
    def invocation_measurement(self) -> Measurement:
        return Measurement.get(
            self.formatter._console,
            self.formatter._console.options,
            self.invocation,
        )

    def format_value(self, value: object) -> _RT:
        match value:
            case str(s):
                return Text(s, "help.action.str_value")
            case Path() as path:
                return EnrichedPath(path)
            # case tuple() | list():
            #     table = Table(
            #         padding=(0, 2, 0, 0),
            #         # show_header=False,
            #         title=f"{value.__class__.__name__}[{len(value)}]",
            #         box=None,
            #     )
            #     table.add_column()
            #     table.add_column()
            #     for i, e in enumerate(value):
            #         table.add_row(f"[{i}]", self.format_value(e))
            #     return table
            case other:
                return Pretty(other)

    def default_rows(self) -> Generator[_InfoTableRow, None, None]:
        if (default := self.action.default) and default != SUPPRESS:
            name = Text("default", "help.action.info.name")
            match default:
                case map if isinstance(map, Mapping):
                    yield _InfoTableRow(name, io.EMPTY)
                    for k, v in map.items():
                        yield _InfoTableRow(
                            Text(
                                f"[{k}]",
                                "help.action.info.name",
                                justify="right",
                            ),
                            self.format_value(v),
                        )

                case seq if isinstance(seq, Sequence) and not isinstance(
                    seq, (str, bytes)
                ):
                    yield _InfoTableRow(name, io.EMPTY)
                    for i, v in enumerate(seq):
                        yield _InfoTableRow(
                            Text(
                                f"[{i}]",
                                "help.action.info.name",
                                justify="right",
                            ),
                            self.format_value(v),
                        )

                case other:
                    yield _InfoTableRow(name, self.format_value(other))

    @cached_property
    def choices_row(self) -> _InfoTableRow | None:
        if isinstance(self.action, Subparsers):
            return None

        if (_choices := self.action.choices) and (choices := tuple(_choices)):
            return _InfoTableRow(
                Text("choices", "help.action.info.name"),
                Group(*(self.format_value(c) for c in choices)),
            )

    def info_table_rows(self) -> Generator[_InfoTableRow, None, None]:
        if typ := self.type:
            yield _InfoTableRow(Text("type", "help.action.info.name"), typ)

        if choices_row := self.choices_row:
            yield choices_row

        yield from self.default_rows()

    @cached_property
    def info_table(self) -> _RT | None:
        if (not self.formatter.short) and (
            rows := list(self.info_table_rows())
        ):
            table = Table(
                padding=(0, self.formatter.indent, 0, 0),
                show_header=False,
                box=None,
                # expand=True,
            )

            table.add_column()  # justify="right")  # ratio=2)
            table.add_column()  # ratio=10)

            for index, row in enumerate(rows):
                # if index != 0:
                #     table.add_row(io.EMPTY, io.EMPTY)
                table.add_row(*row)

            return table

    @cached_property
    def subactions(self) -> _RT | None:
        if hasattr(self.action, "_get_subactions"):
            # pylint: disable=protected-access
            return self.formatter._format_actions(
                list(self.formatter._iter_subactions(self.action)),
                _depth=self.depth + 1,
            )

    @cached_property
    def help(self) -> _RT | None:
        if self.action.help:
            return self.formatter._expand_help(self.action)

    @cached_property
    def contents(self) -> _RT:
        return (
            io.Grouper(
                [
                    self.help,
                    self.info_table,
                    self.subactions,
                ]
            )
            .join(io.NEWLINE)
            .to_group()
        )

    @cached_property
    def type(self) -> _RT | None:
        if typ := self.action.type:
            return enrich(self.action.type)

    def label(self, name: str, icon: str = "🏷 ") -> Text:
        # Tried with an icon, ended up just feeling too noisy
        # return Text.assemble(
        #     " ",
        #     icon,
        #     " ",
        #     (name, "help.action.label.name"),
        #     " ",
        #     style="help.action.label",
        # )

        return Text(name, style="help.action.label.name")

    @cached_property
    def labels(self) -> _RT:
        labels = io.Grouper()

        if isinstance(self.action, ClavierAction) and self.action.is_inherited:
            labels.append(self.label("inherited", "👪"))

        return labels.to_group()
