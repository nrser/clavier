##############################################################################
# DISCLAIMER
#
# This is a shit-show of a file. I'm sorry. It just is.
#
# Originally it tried to minimally extend `argparse.HelpFormatter`, but it ended
# up having to port most if not all of it over. Hence it tries to follow what
# `argparse.HelpFormatter` does, and some of the things `argparse.HelpFormatter`
# does can be rather confusing to follow.
#
# If you see code in here that makes you go "...the fuck?", go check
# `argparse.py` and see if that's how they did it.
#
# As time wears on, I've started to try and clean it up a bit. Particularly
# right now (2023-02-04), to at least try to get rid of the huge red type
# checker warnings.
#
##############################################################################

from __future__ import annotations
from dataclasses import dataclass
from functools import cached_property
import re as _re
import shutil
from argparse import (
    SUPPRESS,
    OPTIONAL,
    ZERO_OR_MORE,
    ONE_OR_MORE,
    REMAINDER,
    PARSER,
    Action,
    HelpFormatter,
    _ArgumentGroup,
)
from textwrap import dedent
from typing import (
    Callable,
    Generator,
    Iterable,
    NamedTuple,
    ParamSpec,
    TypeVar,
    cast,
)

import splatlog
from rich.syntax import Syntax
from rich.text import Text
from rich.console import Group, RenderableType as _RT, Console
from rich.markdown import Markdown
from rich.table import Table
from rich.pretty import Pretty
from rich.columns import Columns
from rich.measure import Measurement
from rich.layout import Layout
from rich.padding import Padding

from clavier import io, err, cfg, txt

_LOG = splatlog.get_logger(__name__)
_CFG = cfg.get_scope(__name__)


TParams = ParamSpec("TParams")
TReturn = TypeVar("TReturn")


class _InfoTableRow(NamedTuple):
    name: _RT
    value: _RT


