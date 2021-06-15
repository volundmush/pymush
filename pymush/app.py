from typing import Optional

# Install Rich handling of console shenanigans.
from mudrich import pretty
pretty.install()

# Rich can handle untrapped tracebacks. Why not?
from mudrich import traceback
traceback.install()

from mudrich.console import Console

from athanor_server.app import Application as BaseApplication
from .game import GameService
from .config import Config


class Application(BaseApplication):
    def __init__(self, config: Config):
        super().__init__(config)
        self.game: Optional[GameService] = None
        self.console = Console()
