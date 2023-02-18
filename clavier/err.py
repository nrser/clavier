from typing import Any

from . import etc

# Re-Exports
# ============================================================================
#
# They used to live here, but then I figured I wanted to draw a line between
# `clavier.etc` and the rest: nothing in `clavier.etc` imports anything that is
# except other things in `clavier.etc` and external dependencies.
#
# So this file got split up into "general" error stuff in `clavier.etc.err` and
# the "Clavier-specific" stuff here. These re-exports are just to make it a
# bit simpler to use in practice.
#
ArgTypeError = etc.err.ArgTypeError
ReturnTypeError = etc.err.ReturnTypeError


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
