from clavier import arg_par


def add_parser(subparsers: arg_par.Subparsers):
    subparsers.add_children(__name__, __path__)
