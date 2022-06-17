from typing import Any, Sequence, Tuple, Type, Union
from .txt import coordinate, fmt_class


class ArgTypeError(TypeError):
    def __init__(
        self, arg_name: str, expected: Union[type, Sequence[type]], given: Any
    ):
        if isinstance(expected, type):
            expected = (expected,)
        elif not isinstance(expected, tuple):
            expected = tuple(expected)
        super().__init__(
            f"Expected `{arg_name}` to be {coordinate(expected, 'or')}, given "
            f"{fmt_class(type(given))}: {repr(given)}",
            arg_name,
            expected,
            given,
        )

    @property
    def arg_name(self) -> str:
        return self.args[1]

    @property
    def expected(self) -> Tuple[Type]:
        return self.args[2]

    @property
    def given(self) -> Any:
        return self.args[3]


class ClavierError(Exception):
    pass


class InternalError(ClavierError):
    """Raised when something goes wrong _internally_ — something that requires a
    developer to fix. Misconfiguration, missuse, etc.

    Categorically different from a `UserError`, where the user has given the app
    bad input and can be encouraged to correct it.
    """

    pass


class UserError(ClavierError):
    """Raised when the app receives bad input from the user. These errors should
    help the user identify their mistake and correct it.

    Categorically different from an `InternalError`, where the mistake seems to
    be in the source code itself.
    """

    pass
