def add_to(subparsers):
    parser = subparsers.add_parser(
        "cmd-with-sub-cmds",
        target=run,
        help=(
            "Demonstrates a command that _also_ has sub-commands, "
            "i.e. you can call this command with args, and also call "
            "subcommands of it."
        ),
    )

    parser.add_children(__name__, __path__)

    parser.add_argument(
        "-l", "--list", action="store_true", help="List some shit."
    )


def run(list: bool):
    if list:
        return ["hey", "ho", "let's go"]
    return (
        "Yeah, you can just call this as a command, "
        "even though it has sub-commands!"
    )
