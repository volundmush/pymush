import time
import weakref

from typing import Optional, Set, List

from mudstring.patches.console import MudConsole
from rich.color import ColorSystem

from athanor.shared import ConnectionDetails, ConnectionInMessage, ConnectionInMessageType
from athanor.shared import ConnectionOutMessage, ConnectionOutMessageType, ColorSystem
from athanor_server.conn import Connection as BaseConnection
from athanor.utils import lazy_property

from .engine.cmdqueue import QueueEntry
from .welcome import message as WELCOME
from .utils import formatter as fmt
from .selectscreen import render_select_screen
from .utils.styling import StyleHandler


COLOR_MAP = {
    ColorSystem.STANDARD: "standard",
    ColorSystem.EIGHT_BIT: "256",
    ColorSystem.TRUECOLOR: "truecolor",
    ColorSystem.WINDOWS: "windows"
}


class Connection(BaseConnection):
    login_matchers = ('login',)
    select_matchers = ('ooc',)

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
            now = time.time()
            self.last_activity = now
            if self.session:
                entry = QueueEntry.from_ic(self.session, cmd, self)
                self.session.last_cmd = now
            elif self.user:
                entry = QueueEntry.from_ooc(self.user, cmd, self)
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
        account.last_login = time.time()
        account.connections.add(self)
        self.show_select_screen()

    def show_select_screen(self):
        self.receive_msg(render_select_screen(self))

    def logout(self):
        user = self.user
        if user:
            self.user = None
            user.connections.remove(self)

    def join_session(self, session: "GameSession"):
        session.connections.add(self)
        self.session = session
        if len(session.connections) == 1:
            session.on_first_connection(self)
        self.on_join_session(session)

    def on_join_session(self, session: "GameSession"):
        entry = QueueEntry.from_ic(self.session, 'look', self)
        self.game.queue.push(entry)

    def _find_cmd(self, entry: "QueueEntry", cmd_text: str, matcher_categories):
        for matcher_name in matcher_categories:
            matchers = self.game.command_matchers.get(matcher_name, list())
            for matcher in matchers:
                if matcher and matcher.access(entry):
                    cmd = matcher.match(entry, cmd_text)
                    if cmd:
                        return cmd

    def _gather_help(self, entry, data, matcher_categories):
        for matcher_name in matcher_categories:
            matchers = self.game.command_matchers.get(matcher_name, list())
            for matcher in matchers:
                if matcher and matcher.access(entry):
                    matcher.populate_help(entry, data)

    def find_login_cmd(self, entry: "QueueEntry", cmd_text: str):
        return self._find_cmd(entry, cmd_text, self.login_matchers)

    def find_selectscreen_cmd(self, entry: "QueueEntry", cmd_text: str):
        return self._find_cmd(entry, cmd_text, self.select_matchers)

    def gather_login_help(self, entry: "QueueEntry", data):
        self._gather_help(entry, data, self.login_matchers)

    def gather_selectscreen_help(self, entry: "QueueEntry", data):
        self._gather_help(entry, data, self.select_matchers)


class PromptHandler:

    def __init__(self, owner: "GameSession"):
        self.owner = owner
        self.last_activity = 0.0
        self.last_prompt = 0.0
        self.delta = 0.0

    def update(self, delta: float):
        diff = self.last_activity - self.last_prompt
        if diff:
            now = time.time()
            diff2 = now - self.last_activity
            if diff2 > self.owner.game.app.config.game_options['prompt_delay']:
                self.send_prompt()
                self.last_prompt = now

    def send_prompt(self):
        pass


class GameSession:
    session_matchers = ('ic',)

    def __init__(self, user: "GameObject", character: "GameObject"):
        self.user: "GameObject" = user
        weakchar = weakref.proxy(character)
        self.character: "GameObject" = weakchar
        self.puppet: "GameObject" = weakchar
        self.connections: Set["Connection"] = set()
        self.in_events: List[ConnectionInMessage] = list()
        self.out_events: List[ConnectionOutMessage] = list()
        self.admin = False
        self.character.session = self
        self.user.account_sessions.add(self)
        now = time.time()
        self.last_cmd = now
        self.created = now

    @lazy_property
    def prompt(self):
        return self.game.app.classes['game']['prompthandler'](self)

    @property
    def game(self):
        return self.user.game

    def get_alevel(self, ignore_fake=False):
        if not self.admin and not ignore_fake:
            return min(self.user.admin_level, self.character.admin_level)
        return self.user.admin_level

    @property
    def style(self):
        return self.user.style

    def msg(self, text, **kwargs):
        flist = fmt.FormatList(self, **kwargs)
        flist.add(fmt.Line(text))
        self.send(flist)

    def send(self, message: fmt.FormatList):
        self.receive_msg(message)
        for listener in self.connections:
            if listener not in message.relay_chain:
                listener.send(message.relay(self))

    def receive_msg(self, message: fmt.FormatList):
        self.prompt.last_activity = time.time()

    def on_first_connection(self, connection: "Connection"):
        pass

    def _find_cmd(self, entry: "QueueEntry", cmd_text: str, matcher_categories):
        for matcher_name in matcher_categories:
            matchers = self.game.command_matchers.get(matcher_name, list())
            for matcher in matchers:
                if matcher and matcher.access(entry):
                    cmd = matcher.match(entry, cmd_text)
                    if cmd:
                        return cmd

    def _gather_help(self, entry, data, matcher_categories):
        for matcher_name in matcher_categories:
            matchers = self.game.command_matchers.get(matcher_name, list())
            for matcher in matchers:
                if matcher and matcher.access(entry):
                    matcher.populate_help(entry, data)

    def find_cmd(self, entry: "QueueEntry", cmd_text: str):
        cmd = self._find_cmd(entry, cmd_text, self.session_matchers)
        if cmd:
            return cmd
        return self.puppet.find_cmd(entry, cmd_text)

    def gather_help(self, entry: "QueueEntry", data):
        self._gather_help(entry, data, self.session_matchers)
        self.puppet.gather_help(entry, data)

    def update(self, delta: float):
        self.prompt.update(delta)

