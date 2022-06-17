# SEE https://rich.readthedocs.io/en/latest/pretty.html#rich-repr-protocol

from clavier import io
from rich.pretty import Pretty
import splatlog as logging

LOG = logging.getLogger(__name__)


class Bird:
    def __init__(self, name, eats=None, fly=True, extinct=False):
        self.name = name
        self.eats = list(eats) if eats else []
        self.fly = fly
        self.extinct = extinct

    def __repr__(self):
        return f"Bird({self.name!r}, eats={self.eats!r}, fly={self.fly!r}, extinct={self.extinct!r})"

    def __rich_repr__(self):
        yield self.name
        yield "eats", self.eats
        yield "fly", self.fly, True
        yield "extinct", self.extinct, False


BIRDS = {
    "gull": Bird("gull", eats=["fish", "chips", "ice cream", "sausage rolls"]),
    "penguin": Bird("penguin", eats=["fish"], fly=False),
    "dodo": Bird("dodo", eats=["fruit"], fly=False, extinct=True),
}

logging.setup(__name__, logging.DEBUG)

LOG.info("Here!", birds=BIRDS)
