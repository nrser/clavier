def add_parser(subparsers):
    parser = subparsers.add_parser(
        "generate",
        aliases=["gen"],
        help="Generate commands and (maybe) other things",
    )
    parser.add_children(__name__, __path__)
