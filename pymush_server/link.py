from pymush.app import Service
import socket
import selectors
from typing import Optional
from pymush.shared import LinkProtocol


class LinkService(Service):

    def __init__(self):
        self.app.link = self
        self.portal: Optional[LinkProtocol] = None
        self.selector: selectors.DefaultSelector = selectors.DefaultSelector()
        self.out_events = list()
        self.in_events = list()
        self.interface: Optional[str] = None
        self.port: int = 0


    def setup(self):
        self.interface = self.app.config.interfaces.get(self.app.config.link["interface"], None)
        if self.interface is None:
            raise ValueError("Server must have a valid link interface!")
        port = self.app.config.link.get('port', 0)
        if port < 0 or port > 65535:
            raise ValueError(f"Invalid port: {port}. Port must be number between 0 and 65535")
        self.port = port