from clavier import arg_par


def add_parser(subparsers: arg_par.Subparsers) -> None:
    parser = subparsers.add_parser(
        "error",
        help="Generate various errors during various processes",
    )

    parser.add_children(__name__, __path__)
