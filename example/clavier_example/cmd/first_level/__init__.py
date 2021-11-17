def add_to(subparsers):
    parser = subparsers.add_parser(
        "first_level",
        aliases=["fl"],
        help="""This is a "first level" command group""",
    )

    parser.add_children(__name__, __path__)
