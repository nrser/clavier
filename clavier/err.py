from .txt import coordinate, fmt_class

class ArgTypeError(TypeError):
    def __init__(self, arg_name, expected, given):
        super().__init__(
            f"Expected `{arg_name}` to be {coordinate(expected, 'or')}, given "
            f"{fmt_class(type(given))}: {repr(given)}"
        )

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
