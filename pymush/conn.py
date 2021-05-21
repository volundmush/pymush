from athanor.shared import ConnectionDetails, MudProtocol, ConnectionInMessage, ConnectionInMessageType
from athanor.shared import ConnectionOutMessage, ConnectionOutMessageType, ColorSystem
from typing import Optional, Set, List, Dict, Union
from mudstring.patches.console import MudConsole
from mudstring.util import OutBuffer
from rich.color import ColorSystem
from athanor_server.conn import Connection as BaseConnection
import time
from .engine.cmdqueue import QueueEntry
from .utils.welcome import message as WELCOME
from .utils import formatter as fmt
from .utils.selectscreen import render_select_screen
from .utils.styling import StyleHandler

COLOR_MAP = {
    ColorSystem.STANDARD: "standard",
    ColorSystem.EIGHT_BIT: "256",
    ColorSystem.TRUECOLOR: "truecolor",
    ColorSystem.WINDOWS: "windows"
}


class Connection(BaseConnection):
    def __init__(self, service: "ConnectionService", details: ConnectionDetails):
        super().__init__(service, details)
        self.connected = details.connected
        self.last_activity = self.connected
        self.user: Optional["GameObject"] = None
        self.session: Optional["GameSession"] = None
        self.console = MudConsole(color_system=COLOR_MAP[details.color] if details.color else None,
                                  mxp=details.mxp_active, file=self, width=details.width)
        self.menu = None
        self.conn_style = StyleHandler(self, save=False)

    @property
    def style(self):
        if self.user:
            return self.user.style
        return self.conn_style

    @property
    def game(self):
        return self.service.app.game

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
            cmd: str = ev.data
            if cmd.upper() == "IDLE":
                return
            self.last_activity = time.time()
            if self.session:
                entry = QueueEntry.from_session(self.session, cmd, self)
            elif self.user:
                entry = QueueEntry.from_selectscreen(self.user, cmd, self)
            else:
                entry = QueueEntry.from_login(self, cmd)
            self.game.queue.push(entry)

    def print(self, *args, **kwargs):
        self.console.print(*args, **kwargs)

    def flush_out_events(self):
        pass

    def on_client_connect(self):
        self.print(WELCOME)

    def listeners(self):
        return []

    def parser(self):
        return Parser(self.core, self.objid, self.objid, self.objid)

    def msg(self, text, **kwargs):
        flist = fmt.FormatList(self, **kwargs)
        flist.add(fmt.Line(text))
        self.send(flist)

    def send(self, message: fmt.FormatList):
        self.receive_msg(message)
        for listener in self.listeners():
            if listener not in message.relay_chain:
                listener.send(message.relay(self))

    def receive_msg(self, message: fmt.FormatList):
        message.send(self)

    def login(self, account: "GameObject"):
        self.user = account
        account.connections.add(self)
        self.receive_msg(render_select_screen(self))

    def logout(self):
        user = self.user
        if user:
            self.user = None
            user.connections.remove(self)
