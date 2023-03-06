from clavier import arg_par


def add_parser(subparsers: arg_par.Subparsers) -> None:
    parser = subparsers.add_parser(
        "shout",
        help="""
            "shell out" in various ways...
        """,
    )

    parser.add_children(__name__, __path__)
