from athanor.shared import ConnectionDetails, MudProtocol, ConnectionInMessage, ConnectionInMessageType
from athanor.shared import ConnectionOutMessage, ConnectionOutMessageType, ColorSystem
from typing import Optional, Set, List, Dict, Union
from mudstring.patches.console import MudConsole
from mudstring.util import OutBuffer
from rich.color import ColorSystem
from athanor_server.conn import Connection as BaseConnection

COLOR_MAP = {
    ColorSystem.STANDARD: "standard",
    ColorSystem.EIGHT_BIT: "256",
    ColorSystem.TRUECOLOR: "truecolor",
    ColorSystem.WINDOWS: "windows"
}


class Connection(BaseConnection):
    def __init__(self, service: "ConnectionService", details: ConnectionDetails):
        super().__init__(service, details)
        self.user: Optional["GameObject"] = None
        self.session: Optional["GameSession"] = None
        self.console = MudConsole(color_system=COLOR_MAP[details.color] if details.color else None, mxp=details.mxp_active, file=self, width=details.width)

    def flush(self):
        pass

    def write(self, b: str):
        self.out_events.append(ConnectionOutMessage(ConnectionOutMessageType.LINE, self.client_id, b))

    def on_update(self, details: ConnectionDetails):
        self.details = details
        self.console._color_system = ColorSystem(int(details.color)) if details.color else None
        self.console.mxp = details.mxp_active
        self.console._width = details.width

    def on_process_event(self, ev: ConnectionInMessage):
        if ev.msg_type == ConnectionInMessageType.LINE:
            self.print(f"ECHOING: {ev.data}")

    def print(self, *args, **kwargs):
        self.console.print(*args, **kwargs)

    def flush_out_events(self):
        pass

    def on_client_connect(self):
        pass
