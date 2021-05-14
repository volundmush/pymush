from pymush.app import Service
import socket
import selectors
from enum import IntEnum
from typing import Optional
from pymush.shared import LinkProtocol


class LinkType(IntEnum):
    LISTENER = 0
    SERVER = 1


class LinkService(Service):

    def __init__(self):
        self.app.link = self
        self.listener: Optional[socket.socket] = None
        self.server: Optional[LinkProtocol] = None
        self.selector: selectors.DefaultSelector = selectors.DefaultSelector()

    def setup(self):
        link_conf = self.app.config.link
        interface = self.app.config.interfaces.get(link_conf["interface"], None)
        if interface is None:
            raise ValueError("Portal must have a link interface!")
        port = int(link_conf["port"])
        if port < 0 or port > 65535:
            raise ValueError(f"Invalid port: {port}. Port must be 16-bit unsigned integer")
        self.listener = socket.create_server((interface, port))
        self.listener.setblocking(False)
        self.selector.register(self.listener, selectors.EVENT_READ, LinkType.LISTENER)

    def poll(self):
        for key, events in self.selector.select(timeout=-1):
            if key.data == LinkType.LISTENER:
                self.link_server()
            elif key.data == LinkType.SERVER:
                if events & selectors.EVENT_READ:
                    self.link_read()
                if events & selectors.EVENT_WRITE:
                    if self.server:
                        self.server.write_ready = True

    def link_server(self):
        try:
            while True:
                sock, addr = self.listener.accept()
                sock.setblocking(False)
                if self.server:
                    self.close_link()
                self.selector.register(sock, selectors.EVENT_READ + selectors.EVENT_WRITE, LinkType.SERVER)
                self.server = LinkProtocol(sock, addr)
        except BlockingIOError as e:
            pass

    def link_read(self):
        if not self.server:
            return
        self.server.read_bytes()

    def link_write(self):
        if not self.server:
            return
        self.server.process_out_events()
        self.server.send_bytes()

    def close_link(self):
        self.server.close()
        self.server = None

    def update(self, delta: float):
        self.poll()
        if self.server and self.server.write_ready:
            self.server.send_bytes()
