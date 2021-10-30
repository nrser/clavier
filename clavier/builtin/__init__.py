def add_parser(subparsers):
    subparsers.add_children(__name__, __path__)
