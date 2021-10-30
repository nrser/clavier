def add_parser(subparsers):
    parser = subparsers.add_parser(
        "builtin",
        help="Free-bees!",
    )
    parser.add_children(__name__, __path__)
