import mudstring
mudstring.install()

from rich import pretty
pretty.install()

from athanor_server.app import Application as BaseApplication
from .game import GameService

from .config import Config
from typing import Optional, List, Set, Dict, Union


class Application(BaseApplication):

    def __init__(self, config: Config):
        super().__init__(config)
        self.game: Optional[GameService] = None
