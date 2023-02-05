from argparse import Action, SUPPRESS


class _HelpAction(Action):
    def __init__(
        self, option_strings, dest=SUPPRESS, default=SUPPRESS, help=None
    ):
        super(_HelpAction, self).__init__(
            option_strings=option_strings,
            dest=dest,
            default=default,
            nargs=0,
            help=help,
        )

    def __call__(self, parser, namespace, values, option_string=None):
        parser.print_help()
        parser.exit()
