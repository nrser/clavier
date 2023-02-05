"""Facilities for embedding an interactive console that uses the same
`clavier.arg_par` functionality to define, parse and execute commands.
"""

from .embed_helpers import CmdFn, as_cmd
from .async_embedded_console import AsyncEmbeddedConsole
