from pymush.app import Application as BaseApplication
from pymush_portal.config import Config
from typing import Optional
from .net import NetService
from .link import LinkService


class Application(BaseApplication):

    def __init__(self, config: Config):
        super().__init__(config)
        self.net: Optional[NetService] = None
        self.link: Optional[LinkService] = None
