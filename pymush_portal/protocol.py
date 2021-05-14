import time
from mudtelnet.mudtelnet import TelnetFrame, TelnetConnection, TelnetOutMessage, TelnetOutMessageType
from mudtelnet.mudtelnet import TelnetInMessage, TelnetInMessageType
from typing import List, Set, Optional, Union, Dict
from pymush.shared import ConnectionDetails, ConnectionInMessageType, ConnectionOutMessage, ConnectionInMessage, ConnectionOutMessageType, MudProtocol
from rich.color import ColorSystem


class MudProtocolHandler:

    __slots__ = ['out_events', 'in_events', "conn_id", "conn", "created", "details"]

    def __init__(self, conn: "MudConnection", conn_id: str):
        self.conn_id: str = conn_id
        self.conn = conn
        self.out_events: List[ConnectionOutMessage] = list()
        self.in_events: List[ConnectionInMessage] = list()
        self.details = ConnectionDetails()
        self.details.client_id = self.conn_id
        self.created = time.time()

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
            del self.conn.outbox[:sent]
        return sent

    def health_check(self):
        pass


COLOR_MAP = {
    "ansi": ColorSystem.STANDARD,
    "xterm256": ColorSystem.EIGHT_BIT,
    "truecolor": ColorSystem.TRUECOLOR
}


class MudTelnetHandler(MudProtocolHandler):
    ptype = MudProtocol.TELNET

    __slots__ = ['telnet', 'telnet_in_events', 'telnet_pending_events', 'started']

    def __init__(self, conn, conn_id):
        super().__init__(conn, conn_id)
        self.telnet = TelnetConnection()
        self.telnet_in_events: List[TelnetInMessage] = list()
        self.telnet_pending_events: List[TelnetInMessage] = list()
        self.started: bool = False

    def start(self):
        self.telnet.start(self.conn.outbox)

    def health_check(self):
        if self.started:
            return
        if self.telnet.handshakes.has_remaining():
            cur = time.time()
            elapsed = cur - self.created
            if elapsed > 0.3:
                self.started = True
        else:
            self.started = True
        if self.started:
            if self.telnet_pending_events:
                self.in_events.append(ConnectionInMessage(ConnectionInMessageType.READY, self.conn_id, self.details))
                if self.details.mssp:
                    self.in_events.append(ConnectionInMessage(ConnectionInMessageType.REQSTATUS, self.conn_id, None))
                self.telnet_in_events.extend(self.telnet_pending_events)
                self.telnet_pending_events.clear()
                self.process_telnet_events()

    def telnet_changed(self, data: Dict):
        for k, v in data.items():
            if k in ("local", "remote"):
                for feature, value in v.items():
                    setattr(self.details, feature, value)
            elif k == "naws":
                self.details.width = v.get('width', 78)
                self.details.height = v.get('height', 24)
            elif k == "mccp2":
                for feature, val in v.items():
                    if feature == "active":
                        self.details.mccp2_active = val
            elif k == "mccp3":
                for feature, val in v.items():
                    if feature == "active":
                        self.details.mccp3_active = val
            elif k == "mtts":
                for feature, val in v.items():
                    if feature in ("ansi", "xterm256", "truecolor"):
                        if not val:
                            self.details.color = None
                        else:
                            mapped = COLOR_MAP[feature]
                            if not self.details.color:
                                self.details.color = mapped
                            else:
                                if mapped > self.details.color:
                                    self.details.color = mapped
                    else:
                        setattr(self.details, feature, val)

    def process_telnet_events(self):
        for ev in self.telnet_in_events:
            msg = None
            if ev.msg_type == TelnetInMessageType.LINE:
                msg = ConnectionInMessage(ConnectionInMessageType.LINE, self.conn_id, ev.data)
            elif ev.msg_type == TelnetInMessageType.GMCP:
                pass
            elif ev.msg_type == TelnetInMessageType.MSSP:
                msg = ConnectionInMessage(ConnectionInMessageType.REQSTATUS, self.conn_id, ev.data)
            if msg:
                self.in_events.append(msg)
        self.telnet_in_events.clear()

    def process_new_bytes(self):
        while True:
            frame, size = TelnetFrame.parse(self.conn.inbox)
            if not frame:
                break
            del self.conn.inbox[:size]
            events_buffer = self.telnet_in_events if self.started else self.telnet_pending_events
            changed = self.telnet.process_input_message(frame, self.conn.outbox, events_buffer)
            if changed:
                self.telnet_changed(changed)
                if self.started:
                    self.in_events.append(ConnectionInMessage(ConnectionInMessageType.UPDATE, self.conn_id,
                                                              self.details))
        if self.started:
            self.process_telnet_events()

    def process_out_events(self):
        for ev in self.out_events:
            msg = None
            if ev.msg_type == ConnectionOutMessageType.LINE:
                msg = TelnetOutMessage(TelnetOutMessageType.LINE, ev.data)
            elif ev.msg_type == ConnectionOutMessageType.TEXT:
                msg = TelnetOutMessage(TelnetOutMessageType.TEXT, ev.data)
            elif ev.msg_type == ConnectionOutMessageType.PROMPT:
                msg = TelnetOutMessage(TelnetOutMessageType.PROMPT, ev.data)
            elif ev.msg_type == ConnectionOutMessageType.MSSP:
                msg = TelnetOutMessage(TelnetOutMessageType.MSSP, ev.data)
            if msg:
                self.telnet.process_output_message(msg, self.conn.outbox)
        self.out_events.clear()


class MudWebSocketHandler(MudProtocolHandler):
    ptype = MudProtocol.WEBSOCKET


PROTOCOL_MAP = {
    MudProtocol.TELNET: MudTelnetHandler,
    MudProtocol.WEBSOCKET: MudWebSocketHandler
}