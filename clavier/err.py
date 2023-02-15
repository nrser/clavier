from textwrap import dedent
from typing import Any, Callable
from . import txt


class ArgTypeError(TypeError):
    MULTILINE_TEMPLATE = dedent(
        """\
        Expected `{name}` to be `{expected_type}`.

        Given `{type}`:

        {value}
        """
    )

    INLINE_TEMPLATE = txt.squish(MULTILINE_TEMPLATE)

    def __init__(self, name: str, expected_type: Any, value: Any):
        message = self.MULTILINE_TEMPLATE.format(
            name=name,
            expected_type=txt.fmt(expected_type),
            type=txt.fmt_type_of(value),
            value=txt.fmt_pretty(value),
        )

        super().__init__(message)


class ReturnTypeError(TypeError):
    LONG_MESSAGE_TEMPLATE = dedent(
        """\
        Expected `{function}` to return `{expected_type}`.

        Received `{return_type}`:

        {return_value}
        """
    )

    CONDITIONAL_LONG_MESSAGE_TEMPLATE = dedent(
        """\
        Expected `{function}` to return `{expected_type}` when {when}.

        Received `{return_type}`:

        {return_value}
        """
    )

    @classmethod
    def _format_when(
        cls,
        function: str,
        expected_type: str,
        return_type: str,
        when: str | None,
    ) -> str | None:
        if when is None:
            return None
        return when.format(
            function=function,
            expected_type=expected_type,
            return_type=return_type,
        )

    @classmethod
    def format_long_message(
        cls,
        function: Callable,
        expected_type: type,
        return_value: object,
        when: str | None,
    ) -> str:
        template = (
            cls.LONG_MESSAGE_TEMPLATE
            if when is None
            else cls.CONDITIONAL_LONG_MESSAGE_TEMPLATE
        )

        function_s = txt.fmt(function)
        expected_type_s = txt.fmt(expected_type)
        return_type_s = txt.fmt_type_of(return_value)
        return_value_s = txt.fmt_pretty(return_value)

        return template.format(
            function=function_s,
            expected_type=expected_type_s,
            return_type=return_type_s,
            return_value=return_value_s,
            when=cls._format_when(
                function=function_s,
                expected_type=expected_type_s,
                return_type=return_type_s,
                when=when,
            ),
        )

    def __init__(
        self,
        function: Callable,
        expected_type: type,
        return_value: object,
        when: str | None = None,
    ):
        message = self.format_long_message(
            function, expected_type, return_value, when
        )

        super().__init__(message)


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


class ParserExit(SystemExit, ClavierError):
    """Raised by `clavier.arg_par.ArgumentParser.exit` when the argument parser
    wants to terminate during parsing, either because an error occurred or
    because an action that bails out early was triggered, like "help".

    In `argparse.ArgumentParser`, early exit is accomplished by calling
    `sys.exit`, which raises a `SystemExit` error.

    This behavior has been changed in Clavier because:

    1.  We want the ability to do something other than exit the process, such as
        when we're in a `clavier.embed` loop.

    2.  We want to be able to distinguish between exceptions that came from
        `clavier.arg_par.ArgumentParser.exit` and some `sys.exit` call in user
        code.

    3.  Much the same as deciding how and when to exit the process, we want to
        handle printing of messages and feedback at a higher level.

    """

    def __init__(self, status: int = 0, message: Any = None):
        super().__init__(status, message)

    @property
    def status(self) -> int:
        return self.args[0]

    @property
    def message(self) -> Any:
        return self.args[1]
