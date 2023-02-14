from argparse import Action, SUPPRESS
from dataclasses import dataclass
from functools import cached_property
from typing import TYPE_CHECKING, Generator, NamedTuple

from rich.text import Text
from rich.console import Group, RenderableType as _RT
from rich.table import Table
from rich.pretty import Pretty
from rich.measure import Measurement
from rich.padding import Padding

from clavier import io, txt

if TYPE_CHECKING:
    from ..rich_help_formatter import RichHelpFormatter


class _InfoTableRow(NamedTuple):
    name: _RT
    value: _RT


@dataclass
class RichActionFormatter:
    help_formatter: "RichHelpFormatter"
    action: Action
    depth: int

    @cached_property
    def invocation(self) -> _RT:
        return self.help_formatter._format_action_invocation(self.action)

    @cached_property
    def invocation_measurement(self) -> Measurement:
        return Measurement.get(
            self.help_formatter._console,
            self.help_formatter._console.options,
            self.invocation,
        )

    def format_value(self, value: object) -> _RT:
        if isinstance(value, str):
            return Text(value, "help.action.str_value")
        return Pretty(value)

    @cached_property
    def default_row(self) -> _InfoTableRow | None:
        if (default := self.action.default) and default != SUPPRESS:
            return _InfoTableRow(
                Text("default", "help.action.info.name"),
                self.format_value(default),
            )

    @cached_property
    def choices_row(self) -> _InfoTableRow | None:
        if (_choices := self.action.choices) and (choices := tuple(_choices)):
            return _InfoTableRow(
                Text("choices", "help.action.info.name"),
                Group(*(self.format_value(c) for c in choices)),
            )

    def info_table_rows(self) -> Generator[_InfoTableRow, None, None]:
        if choices_row := self.choices_row:
            yield choices_row

        if default_row := self.default_row:
            yield default_row

    @cached_property
    def info_table(self) -> _RT | None:
        table = Table(padding=(0, 2, 0, 0), show_header=False, box=None)

        for index, row in enumerate(self.info_table_rows()):
            if index != 0:
                table.add_row(io.EMPTY, io.EMPTY)
            table.add_row(*row)

        if table.row_count > 0:
            return Padding(table, (0, 0))

    @cached_property
    def subactions(self) -> _RT | None:
        if hasattr(self.action, "_get_subactions"):
            # pylint: disable=protected-access
            return self.help_formatter._format_actions(
                list(self.help_formatter._iter_subactions(self.action)),
                _depth=self.depth + 1,
            )

    @cached_property
    def help(self) -> _RT | None:
        if self.action.help:
            return self.help_formatter._expand_help(self.action)

    @cached_property
    def contents(self) -> _RT:
        g = io.Grouper()

        g.append(self.help)
        g.append(self.info_table)
        g.append(self.subactions)

        return g.to_group()

    @cached_property
    def type(self) -> _RT:
        if self.action.type is None:
            return io.EMPTY
        return Pretty(txt.fmt(self.action.type))

    def to_row(self) -> tuple[_RT, _RT, _RT]:
        return (self.invocation, self.type, self.contents)
