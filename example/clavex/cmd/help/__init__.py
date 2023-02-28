from clavier import arg_par


def add_parser(subparsers: arg_par.Subparsers) -> None:
    parser = subparsers.add_parser(
        "help",
        help="Play with the generated -h, --help output",
    )

    parser.add_children(__name__, __path__)
