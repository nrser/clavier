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
