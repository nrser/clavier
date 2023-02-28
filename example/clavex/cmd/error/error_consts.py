from clavier import err

ERROR_TYPES: dict[str, type[BaseException]] = {
    "exception": Exception,
    "runtime": RuntimeError,
    "internal": err.InternalError,
    "user": err.UserError,
    "system_exit": SystemExit,
    "parser_exit": err.ParserExit,
}
