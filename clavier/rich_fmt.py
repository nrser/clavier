from __future__ import annotations
from typing import *
import re as _re
import shutil
from argparse import (
    SUPPRESS,
    OPTIONAL,
    ZERO_OR_MORE,
    ONE_OR_MORE,
    REMAINDER,
    PARSER,
)

from rich.syntax import Syntax
from rich.text import Text
from rich.console import RenderGroup
from rich.markdown import Markdown
from rich.table import Table
import splatlog as logging

from . import io

LOG = logging.getLogger(__name__)

MIN_WIDTH = 64
ARG_INVOCATION_RATIO = 0.33


class RichFormatter:
    """Formatter for `argparse.ArgumentParser` using `rich`.

    Adapted from `argparse.HelpFormatter`.
    """

    class _Section(object):
        def __init__(self, formatter, parent, heading=None):
            self.formatter = formatter
            self.parent = parent
            self.heading = heading
            self.items = []
            if parent is None:
                self.level = 0
            else:
                self.level = 1 + parent.level

        @property
        def title(self) -> Optional[str]:
            if self.heading is not SUPPRESS and self.heading is not None:
                return self.heading.title()
            return None

        @property
        def renderable_items(self):
            return list(
                filter(
                    lambda x: x is not None and x is not io.EMPTY,
                    (func(*args) for func, args in self.items),
                )
            )

        @property
        def render_group(self) -> Optional[RenderGroup]:
            return RenderGroup(*self.renderable_items)

        def format_rich(self):
            items = self.renderable_items

            if len(items) == 0:
                return None

            if self.parent is None:
                return RenderGroup(*items)

            if self.title is None or self.title == "":
                return RenderGroup(*items, io.NEWLINE)
            else:
                return RenderGroup(
                    *io.header(self.title),
                    *items,
                    io.NEWLINE,
                )

        def format_help(self):
            raise "HERE"
            # return self.renderable

    _prog: Any  # TODO Type?
    _root_section: _Section
    _current_section: _Section
    _width: int

    def __init__(self, prog, *, width=None):
        self._prog = prog

        self._root_section = self._Section(self, None)
        self._current_section = self._root_section

        if width is None:
            self._width = max(
                (shutil.get_terminal_size().columns - 2, MIN_WIDTH)
            )
        else:
            self._width = width

    def _add_item(self, func, args):
        self._current_section.items.append((func, args))

    # ===============================
    # Sizing Methods
    # ===============================

    @property
    def _action_invocation_max_width(self):
        return int(self._width * ARG_INVOCATION_RATIO)

    # ========================
    # Message building methods
    # ========================

    def start_section(self, heading):
        section = self._Section(self, self._current_section, heading)
        self._add_item(section.format_rich, [])
        self._current_section = section

    def end_section(self):
        self._current_section = self._current_section.parent

    def add_text(self, text):
        if text is not SUPPRESS and text is not None:
            self._add_item(self._format_text, [text])

    def add_usage(self, usage, actions, groups, prefix="usage"):
        if usage is not SUPPRESS:
            args = usage, actions, groups
            if prefix == "":
                # This is special case where code in `argparse` ends up using
                # this method to get the usage string
                self._add_item(self._format_usage, args)
            else:
                self.start_section(prefix)
                self._add_item(self._format_usage, args)
                self.end_section()

    def add_arguments(self, actions):
        self._add_item(self._format_actions, [actions])

    # =======================
    # Help-formatting methods
    # =======================

    def format_rich(self):
        return self._root_section.format_rich()

    def format_help(self):
        return io.render_to_string(self.format_rich())

    def _format_action_invocation(self, action):
        if not action.option_strings:
            default = self._get_default_metavar_for_positional(action)
            (metavar,) = self._metavar_formatter(action, default)(1)
            return metavar

        else:
            # items = io.RenderGrouper()
            items = []

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

    def _format_actions(self, actions):
        if len(actions) == 0:
            return io.EMPTY

        table = Table(padding=(0, 2, 1, 0), show_header=False, box=None)
        table.add_column(width=0)
        table.add_column(max_width=self._action_invocation_max_width)
        table.add_column()
        for action in actions:
            invocation = self._format_action_invocation(action)
            contents = io.RenderGrouper()

            # if there was help for the action, add lines of help text
            if action.help:
                contents.append(self._expand_help(action))

            # if there are any sub-actions, add their help as well
            if hasattr(action, "_get_subactions"):
                # pylint: disable=protected-access
                contents.append(
                    self._format_actions(list(action._get_subactions()))
                )

            table.add_row("", invocation, contents.to_group())

        return table

    def _format_actions_usage(self, actions, groups):
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
                    if not group.required:
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

    def _format_usage(self, usage, actions, groups):
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
            format_fn = self._format_actions_usage
            action_usage = format_fn(optionals + positionals, groups)
            usage = " ".join([s for s in [prog, action_usage] if s])

        # https://rich.readthedocs.io/en/latest/reference/syntax.html
        return Syntax(usage, "bash")

    def _format_text(self, text):
        if "%(prog)" in text:
            text = text % dict(prog=self._prog)
        return Markdown(text)

    def _iter_subactions(self, action):
        try:
            # pylint: disable=protected-access
            get_subactions = action._get_subactions
        except AttributeError:
            pass
        else:
            yield from get_subactions()

    def _metavar_formatter(self, action, default_metavar):
        if action.metavar is not None:
            result = action.metavar
        elif action.choices is not None:
            choice_strs = [str(choice) for choice in action.choices]
            result = "{%s}" % ",".join(choice_strs)
        else:
            result = default_metavar

        def formater(tuple_size):
            if isinstance(result, tuple):
                return result
            else:
                return (result,) * tuple_size

        return formater

    def _format_args(self, action, default_metavar):
        get_metavar = self._metavar_formatter(action, default_metavar)
        if action.nargs is None:
            result = "%s" % get_metavar(1)
        elif action.nargs == OPTIONAL:
            result = "[%s]" % get_metavar(1)
        elif action.nargs == ZERO_OR_MORE:
            result = "[%s [%s ...]]" % get_metavar(2)
        elif action.nargs == ONE_OR_MORE:
            result = "%s [%s ...]" % get_metavar(2)
        elif action.nargs == REMAINDER:
            result = "..."
        elif action.nargs == PARSER:
            result = "%s ..." % get_metavar(1)
        elif action.nargs == SUPPRESS:
            result = ""
        else:
            try:
                formats = ["%s" for _ in range(action.nargs)]
            except TypeError:
                raise ValueError("invalid nargs value") from None
            result = " ".join(formats) % get_metavar(action.nargs)
        return result

    def _get_default_metavar_for_positional(self, action):
        return action.dest

    def _format_action(self, action):
        # determine the required width and the entry label
        action_header = self._format_action_invocation(action)

        # collect the pieces of the action help
        parts = [action_header]

        # if there was help for the action, add lines of help text
        if action.help:
            help_text = self._expand_help(action)
            parts.append(help_text)

        # if there are any sub-actions, add their help as well
        for subaction in self._iter_subactions(action):
            parts.append(self._format_action(subaction))

        # return a render group
        return RenderGroup(*parts)

    def _get_default_metavar_for_optional(self, action):
        return action.dest.upper()

    def _expand_help(self, action):
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

    def _get_help_string(self, action):
        return str(action.help)
