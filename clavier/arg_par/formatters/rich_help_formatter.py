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
import re as _re
from argparse import (
    SUPPRESS,
    OPTIONAL,
    ZERO_OR_MORE,
    ONE_OR_MORE,
    REMAINDER,
    PARSER,
    _HelpAction,
    Action,
    HelpFormatter,
    _ArgumentGroup,
)
from textwrap import dedent
from typing import (
    Callable,
    Generator,
    Iterable,
    ParamSpec,
    TypeVar,
    cast,
)
from clavier.arg_par.actions import ClavierAction, ShortHelpAction

import splatlog
from rich.syntax import Syntax
from rich.text import Text
from rich.console import Group, RenderableType as _RT, Console
from rich.markdown import Markdown
from rich.table import Table
from rich.padding import Padding
from rich.highlighter import RegexHighlighter
from rich.rule import Rule
from rich.style import Style as _S

from clavier import io, err, cfg
from .rich_action_formatter import RichActionFormatter
from .rich_section_formatter import RichSectionFormatter

_LOG = splatlog.get_logger(__name__)
_CFG = cfg.get_scope(__name__)


TParams = ParamSpec("TParams")
TReturn = TypeVar("TReturn")


class InvocationHighLighter(RegexHighlighter):
    base_style = "help.action.invocation."

    highlights = [
        r"(?P<flag>--[^\s=]+)(?:[\s=](?P<metavar>\w+))?",
        r"(?P<flag>-\w)(?:\s(?P<metavar>\w+))?",
        r"\A(?P<metavar>\w+)",
        r"\s(?P<metavar>\w+)",
    ]


class RichHelpFormatter(HelpFormatter):
    """Formatter for `argparse.ArgumentParser` using `rich`.

    Adapted from `argparse.HelpFormatter`.
    """

    _log = splatlog.LoggerProperty()

    _Section = RichSectionFormatter
    _ActionFormatter = RichActionFormatter

    @classmethod
    def _fetch_config(cls) -> tuple[int, int, float]:
        min_width, indent, invocation_ratio = _CFG._extract_(
            ("min_width", int),
            ("indent", int),
            ("invocation_ratio", float),
        )

        if min_width <= 0:
            raise ValueError(
                f"Configured value for {_CFG._key_ / 'min_width'} must be "
                f"positive integer; found {min_width!r}"
            )

        if indent < 0 or indent % 2 != 0:
            raise ValueError(
                f"Configured value for {_CFG._key_ / 'indent'} must be "
                f"non-negative even integer; found {indent!r}"
            )

        if not (0 <= invocation_ratio <= 1):
            raise ValueError(
                f"Configured value for {_CFG._key_ / 'invocation_ratio'} must "
                f"be in [0, 1]; found {invocation_ratio!r}"
            )

        return min_width, indent, invocation_ratio

    _prog: str
    _console: Console
    _short: bool
    _width: int
    _indent: int

    _root_section: _Section
    _current_section: _Section

    def __init__(
        self,
        prog: str,
        *,
        console: Console = io.OUT,
        short: bool = False,
        width: int | None = None,
    ):
        self._prog = prog

        self._root_section = self._Section(self)
        self._current_section = self._root_section

        min_width, indent, invocation_ratio = self._fetch_config()

        self._indent = indent

        if width is None:
            self._width = max(console.width, min_width)
        else:
            self._width = max(width, min_width)

        self._action_invocation_max_width = int(
            self._width * invocation_ratio
        ) - (indent * 2)

        self._console = console
        self._short = short

    @property
    def _splatlog_self_(self):
        return {"prog": self.prog}

    @property
    def prog(self) -> str:
        return self._prog

    @property
    def short(self) -> bool:
        return self._short

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

    def add_header(self) -> None:
        self._add_item(self._format_header)

    # =======================
    # Help-formatting methods
    # =======================

    def format_rich(self) -> _RT | None:
        return self._root_section.format_rich()

    def format_help(self) -> str:
        return io.render_to_string(self.format_rich())

    # Internal Methods
    # ========================================================================

    def _format_header(self) -> _RT:
        commands = self._prog.split()
        # text = " > ".join(commands) + " Command"
        text = " ➤ ".join(commands) + " Command"

        # if commands:
        #     text = f"{name} | {' '.join(commands)} Command"
        # else:
        #     text = name

        return Group(
            Text(
                text,
                justify="center",
                style="help.header.text",
            ),
            Rule(style="help.header.rule"),
        )

    def _format_action_invocation(self, action: Action) -> _RT:
        if not action.option_strings:
            default = self._get_default_metavar_for_positional(action)
            (metavar,) = self._metavar_formatter(action, default)(1)

            if metavar is None:
                return ""

            text = Text(metavar)
            InvocationHighLighter().highlight(text)
            return text

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
                text = Text(",\n" + (" " * self._indent)).join(items)
            else:
                text = Text(", ").join(items)

            InvocationHighLighter().highlight(text)

            return text

    def _is_formatting_action(self, action: Action) -> bool:
        # Suppressed actions are always omitted
        if action.help == SUPPRESS:
            return False

        if self._short:
            # Omit help actions themselves in short format
            if isinstance(action, (_HelpAction, ShortHelpAction)):
                return False

            # Omit inherited actions in short format
            if isinstance(action, ClavierAction) and action.is_inherited:
                return False

        # Everything else is ok (for now)
        return True

    def _format_actions(
        self,
        actions: Iterable[Action],
        _depth: int = 0,
    ) -> _RT:
        action_formatters = [
            self._ActionFormatter(
                formatter=self,
                action=action,
                depth=_depth,
            )
            for action in actions
            if self._is_formatting_action(action)
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

        def make_table():
            table = Table(
                padding=(0, self._indent // 2), show_header=False, box=None
            )
            table.add_column(width=inv_width + self._indent)
            table.add_column()
            table.add_column()

            return table

        table = make_table()
        grouper.append(table)

        for index, af in enumerate(action_formatters):
            if index != 0:
                table.add_row(io.EMPTY, io.EMPTY, io.EMPTY)

            if af.invocation_measurement.maximum > inv_max_width:
                grouper.append(
                    Padding(af.invocation, pad=(0, self._indent // 2))
                )
                grouper.append(io.NEWLINE)

                table = make_table()
                table.add_row(af.labels, af.type, af.contents)

                grouper.append(table)

            else:
                table.add_row(
                    Group(
                        af.invocation,
                        af.labels,
                    ),
                    af.type,
                    af.contents,
                )

        return Padding(grouper.to_group(), pad=(0, self._indent // 2))

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
        return Syntax(
            usage, "bash", padding=(1 if self._short else 1, self._indent)
        )

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
                params[name] = params[name].__name__
        if params.get("choices") is not None:
            choices_str = ", ".join([str(c) for c in params["choices"]])
            params["choices"] = choices_str
        return Markdown(self._get_help_string(action) % params)

    def _get_help_string(self, action: Action) -> str:
        return dedent(str(action.help))
