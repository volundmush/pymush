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

    def close_link(self):
        if not self.portal:
            return
        self.selector.unregister(self.portal.socket)
        self.portal.close()
        self.portal = None

    def connect_link(self):
        print("Attempting to connect...")
        if self.portal:
            self.close_link()
        try:
            sock = socket.create_connection((self.interface, self.port))
            print(f"SERVER LINKED TO PORTAL!")
            self.portal = LinkProtocol(sock, self.interface)
            self.selector.register(sock, selectors.EVENT_READ + selectors.EVENT_WRITE, self.portal)
        except Exception as e:
            pass

    def setup(self):
        print("is this happening?", flush=True)
        self.interface = self.app.config.interfaces.get(self.app.config.link["interface"], None)
        if self.interface is None:
            raise ValueError("Server must have a valid link interface!")
        port = self.app.config.link.get('port', 0)
        if port < 0 or port > 65535:
            raise ValueError(f"Invalid port: {port}. Port must be number between 0 and 65535")
        self.port = port

    def update(self, delta: float):
        if not self.portal:
            self.connect_link()
        if not self.portal:
            return

        self.portal.out_events.extend(self.out_events)
        self.out_events.clear()

        for key, events in self.selector.select(timeout=-1):
            if events & selectors.EVENT_READ:
                key.data.read_bytes()
                if key.data.closed:
                    self.close_link()
                if key.data.in_events:
                    self.in_events.extend(key.data.in_events)
                    key.data.in_events.clear()
            if events & selectors.EVENT_WRITE:
                key.data.write_ready = True

        if self.portal and self.portal.write_ready:
            self.portal.send_bytes()