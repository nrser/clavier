from argparse import OPTIONAL, Action, SUPPRESS, Namespace
from typing import TYPE_CHECKING, Any, Sequence

import splatlog

from clavier import cfg

if TYPE_CHECKING:
    from .argument_parser import ArgumentParser


class ClavierAction(Action):
    _propagate: bool

    def __init__(self, *args, propagate: bool = False, **kwds):
        super().__init__(*args, **kwds)
        self._propagate = propagate

    def propagate(self) -> bool:
        return self._propagate


class StoreSetting(ClavierAction):
    _log = splatlog.LoggerProperty()

    _key: cfg.Key
    _wrapped_action: Action
    _wrapped_namespace: Namespace

    def __init__(
        self,
        option_strings: Sequence[str],
        dest: str,
        key: cfg.Key,
        wrapped_action: type[Action],
        propagate: bool = False,
        **kwds
    ):
        self._key = key

        self._wrapped_action = wrapped_action(
            option_strings=option_strings,
            dest=self._wrapped_dest,
            **kwds,
        )

        self._wrapped_namespace = Namespace()

        super().__init__(
            option_strings=option_strings,
            dest=SUPPRESS,
            nargs=self._wrapped_action.nargs,
            const=self._wrapped_action.const,
            default=self._wrapped_action.default,
            type=self._wrapped_action.type,
            choices=self._wrapped_action.choices,
            required=self._wrapped_action.required,
            help=self._wrapped_action.help,
            # Since we inject `dest=SUPPRESS` to avoid this action's value
            # being added to the parsed `Namespace` we want to explicitly
            # default the `metavar`, otherwise you'll see things like
            #
            #       -O ==SUPPRESS==
            #
            # in the help output.
            metavar=(self._wrapped_action.metavar or dest.upper()),
            propagate=propagate,
        )

    @property
    def _splatlog_self_(self) -> Any:
        return self._key

    @property
    def _wrapped_dest(self) -> str:
        return "__setting_" + str(self._key).replace(".", "__")

    def __call__(
        self,
        parser: "ArgumentParser",
        namespace: Namespace,
        values: str | Sequence[Any] | None,
        option_string: str | None = None,
    ):
        self._log.debug("Invoking action...")

        self._wrapped_action(
            parser, self._wrapped_namespace, values, option_string
        )
        value = getattr(self._wrapped_namespace, self._wrapped_dest)

        with cfg.changeset(action=self, parser=parser) as config:
            config[self._key] = value

        if hasattr(namespace, self.dest):
            delattr(namespace, self.dest)


class _HelpAction(Action):
    def __init__(
        self, option_strings, dest=SUPPRESS, default=SUPPRESS, help=None
    ):
        super(_HelpAction, self).__init__(
            option_strings=option_strings,
            dest=dest,
            default=default,
            nargs=0,
            help=help,
        )

    def __call__(self, parser, namespace, values, option_string=None):
        parser.print_help()
        parser.exit()
