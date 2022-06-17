def add_parser(subparsers):
    parser = subparsers.add_parser(
        "config",
        aliases=["cfg"],
        help="Manipulate configuration.",
    )
    parser.add_children(__name__, __path__)
