from enum import IntEnum
from mudtelnet.mudtelnet import TelnetFrame, TelnetConnection, TelnetOutMessage, TelnetOutMessageType
from mudtelnet.mudtelnet import TelnetInMessage, TelnetInMessageType
from typing import List, Set, Optional, Union, Dict


class MudProtocol(IntEnum):
    TELNET = 0
    WEBSOCKET = 1


class MudProtocolHandler:

    __slots__ = ['out_events', 'in_events', "conn_id", "conn", "user", "session"]

    def __init__(self, conn: "MudConnection", conn_id: int):
        self.conn_id = conn_id
        self.conn = conn
        self.out_events: List[TelnetOutMessage] = list()
        self.in_events: List[TelnetInMessage] = list()
        self.user: Optional["GameObject"] = None
        self.session: Optional["GameSession"] = None

    def start(self):
        pass

    def process_new_bytes(self):
        pass

    def process_out_events(self):
        pass

    @property
    def stype(self):
        return self.conn.stype

    def read_from_socket(self):
        new_bytes = 0
        try:
            while True:
                data = self.conn.socket.recv(4096)
                if data:
                    new_bytes += len(data)
                    self.conn.inbox.extend(data)
        except BlockingIOError:
            if new_bytes:
                self.process_new_bytes()
        except ConnectionResetError as e:
            pass

    def write_to_socket(self) -> int:
        sent = self.conn.socket.send(self.conn.outbox)
        if sent:
            del self.conn.outbox[:sent + 1]
        return sent


class MudTelnetHandler(MudProtocolHandler):
    ptype = MudProtocol.TELNET

    __slots__ = ['telnet']

    def __init__(self, conn, conn_id):
        super().__init__(conn, conn_id)
        self.telnet = TelnetConnection()

    def start(self):
        self.telnet.start(self.conn.outbox)

    def process_new_bytes(self):
        while True:
            frame, size = TelnetFrame.parse(self.conn.inbox)
            if not frame:
                break
            del self.conn.inbox[:size]
            self.telnet.process_input_message(frame, self.conn.outbox, self.in_events)

    def process_out_events(self):
        for ev in self.out_events:
            self.telnet.process_output_message(ev, self.conn.outbox)
        self.out_events.clear()


class MudWebSocketHandler(MudProtocolHandler):
    ptype = MudProtocol.WEBSOCKET


PROTOCOL_MAP = {
    MudProtocol.TELNET: MudTelnetHandler,
    MudProtocol.WEBSOCKET: MudWebSocketHandler
}