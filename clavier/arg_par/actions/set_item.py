from argparse import ArgumentTypeError, Namespace
from dataclasses import dataclass
from typing import (
    Any,
    Callable,
    Generic,
    Mapping,
    MutableMapping,
    Sequence,
    TypeVar,
    cast,
    TYPE_CHECKING,
)
from copy import copy

from clavier import err
from .clavier_action import ClavierAction

if TYPE_CHECKING:
    from ..argument_parser import ArgumentParser

K = TypeVar("K")
V = TypeVar("V")

AnyType: Callable[[str], Any] = lambda arg: arg


@dataclass(frozen=True)
class _SetItemType(Generic[K, V]):
    """Internal class used as the `argparse.Action.type` for `SetItem` actions.

    Provides the desired interface

        (str) -> (K, V)

    by composing the `split` with the `key_type` and `value_type`.
    """

    key_type: Callable[[str], K]
    value_type: Callable[[str], V]
    split: Callable[[str], tuple[str, str]]

    def __call__(self, arg: str) -> tuple[K, V]:
        s_key, s_value = self.split(arg)
        return self.key_type(s_key), self.value_type(s_value)


class SetItem(Generic[K, V], ClavierAction):
    """Action like "append" (argparse._AppendAction) but for
    `typing.MutableMapping`: sets an item in the mapping for each matching
    argument.

    The `argparse.Action.type` is composed of a `key_type` and `value_type`,
    each which map a `str` to the respective key or value.

        key_type: (str) -> K
        value_type: (str) -> V

    The default implementation for both is `AnyType`, which is the identity
    function (mapping each key or value to itself) with the return value cast as
    a `typing.Any` (which... it seems might not be necessary for the type
    checker, but that thing is fickle and I feel like picked up the habbit for
    _some_ reason).

    This action also introduces a `split` attribute, which is a function that
    takes the raw argument string and splits it into a pair of key/value
    strings.

        split: (str) -> (str, str)

    Those returned strings then become the arguments to `key_type` and
    `value_type`.

    The default implementation is `EqSplit`, which simply splits the string on
    the first `=` character.

    ```python
    >>> SetItem.eq_split("NAME=value")
    ('NAME', 'value')

    ```

    > 📝 NOTE
    >
    > Like the "append" action, this action coppies the mapping _every time_
    > an argument is added (using `copy.copy`).
    >
    > This is presumably to avoid the "mutable default" problem, where the
    > `argparse.Action.default` itself is mutated, leaving it in a bad state.
    >
    > This seems to be needed because the action can not tell when it's
    > attribute in the `argparse.Namespace` is from processing a previous
    > argument or from the action default.
    >
    > For some reason this annoys me more than it should, but the "append"
    > action has gotten along with it for however long, so I doubt it will
    > really matter.
    >
    """

    @staticmethod
    def eq_split(arg: str, /) -> tuple[str, str]:
        try:
            key, value = arg.split("=", 1)
        except BaseException as error:
            raise ArgumentTypeError(
                f"failed to split argument by '=' character: {arg!r}"
            ) from None
        return key, value

    type: _SetItemType

    def __init__(
        self,
        option_strings: Sequence[str],
        dest: str,
        default: MutableMapping[K, V] | None = None,
        key_type: Callable[[str], K] = AnyType,
        value_type: Callable[[str], V] = AnyType,
        split: Callable[[str], tuple[str, str]] = eq_split,
        required: bool = False,
        help: str | None = None,
        metavar: str | tuple[str, ...] | None = None,
    ):
        super().__init__(
            option_strings=option_strings,
            dest=dest,
            nargs=None,
            const=None,
            default=default,
            type=_SetItemType(
                key_type=key_type,
                value_type=value_type,
                split=split,
            ),
            choices=None,
            required=required,
            help=help,
            metavar=metavar,
        )

    @property
    def key_type(self) -> Callable[[str], K]:
        return self.type.key_type

    @property
    def value_type(self) -> Callable[[str], V]:
        return self.type.value_type

    @property
    def split(self) -> Callable[[str], tuple[str, str]]:
        return self.type.split

    def __call__(
        self,
        parser: "ArgumentParser",
        namespace: Namespace,
        values: tuple[K, V],
        option_string: str | None = None,
    ):
        match values:
            case (key, value):
                pass
            case _:
                raise err.ArgTypeError(
                    name="values",
                    expected_type=tuple[K, V],
                    value=values,
                )

        items = getattr(namespace, self.dest, None)
        if items is None:
            items = {}
        else:
            items = copy(items)
        items[key] = value
        setattr(namespace, self.dest, items)
