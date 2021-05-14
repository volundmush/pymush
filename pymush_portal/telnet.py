from asyncio import Protocol, transports
from typing import Optional, Union, Dict, Set, List
from .conn import MudConnection
from mudtelnet.mudtelnet import TelnetFrame, TelnetConnection, TelnetOutMessage, TelnetOutMessageType
from mudtelnet.mudtelnet import TelnetInMessage, TelnetInMessageType
from pymush.shared import COLOR_MAP
from pymush.shared import ConnectionInMessageType, ConnectionOutMessage, ConnectionInMessage, ConnectionOutMessageType


class TelnetMudConnection(MudConnection, Protocol):

    def __init__(self, listener):
        super().__init__(listener)
        self.telnet = TelnetConnection()
        self.telnet_in_events: List[TelnetInMessage] = list()
        self.telnet_pending_events: List[TelnetInMessage] = list()
        self.transport: Optional[transports.Transport] = None
        self.in_buffer = bytearray()

    def data_received(self, data: bytearray):
        self.in_buffer.extend(data)
        while True:
            frame, size = TelnetFrame.parse(self.in_buffer)
            if not frame:
                break
            del self.in_buffer[:size]
            events_buffer = self.telnet_in_events if self.started else self.telnet_pending_events
            out_buffer = bytearray()
            changed = self.telnet.process_input_message(frame, out_buffer, events_buffer)
            if out_buffer:
                self.transport.write(out_buffer)
            if changed:
                self.update_details(changed)
                if self.started:
                    self.in_events.append(ConnectionInMessage(ConnectionInMessageType.UPDATE, self.conn_id,
                                                              self.details))

        if self.telnet_in_events:
            self.process_telnet_events()

    def connection_made(self, transport: transports.Transport) -> None:
        self.transport = transport
        self.details.host_address = transport.get_extra_info('peername')
        out_buffer = bytearray()
        self.telnet.start(out_buffer)
        self.running = True
        self.transport.write(out_buffer)

    def update_details(self, changed: dict):
        for k, v in changed.items():
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

    def telnet_in_to_conn_in(self, ev: TelnetInMessage):
        if ev.msg_type == TelnetInMessageType.LINE:
            return ConnectionInMessage(ConnectionInMessageType.LINE, self.conn_id, ev.data)
        elif ev.msg_type == TelnetInMessageType.GMCP:
            return None
        elif ev.msg_type == TelnetInMessageType.MSSP:
            return ConnectionInMessage(ConnectionInMessageType.REQSTATUS, self.conn_id, ev.data)
        else:
            return None

    def process_telnet_events(self):
        for ev in self.telnet_in_events:
            msg = self.telnet_in_to_conn_in(ev)
            if msg:
                self.in_events.append(msg)
        self.telnet_in_events.clear()

    def conn_out_to_telnet_out(self, ev: ConnectionOutMessage):
        if ev.msg_type == ConnectionOutMessageType.LINE:
            return TelnetOutMessage(TelnetOutMessageType.LINE, ev.data)
        elif ev.msg_type == ConnectionOutMessageType.TEXT:
            return TelnetOutMessage(TelnetOutMessageType.TEXT, ev.data)
        elif ev.msg_type == ConnectionOutMessageType.PROMPT:
            return TelnetOutMessage(TelnetOutMessageType.PROMPT, ev.data)
        elif ev.msg_type == ConnectionOutMessageType.MSSP:
            return TelnetOutMessage(TelnetOutMessageType.MSSP, ev.data)
        else:
            return None

    def process_out_events(self):
        for ev in self.out_events:
            msg = self.conn_out_to_telnet_out(ev)
            if msg:
                outbox = bytearray()
                self.telnet.process_output_message(msg, outbox)
                if outbox:
                    self.transport.write(outbox)
        self.out_events.clear()
