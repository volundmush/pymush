import ssl
import socket
import selectors
from enum import IntEnum
from typing import Optional, Union, List, Dict, Set
from .protocol import MudProtocol, MudTelnetHandler, MudWebSocketHandler, PROTOCOL_MAP, MudProtocolHandler


class SocketType(IntEnum):
    LISTENER = 0
    CONNECTION = 1


class MudConnection:
    stype = SocketType.CONNECTION

    def __init__(self, sock: socket.socket, addr, ssl_context: Optional[ssl.SSLContext]):
        self.socket: Union[socket.socket, ssl.SSLSocket] = sock if not ssl_context else \
            ssl_context.wrap_socket(sock, server_side=True)
        self.addr = addr
        self.ssl_context: Optional[ssl.SSLContext] = ssl_context
        self.inbox: bytearray = bytearray()
        self.outbox: bytearray = bytearray()


class MudListener:
    stype = SocketType.LISTENER

    __slots__ = ['manager', 'name', 'interface', 'port', 'protocol', 'ssl_context', 'socket']

    def __init__(self, manager: "MudNetManager", name: str, interface: str, port: int, protocol: MudProtocol,
                 ssl_context: Optional[ssl.SSLContext] = None):
        self.manager: "MudNetManager" = manager
        self.name: str = name
        self.interface: str = interface
        self.port: int = port
        self.protocol: MudProtocol = protocol
        self.ssl_context: Optional[ssl.SSLContext] = ssl_context
        self.socket = socket.create_server((interface, port))
        self.socket.setblocking(False)


class MudNetManager:

    __slots__ = ['app', 'ssl_contexts', 'listeners', 'listeners', 'mudconnections', 'interfaces', 'selector', 'ready_listeners',
                 'ready_readers', 'ready_writers']

    def __init__(self, app):
        self.app = app
        self.ssl_contexts: Dict[str, ssl.SSLContext] = dict()
        self.listeners: Dict[str, MudListener] = dict()
        self.mudconnections: Dict[int, MudProtocolHandler] = dict()
        self.interfaces: Dict[str, str] = {
            "localhost":  "localhost",
            "any": "",
            "public": socket.gethostname()
        }
        self.selector: selectors.DefaultSelector = selectors.DefaultSelector()
        self.ready_listeners: Set[MudListener] = set()
        self.ready_readers: Set[MudProtocolHandler] = set()
        self.ready_writers: Set[MudProtocolHandler] = set()

    def register_listener(self, name: str, interface: str, port: int, protocol: MudProtocol,
                          ssl_context: Optional[str] = None):
        if name in self.listeners:
            raise ValueError(f"A Listener is already using name: {name}")
        host = self.interfaces.get(interface, None)
        if not host:
            raise ValueError(f"Interface not registered: {interface}")
        if port < 0 or port > 65535:
            raise ValueError(f"Invalid port: {port}. Port must be number between 0 and 65535")
        ssl = self.ssl_contexts.get(ssl_context, None)
        if ssl_context and not ssl:
            raise ValueError(f"SSL Context not registered: {ssl_context}")
        listener = MudListener(self, name, host, port, protocol, ssl_context=ssl)
        self.listeners[name] = listener
        self.selector.register(listener.socket, selectors.EVENT_READ, listener)

    def register_interface(self, name, interface):
        self.interfaces[name] = interface

    def register_ssl(self, name, pem_path):
        pass

    def poll(self):
        self.ready_listeners.clear()
        self.ready_readers.clear()
        # ready writers are not cleared because sometimes they're ready to write but have no data waiting.

        for key, events in self.selector.select(timeout=-1):
            if key.data.stype == SocketType.LISTENER:
                self.ready_listeners.add(key.data)
            elif key.data.stype == SocketType.CONNECTION:
                if key.events & selectors.EVENT_READ:
                    self.ready_readers.add(key.data)
                if key.events & selectors.EVENT_WRITE:
                    self.ready_writers.add(key.data)

    def accept_connections(self):
        for listener in self.ready_listeners:
            try:
                while True:
                    sock, addr = listener.socket.accept()
                    fd = sock.fileno()
                    sock.setblocking(False)
                    conn = MudConnection(sock, addr, listener.ssl_context)
                    proto = PROTOCOL_MAP[listener.protocol](conn, fd)
                    self.mudconnections[fd] = proto
                    proto.start()
                    self.selector.register(sock, selectors.EVENT_READ + selectors.EVENT_WRITE, proto)
            except BlockingIOError as e:
                pass

    def write_bytes(self):
        written = set()
        for proto in self.ready_writers:
            if not proto.conn.outbox:
                continue
            if proto.write_to_socket():
                written.add(proto)
        self.ready_writers -= written

    def read_bytes(self):
        for proto in self.ready_readers:
            proto.read_from_socket()