class RichHelpFormatter(HelpFormatter):
    """Formatter for `argparse.ArgumentParser` using `rich`.

    Adapted from `argparse.HelpFormatter`.
    """

    class _Section:
        formatter: RichHelpFormatter
        parent: RichHelpFormatter._Section | None
        heading: str | None
        items: list[Callable[[], _RT | None]]

        def __init__(
            self,
            formatter: RichHelpFormatter,
            parent: RichHelpFormatter._Section | None = None,
            heading: str | None = None,
        ):
            self.formatter = formatter
            self.parent = parent
            self.heading = heading
            self.items = []
            if parent is None:
                self.level = 0
            else:
                self.level = 1 + parent.level

        @property
        def title(self) -> str | None:
            if self.heading is not SUPPRESS and self.heading is not None:
                return self.heading.title()
            return None

        def get_renderable_items(self) -> tuple[_RT, ...]:
            return tuple(
                x
                for x in (f() for f in self.items)
                if x is not None and x is not io.EMPTY
            )

        def format_rich(self) -> Group | None:
            items = self.get_renderable_items()

            if len(items) == 0:
                return None

            if self.parent is None:
                return Group(*items)

            if self.title is None or self.title == "":
                return Group(*items, io.NEWLINE)
            else:
                return Group(
                    *io.header(self.title),
                    *items,
                    io.NEWLINE,
                )

        def format_help(self):
            # Note really sure what the story was here... guess it doesn't get
            # called?
            raise NotImplementedError("TODO..?!?")
            # return self.renderable

    @dataclass
    class _ActionFormatter:
        help_formatter: "RichHelpFormatter"
        action: Action

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
            if (_choices := self.action.choices) and (
                choices := tuple(_choices)
            ):
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
                    list(self.help_formatter._iter_subactions(self.action))
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

    _prog: str
    _console: Console
    _root_section: _Section
    _current_section: _Section
    _width: int

    def __init__(self, prog: str, *, width=None):
        self._prog = prog

        self._root_section = self._Section(self)
        self._current_section = self._root_section

        if width is None:
            self._width = max(
                (
                    shutil.get_terminal_size().columns - 2,
                    _CFG[{"min_width": int}],
                )
            )
        else:
            self._width = width

        self._action_invocation_max_width = (
            int(self._width * _CFG[{"invocation_ratio": float}]) - 4
        )

        self._console = io.OUT

    def _add_item(
        self,
        func: Callable[TParams, _RT | None],
        *args: TParams.args,
        **kwds: TParams.kwargs,
    ) -> None:
        self._current_section.items.append(lambda: func(*args, **kwds))

    # ========================
    # Message building methods
    # ========================

    def start_section(self, heading: str | None) -> None:
        section = self._Section(self, self._current_section, heading)
        self._add_item(section.format_rich)
        self._current_section = section

    def end_section(self) -> None:
        if self._current_section.parent is None:
            raise err.InternalError(
                "Can not end section -- current section is a root section"
            )
        self._current_section = self._current_section.parent

    def add_text(self, text: str | None) -> None:
        if text is not SUPPRESS and text is not None:
            self._add_item(self._format_text, text)

    def add_usage(
        self,
        usage: str | None,
        actions: Iterable[Action],
        groups: Iterable[_ArgumentGroup],
        prefix: str | None = "usage",
    ):
        if usage is not SUPPRESS:
            if prefix == "":
                # This is special case where code in `argparse` ends up using
                # this method to get the usage string
                self._add_item(self._format_usage, usage, actions, groups)
            else:
                self.start_section(prefix)
                self._add_item(self._format_usage, usage, actions, groups)
                self.end_section()

    def add_arguments(self, actions: Iterable[Action]) -> None:
        self._add_item(self._format_actions, actions)

    # =======================
    # Help-formatting methods
    # =======================

    def format_rich(self) -> _RT | None:
        return self._root_section.format_rich()

    def format_help(self) -> str:
        return io.render_to_string(self.format_rich())

    def _format_action(self, action: Action) -> Group:
        # determine the required width and the entry label
        action_header = self._format_action_invocation(action)

        # collect the pieces of the action help
        parts: list[_RT] = [action_header]

        # if there was help for the action, add lines of help text
        if action.help:
            help_text = self._expand_help(action)
            parts.append(help_text)

        # if there are any sub-actions, add their help as well
        for subaction in self._iter_subactions(action):
            parts.append(self._format_action(subaction))

        # return a render group
        return Group(*parts)

    def _format_action_invocation(self, action: Action) -> _RT:
        if not action.option_strings:
            default = self._get_default_metavar_for_positional(action)
            (metavar,) = self._metavar_formatter(action, default)(1)
            return str(metavar)

        else:
            # items = io.Grouper()
            items: list[Text] = []

            # if the Optional doesn't take a value, format is:
            #    -s, --long
            if action.nargs == 0:
                for option_string in action.option_strings:
                    items.append(Text(option_string, no_wrap=True))

            # if the Optional takes a value, format is:
            #    -s ARGS, --long ARGS
            else:
                default = self._get_default_metavar_for_optional(action)
                args_string = self._format_args(action, default)
                for option_string in action.option_strings:
                    items.append(
                        Text(
                            "%s %s" % (option_string, args_string),
                            no_wrap=True,
                        )
                    )

            width = sum((len(text) for text in items))

            if width > self._action_invocation_max_width:
                text = Text(",\n").join(items)
            else:
                text = Text(", ").join(items)

            return text

    def _format_actions(self, actions: Iterable[Action]) -> _RT:
        if _CFG.get({"use_table": bool}, True):
            return self._format_actions_table(actions)

        return self._format_actions_layout(actions)

    def _format_actions_table(self, actions: Iterable[Action]) -> _RT:
        rows: list[tuple[_RT, ...]] = []

        for action in actions:
            if action.help is SUPPRESS:
                continue

            invocation = self._format_action_invocation(action)
            contents = io.Grouper()

            # if there was help for the action, add lines of help text
            if action.help:
                contents.append(self._expand_help(action))

            # If the action has a default then add that (this handles arg
            # defaults)
            if action.default is not None and action.default != SUPPRESS:
                contents.append(
                    Columns(
                        [
                            Text("default", style="dim white italic"),
                            Pretty(action.default),
                        ]
                    )
                )

            # if there are any sub-actions, add their help as well
            if hasattr(action, "_get_subactions"):
                # pylint: disable=protected-access
                contents.append(
                    self._format_actions(list(self._iter_subactions(action)))
                )

            rows.append(
                (
                    "",
                    invocation,
                    ""
                    if action.type is None
                    else splatlog.lib.fmt(action.type),
                    contents.to_group(),
                )
            )

        if len(rows) == 0:
            return io.EMPTY

        table = Table(padding=(0, 2, 1, 0), show_header=False, box=None)
        table.add_column(width=0)
        table.add_column(max_width=self._action_invocation_max_width)
        table.add_column()
        table.add_column()
        for row in rows:
            table.add_row(*row)

        return table

    def _format_actions_layout(
        self, actions: Iterable[Action], _depth: int = 0
    ) -> _RT:

        action_formatters = [
            self._ActionFormatter(self, action)
            for action in actions
            if action.help != SUPPRESS
        ]

        if len(action_formatters) == 0:
            return io.EMPTY

        inv_max_width = self._action_invocation_max_width

        grouper = io.Grouper()

        inv_width = max(
            af.invocation_measurement.maximum
            for af in action_formatters
            if af.invocation_measurement.maximum < inv_max_width
        )

        _LOG.debug(
            "Rendering actions",
            inv_max_width=inv_max_width,
            inv_width=inv_width,
        )

        for af in action_formatters:
            _LOG.debug(
                "Action {} widths",
                af.action.option_strings,
                min=af.invocation_measurement.minimum,
                max=af.invocation_measurement.maximum,
                oversized=(af.invocation_measurement.maximum > inv_max_width),
            )

        table = Table(padding=(0, 1), show_header=False, box=None)
        table.add_column(width=inv_width + 2)
        table.add_column()
        table.add_column()

        grouper.append(table)

        for index, af in enumerate(action_formatters):
            if index != 0:
                table.add_row(io.EMPTY, io.EMPTY, io.EMPTY)

            if af.invocation_measurement.maximum > inv_max_width:
                grouper.append(af.invocation)
                grouper.append(io.NEWLINE)

                table = Table(padding=(0, 1), show_header=False, box=None)
                table.add_column(width=inv_width + 2)
                table.add_column()
                table.add_column()
                table.add_row(io.EMPTY, af.type, af.contents)

                grouper.append(table)

            else:
                table.add_row(af.invocation, af.type, af.contents)

        return Padding(grouper.to_group(), pad=(0, 1))

    def _format_actions_usage(
        self, actions: list[Action], groups: Iterable[_ArgumentGroup]
    ) -> _RT:
        # find group indices and identify actions in groups
        group_actions = set()
        inserts = {}
        for group in groups:
            # pylint: disable=protected-access
            try:
                start = actions.index(group._group_actions[0])
            except ValueError:
                continue
            else:
                end = start + len(group._group_actions)
                if actions[start:end] == group._group_actions:
                    for action in group._group_actions:
                        group_actions.add(action)
                    if not getattr(group, "required", None):
                        if start in inserts:
                            inserts[start] += " ["
                        else:
                            inserts[start] = "["
                        if end in inserts:
                            inserts[end] += "]"
                        else:
                            inserts[end] = "]"
                    else:
                        if start in inserts:
                            inserts[start] += " ("
                        else:
                            inserts[start] = "("
                        if end in inserts:
                            inserts[end] += ")"
                        else:
                            inserts[end] = ")"
                    for i in range(start + 1, end):
                        inserts[i] = "|"

        # collect all actions format strings
        parts = []
        for i, action in enumerate(actions):

            # suppressed arguments are marked with None
            # remove | separators for suppressed arguments
            if action.help is SUPPRESS:
                parts.append(None)
                if inserts.get(i) == "|":
                    inserts.pop(i)
                elif inserts.get(i + 1) == "|":
                    inserts.pop(i + 1)

            # produce all arg strings
            elif not action.option_strings:
                default = self._get_default_metavar_for_positional(action)
                part = self._format_args(action, default)

                # if it's in a group, strip the outer []
                if action in group_actions:
                    if part[0] == "[" and part[-1] == "]":
                        part = part[1:-1]

                # add the action string to the list
                parts.append(part)

            # produce the first way to invoke the option in brackets
            else:
                option_string = action.option_strings[0]

                # if the Optional doesn't take a value, format is:
                #    -s or --long
                if action.nargs == 0:
                    part = "%s" % option_string

                # if the Optional takes a value, format is:
                #    -s ARGS or --long ARGS
                else:
                    default = self._get_default_metavar_for_optional(action)
                    args_string = self._format_args(action, default)
                    part = "%s %s" % (option_string, args_string)

                # make it look optional if it's not required or in a group
                if not action.required and action not in group_actions:
                    part = "[%s]" % part

                # add the action string to the list
                parts.append(part)

        # insert things at the necessary indices
        for i in sorted(inserts, reverse=True):
            parts[i:i] = [inserts[i]]

        # join all the action items with spaces
        text = " ".join([item for item in parts if item is not None])

        # clean up separators for mutually exclusive groups
        open_s = r"[\[(]"
        close_s = r"[\])]"
        text = _re.sub(r"(%s) " % open_s, r"\1", text)
        text = _re.sub(r" (%s)" % close_s, r"\1", text)
        text = _re.sub(r"%s *%s" % (open_s, close_s), r"", text)
        text = _re.sub(r"\(([^|]*)\)", r"\1", text)
        text = text.strip()

        # return the text
        return text

    def _format_usage(
        self,
        usage: str | None,
        actions: Iterable[Action],
        groups: Iterable[_ArgumentGroup],
    ) -> _RT:
        # if usage is specified, use that
        if usage is not None:
            usage = usage % dict(prog=self._prog)

        # if no optionals or positionals are available, usage is just prog
        elif usage is None and not actions:
            usage = "%(prog)s" % dict(prog=self._prog)

        # if optionals and positionals are available, calculate usage
        elif usage is None:
            prog = "%(prog)s" % dict(prog=self._prog)

            # split optionals from positionals
            optionals = []
            positionals = []
            for action in actions:
                if action.option_strings:
                    optionals.append(action)
                else:
                    positionals.append(action)

            # build full usage string
            action_usage = self._format_actions_usage(
                optionals + positionals, groups
            )
            usage = " ".join([s for s in [prog, action_usage] if s])

        # https://rich.readthedocs.io/en/latest/reference/syntax.html
        return Syntax(usage, "bash", padding=(1, 2))

    def _format_text(self, text: str) -> _RT:
        text = dedent(text)
        if "%(prog)" in text:
            text = text % dict(prog=self._prog)
        return Markdown(text)

    def _iter_subactions(self, action: Action) -> Generator[Action, None, None]:
        """Addition to iterate subactions without indenting, see
        `HelpFormatter._iter_indented_subactions` for comparison.
        """
        try:
            get_subactions = cast(
                Callable[[], Iterable[Action]],
                getattr(action, "_get_subactions"),
            )
        except AttributeError:
            pass
        else:
            yield from get_subactions()

    def _metavar_formatter(
        self, action: Action, default_metavar: str | None
    ) -> Callable[[int], tuple[str | None, ...]]:
        if action.metavar is not None:
            result = action.metavar
        # elif action.choices is not None:
        #     choice_strs = [str(choice) for choice in action.choices]
        #     result = '{%s}' % ','.join(choice_strs)
        else:
            result = default_metavar

        def format(tuple_size: int) -> tuple[str | None, ...]:
            if isinstance(result, tuple):
                return result
            else:
                return (result,) * tuple_size

        return format

    # def _format_args(self, action: Action, default_metavar: str | None) -> str:
    #     get_metavar = self._metavar_formatter(action, default_metavar)
    #     if action.nargs is None:
    #         return "%s" % get_metavar(1)
    #     if action.nargs == OPTIONAL:
    #         return "[%s]" % get_metavar(1)
    #     if action.nargs == ZERO_OR_MORE:
    #         return "[%s [%s ...]]" % get_metavar(2)
    #     if action.nargs == ONE_OR_MORE:
    #         return "%s [%s ...]" % get_metavar(2)
    #     if action.nargs == REMAINDER:
    #         return "..."
    #     if action.nargs == PARSER:
    #         return "%s ..." % get_metavar(1)
    #     if action.nargs == SUPPRESS:
    #         return ""

    #     if isinstance(action.nargs, int):
    #         formats = ["%s" for _ in range(action.nargs)]
    #         return " ".join(formats) % get_metavar(action.nargs)

    #     raise ValueError(f"invalid nargs value: {action.nargs!r}")

    # def _get_default_metavar_for_positional(self, action):
    #     return action.dest

    # def _get_default_metavar_for_optional(self, action):
    #     return action.dest.upper()

    def _expand_help(self, action: Action) -> Markdown:
        params = dict(vars(action), prog=self._prog)
        for name in list(params):
            if params[name] is SUPPRESS:
                del params[name]
        for name in list(params):
            if hasattr(params[name], "__name__"):
                params[name] = params[name].__name__x
        if params.get("choices") is not None:
            choices_str = ", ".join([str(c) for c in params["choices"]])
            params["choices"] = choices_str
        return Markdown(self._get_help_string(action) % params)

    def _get_help_string(self, action: Action) -> str:
        return dedent(str(action.help))
