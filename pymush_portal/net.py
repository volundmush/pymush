import ssl
import asyncio
from typing import Optional, Union, List, Dict, Set
from pymush.app import Service
import websockets
from .conn import MudConnection
from .telnet import TelnetMudConnection
from .websocket import WebSocketConnection
from enum import IntEnum


class MudProtocol(IntEnum):
    TELNET = 0
    WEBSOCKET = 1


class MudListener:
    __slots__ = ['service', 'name', 'interface', 'port', 'protocol', 'ssl_context', 'server']

    def __init__(self, service: "NetService", name: str, interface: str, port: int, protocol: MudProtocol,
                 ssl_context: Optional[ssl.SSLContext] = None):
        self.service: "NetService" = service
        self.name: str = name
        self.interface: str = interface
        self.port: int = port
        self.protocol: MudProtocol = protocol
        self.ssl_context: Optional[ssl.SSLContext] = ssl_context
        self.server = None

    async def async_setup(self):
        if self.protocol == MudProtocol.TELNET:
            loop = asyncio.get_event_loop()
            self.server = await loop.create_server(self.accept_telnet, self.interface, self.port,
                                             ssl=self.ssl_context, start_serving=False)
        elif self.protocol == MudProtocol.WEBSOCKET:
            self.server = websockets.serve(self.accept_websocket, self.interface, self.port,
                                           ssl=self.ssl_context)

    def accept_telnet(self):
        conn = TelnetMudConnection(self)
        self.service.mudconnections[conn.conn_id] = conn
        return conn

    def accept_websocket(self, ws, path):
        conn = WebSocketConnection(self, ws, path)
        self.service.mudconnections[conn.conn_id] = conn
        return conn.run()

    async def run(self):
        if self.protocol == MudProtocol.TELNET:
            await self.server.serve_forever()
        elif self.protocol == MudProtocol.WEBSOCKET:
            await self.server


class NetService(Service):
    __slots__ = ['app', 'ssl_contexts', 'listeners', 'listeners', 'mudconnections', 'interfaces', 'selector',
                 'ready_listeners', 'ready_readers', 'ready_writers']

    def __init__(self):
        self.app.net = self
        self.listeners: Dict[str, MudListener] = dict()
        self.mudconnections: Dict[str, MudConnection] = dict()
        self.in_events: Optional[asyncio.Queue] = None
        self.out_events: Optional[asyncio.Queue] = None

    def register_listener(self, name: str, interface: str, port: int, protocol: MudProtocol,
                          ssl_context: Optional[str] = None):
        if name in self.listeners:
            raise ValueError(f"A Listener is already using name: {name}")
        host = self.app.config.interfaces.get(interface, None)
        if host is None:
            raise ValueError(f"Interface not registered: {interface}")
        if port < 0 or port > 65535:
            raise ValueError(f"Invalid port: {port}. Port must be number between 0 and 65535")
        ssl = self.app.config.tls_contexts.get(ssl_context, None)
        if ssl_context and not ssl:
            raise ValueError(f"SSL Context not registered: {ssl_context}")
        listener = MudListener(self, name, host, port, protocol, ssl_context=ssl)
        self.listeners[name] = listener

    def setup(self):
        for name, config in self.app.config.listeners.items():
            try:
                protocol = MudProtocol(config.get("protocol", -1))
            except ValueError:
                raise ValueError(f"Must provide a valid protocol for {name}!")
            self.register_listener(name, config.get("interface", None), config.get("port", -1), protocol, config.get("ssl", None))

    async def async_setup(self):
        self.in_events = asyncio.Queue()
        self.out_events = asyncio.Queue()
        for listener in self.listeners.values():
            await listener.async_setup()

    async def async_run(self):
        gathered = asyncio.gather(*[l.run() for l in self.listeners.values()])
        await gathered