from dataclasses import dataclass
from rich.color import ColorSystem
from typing import List, Set, Optional, Union, Dict
import time
from enum import IntEnum
import zlib
import ujson

UNKNOWN = "UNKNOWN"


class MudProtocol(IntEnum):
    TELNET = 0
    WEBSOCKET = 1


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


class LinkProtocol:

    def __init__(self, sock, addr):
        self.socket = sock
        self.address = addr
        self.compress = zlib.compressobj(9)
        self.decompress = zlib.decompressobj()
        self.write_ready = False
        self.expecting = None
        self.in_buffer = bytearray()
        self.out_buffer = bytearray()
        self.in_events = list()
        self.out_events = list()
        self.closed = False

    def read_bytes(self):
        try:
            read_bytes = 0
            while True:
                data = self.socket.recv(4096)
                read_bytes += len(data)
                self.in_buffer.extend(data)
        except BlockingIOError as e:
            pass

        while len(self.in_buffer):
            if self.expecting is None:
                if len(self.in_buffer) >= 8:
                    self.expecting = int.from_bytes(self.in_buffer[:8], byteorder='big', signed=False)
                    del self.in_buffer[:8]
            if len(self.in_buffer) >= self.expecting:
                msg = self.in_buffer[:self.expecting]
                del self.in_buffer[:self.expecting]
                self.expecting = None
                decomp_data = self.decompress.decompress(msg)
                js_msg = decomp_data.decode()
                js_data = ujson.loads(js_msg)
                self.in_events.append(js_data)

    def send_bytes(self):
        if not self.write_ready:
            return
        if not self.out_buffer:
            return

        sent = 0
        try:
            while True:
                more_sent = self.socket.send(self.out_buffer)
                sent += more_sent
        except BlockingIOError as e:
            sent += e.characters_written
            self.write_ready = False

        if sent:
            del self.out_buffer[:sent]

    def process_out_events(self):
        for ev in self.out_events:
            js_data: str = ujson.dumps(ev)
            js_msg = js_data.encode()
            msg = self.compress.compress(js_msg) + self.compress.flush(zlib.Z_SYNC_FLUSH)
            self.out_buffer.extend(len(msg).to_bytes(8, byteorder='big', signed=False))
            self.out_buffer.extend(msg)

        self.out_events.clear()

    def close(self):
        self.socket.close()
