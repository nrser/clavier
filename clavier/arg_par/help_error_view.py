from clavier import io, err


class HelpErrorView(io.ErrorView):
    def render_rich(self):
        io.render_to_console(self.data.format_rich_help())

    def render_json(self):
        raise err.UserError("Help not available as JSON")
