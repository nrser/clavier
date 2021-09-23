def add_to(subparsers):
    parser = subparsers.add_parser(
        "second_level",
        help="""This is a "second level" command group""",
    )

    parser.add_children(__name__, __path__)
