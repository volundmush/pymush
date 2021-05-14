from dataclasses import dataclass
from rich.color import ColorSystem
from typing import List, Set, Optional, Union, Dict
import time
from enum import IntEnum
import zlib
import ujson
import asyncio
from asyncio import Protocol, transports
from pymush.app import Service


UNKNOWN = "UNKNOWN"


class MudProtocol(IntEnum):
    TELNET = 0
    WEBSOCKET = 1


COLOR_MAP = {
    "ansi": ColorSystem.STANDARD,
    "xterm256": ColorSystem.EIGHT_BIT,
    "truecolor": ColorSystem.TRUECOLOR
}


@dataclass
class ConnectionDetails:
    protocol: MudProtocol = 0
    client_id: str = UNKNOWN
    client_name: str = UNKNOWN
    client_version: str = UNKNOWN
    host_address: str = UNKNOWN
    host_name: str = UNKNOWN
    host_port: int = 0
    connected: float = time.time()
    utf8: bool = False
    color: Optional[ColorSystem] = None
    screen_reader: bool = False
    proxy: bool = False
    osc_color_palette: bool = False
    vt100: bool = False
    mouse_tracking: bool = False
    naws: bool = False
    width: int = 78
    height: int = 24
    mccp2: bool = False
    mccp2_active: bool = False
    mccp3: bool = False
    mccp3_active: bool = False
    mtts: bool = False
    ttype: bool = False
    mnes: bool = False
    suppress_ga: bool = False
    force_endline: bool = False
    linemode: bool = False
    mssp: bool = False


class ConnectionInMessageType(IntEnum):
    LINE = 0
    OOB = 1
    CONNECT = 2
    READY = 3
    REQSTATUS = 4
    DISCONNECT = 5
    UPDATE = 6


@dataclass
class ConnectionInMessage:
    msg_type: ConnectionInMessageType
    client_id: str
    data: object


class ConnectionOutMessageType(IntEnum):
    LINE = 0
    TEXT = 1
    PROMPT = 2
    OOB = 3
    MSSP = 4
    DISCONNECT = 5


@dataclass
class ConnectionOutMessage:
    msg_type: ConnectionOutMessageType
    client_id: str
    data: object


class PortalOutMessageType(IntEnum):
    BUNDLE = 0
    SINGLE = 1
    HELLO = 2
    SYSTEM = 3


@dataclass
class PortalOutMessage:
    msg_type: PortalOutMessageType
    process_id: int
    data: object


class ServerInMessageType(IntEnum):
    BUNDLE = 0
    SINGLE = 1
    HELLO = 2
    SYSTEM = 3


@dataclass
class ServerInMessage:
    msg_type: ServerInMessageType
    process_id: int
    data: object


class LinkProtocol(Protocol):

    def __init__(self, service):
        self.service = service
        self.transport: Optional[transports.Transport] = None
        self.compress = zlib.compressobj(9)
        self.decompress = zlib.decompressobj()
        self.in_buffer = bytearray()

    def parse_frame(self):
        """
        Given a mutable buffer, discern a message from it if possible. If there is one, remove bytes from buffer.
        """
        if len(self.in_buffer) >= 8:
            expecting = int.from_bytes(self.in_buffer[:8], byteorder='big', signed=False)
            if len(self.in_buffer) >= expecting + 8:
                decomp_data = self.decompress.decompress(self.in_buffer[8:expecting])
                js_msg = decomp_data.decode()
                js_data = ujson.loads(js_msg)
                del self.in_buffer[:expecting + 8]
                return js_data
            else:
                return None
        else:
            return None

    def connection_made(self, transport: transports.BaseTransport) -> None:
        self.transport = transport

    def data_received(self, data: bytes) -> None:
        self.in_buffer.extend(data)
        while (event := self.parse_frame()):
            self.service.in_events.put_nowait(event)

    def serialize_event(self, buffer: bytearray, event: object):
        js_data: str = ujson.dumps(event)
        js_msg = js_data.encode()
        msg = self.compress.compress(js_msg) + self.compress.flush(zlib.Z_SYNC_FLUSH)
        buffer.extend(len(msg).to_bytes(8, byteorder='big', signed=False))
        buffer.extend(msg)

    def send_event(self, ev: object):
        out_buffer = bytearray()
        self.serialize_event(out_buffer, ev)
        self.transport.write(out_buffer)


class LinkService(Service):

    def __init__(self):
        self.app.link = self
        self.link: Optional[LinkProtocol] = None
        self.interface: Optional[str] = None
        self.port: int = 0
        self.in_events: Optional[asyncio.Queue] = None
        self.out_events: Optional[asyncio.Queue] = None

    def setup(self):
        link_conf = self.app.config.link
        interface = self.app.config.interfaces.get(link_conf["interface"], None)
        if interface is None:
            raise ValueError("Portal must have a link interface!")
        self.interface = interface
        port = int(link_conf["port"])
        if port < 0 or port > 65535:
            raise ValueError(f"Invalid port: {port}. Port must be 16-bit unsigned integer")
        self.port = port

    async def async_setup(self):
        self.in_events = asyncio.Queue()
        self.out_events = asyncio.Queue()

    async def async_run(self):
        pass

    async def handle_in_events(self):
        while True:
            msg = await self.in_events.get()
            await self.app.net.in_events.put(msg)

    async def handle_out_events(self):
        while True:
            if self.link and self.link.transport:
                msg = await self.out_events.get()
                self.link.send_event(msg)
            else:
                await asyncio.sleep(1)

    def new_link(self):
        link = LinkProtocol(self)
        if self.server:
            self.close_link()
        self.server = link
        return link

    def close_link(self):
        pass


class LinkServiceServer(LinkService):

    def __init__(self):
        super().__init__()
        self.listener = None

    async def async_run(self):
        await asyncio.gather(self.listener.serve_forever(), self.handle_in_events(), self.handle_out_events())

    async def async_setup(self):
        await super().async_setup()
        loop = asyncio.get_event_loop()
        self.listener = await loop.create_server(self.new_link, self.interface, self.port, start_serving=False)


class LinkServiceClient(LinkService):
    pass