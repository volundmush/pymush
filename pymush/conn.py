import time
import weakref

from typing import Optional, Set, List, Tuple

from mudrich.console import Console
from mudrich.color import ColorSystem
from mudrich.console import _null_highlighter
from mudrich.traceback import Traceback
from mudrich.box import ASCII
from mudrich.text import Text

from athanor.shared import (
    ConnectionDetails,
    ConnectionInMessage,
    ConnectionInMessageType,
)
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
    ColorSystem.WINDOWS: "windows",
}


class Connection(BaseConnection):
    login_matchers = ("login",)
    select_matchers = ("ooc",)

    def __init__(self, service: "ConnectionService", details: ConnectionDetails):
        super().__init__(service, details)
        self.connected = details.connected
        self.last_activity = self.connected
        self.user: Optional["GameObject"] = None
        self.session: Optional["GameSession"] = None
        self.console = Console(
            color_system=COLOR_MAP[details.color] if details.color else None,
            mxp=details.mxp_active,
            file=self,
            width=details.width,
        )
        self._repr_highlighter = self.console.highlighter
        self.console.highlighter = _null_highlighter
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
        self.out_gamedata.append(("line", (b,), dict()))

    def on_update(self, details: ConnectionDetails):
        self.details = details
        self.console._color_system = (
            ColorSystem(int(details.color)) if details.color else None
        )
        self.console.mxp = details.mxp_active
        self.console._width = details.width

    def on_process_event(self, ev: ConnectionInMessage):
        if ev.msg_type == ConnectionInMessageType.GAMEDATA:
            now = time.time()
            for cmd, args, kwargs in ev.data:
                if cmd in ("text", "line"):
                    command = args[0]
                    if command.upper() == "IDLE":
                        return
                    self.last_activity = now
                    if self.session:
                        entry = QueueEntry.from_ic(self.session, command, self)
                        self.session.last_cmd = now
                    elif self.user:
                        entry = QueueEntry.from_ooc(self.user, command, self)
                    else:
                        entry = QueueEntry.from_login(self, command)
                    self.game.queue.push(entry)

    def print(self, *args, **kwargs):
        self.console.print(*args, highlight=False, **kwargs)

    def print_exception(self, trace):
        tb = Traceback(trace=trace, width=self.console.width, box=ASCII)
        self.console.print(tb)

    def print_python(self, *args, **kwargs):
        self.console.highlighter = self._repr_highlighter
        self.console.print(*args, **kwargs)
        self.console.highlighter = _null_highlighter

    def on_client_connect(self):
        self.show_welcome_screen()

    def show_welcome_screen(self):
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

    async def create_user(self, entry: "QueueEntry", name: str, password: str) -> Tuple[bool, Optional[Text]]:
        pass_hash = self.game.crypt_con.hash(password)
        user, error = await self.game.create_object(entry, "USER", name)
        if error:
            return False, Text(error)
        await user.change_password(pass_hash, nohash=True)

        cmd = (
            f'connect "{user.name}" <password>'
            if " " in user.name
            else f"connect {user.name} <password>"
        )
        self.msg(text="User Account created! You can login with " + ansi_fun("hw", cmd))

    async def check_login(self, entry: "QueueEntry", name: str, password: str) -> Tuple[bool, Optional[Text]]:
        candidates = self.game.type_index["USER"]
        user, error = await self.game.search_objects(entry, name, candidates=candidates, exact=True)
        if error:
            return False, Text("Sorry, that was an incorrect username or password.")
        if not user:
            return False, Text("Sorry, that was an incorrect username or password.")
        if not await user.check_password(password):
            return False, Text("Sorry, that was an incorrect username or password.")
        await self.login(entry, user)
        return True, None

    async def login(self, entry: "QueueEntry", user: "GameObject"):
        self.user = user
        user.last_login = time.time()
        user.connections.add(self)
        await self.show_select_screen(entry)
        if len(user.connections) == 1:
            await user.on_first_connection_login(entry, self)
        await user.on_connection_login(entry, self)

    async def show_select_screen(self, entry: "QueueEntry"):
        self.receive_msg(render_select_screen(self))

    async def terminate(self, entry: "QueueEntry"):
        if self.session:
            await self.leave_session(entry)
        if self.user:
            await self.logout(entry)
        self.disconnect = True

    async def logout(self, entry: "QueueEntry"):
        user = self.user
        if user:
            self.user = None
            user.connections.remove(self)
            await user.on_connection_logout(entry, self)
            if not user.connections:
                await user.on_final_connection_logout(entry, self)

    async def leave_session(self, entry: "QueueEntry"):
        if not self.session:
            return
        session = self.session
        session.connections.remove(self)
        await session.on_connection_leave(entry, self)
        if not session.connections:
            await session.on_final_connection_leave(entry, self)
        self.session = None

    async def join_session(self, entry: "QueueEntry", session: "GameSession"):
        session.connections.add(self)
        self.session = session
        if len(session.connections) == 1:
            await session.on_first_connection(entry, self)
        await self.on_join_session(entry, session)

    async def on_join_session(self, entry: "QueueEntry", session: "GameSession"):
        entry = QueueEntry.from_ic(self.session, "look", self)
        self.game.queue.push(entry)

    async def _find_cmd(self, entry: "QueueEntry", cmd_text: str, matcher_categories):
        for matcher_name in matcher_categories:
            matchers = self.game.command_matchers.get(matcher_name, list())
            for matcher in matchers:
                if matcher and await matcher.access(entry):
                    cmd = await matcher.match(entry, cmd_text)
                    if cmd:
                        return cmd

    async def _gather_help(self, entry, data, matcher_categories):
        for matcher_name in matcher_categories:
            matchers = self.game.command_matchers.get(matcher_name, list())
            for matcher in matchers:
                if matcher and await matcher.access(entry):
                    await matcher.populate_help(entry, data)

    async def find_login_cmd(self, entry: "QueueEntry", cmd_text: str):
        return self._find_cmd(entry, cmd_text, self.login_matchers)

    async def find_selectscreen_cmd(self, entry: "QueueEntry", cmd_text: str):
        return self._find_cmd(entry, cmd_text, self.select_matchers)

    async def gather_login_help(self, entry: "QueueEntry", data):
        await self._gather_help(entry, data, self.login_matchers)

    async def gather_selectscreen_help(self, entry: "QueueEntry", data):
        await self._gather_help(entry, data, self.select_matchers)


class PromptHandler:
    def __init__(self, owner: "GameSession"):
        self.owner = owner
        self.last_activity = 0.0
        self.last_prompt = 0.0
        self.delta = 0.0

    def update(self, now: float, delta: float):
        diff = self.last_activity - self.last_prompt
        if diff:
            diff2 = now - self.last_activity
            if diff2 > self.owner.game.app.config.game_options["prompt_delay"]:
                self.send_prompt()
                self.last_prompt = now

    def send_prompt(self):
        pass


class GameSession:
    session_matchers = ("ic",)

    def __init__(self, user: "GameObject", character: "GameObject"):
        self.user: "GameObject" = user
        weakchar = weakref.proxy(character)
        self.character: "GameObject" = weakchar
        self.puppet: "GameObject" = weakchar
        self.connections: Set["Connection"] = weakref.WeakSet()
        self.in_events: List[ConnectionInMessage] = list()
        self.out_events: List[ConnectionOutMessage] = list()
        self.admin = False
        self.ending_safely = False
        self.linkdead = False
        self.character.session = self
        self.user.account_sessions.add(self)
        now = time.time()
        self.last_cmd = now
        self.created = now

    @lazy_property
    def prompt(self):
        return self.game.app.classes["game"]["prompthandler"](self)

    @property
    def game(self):
        return self.user.game

    def get_alevel(self, ignore_fake=False):
        if not self.admin and not ignore_fake:
            return min(self.user.alevel, self.character.alevel)
        return self.user.alevel

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

    async def on_first_connection(self, entry: "QueueEntry", connection: "Connection"):
        await self.puppet.announce_login(entry, from_linkdead=self.linkdead)
        self.linkdead = False

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

    def update(self, now: float, delta: float):
        self.prompt.update(now, delta)

    async def on_connection_leave(self, entry: "QueueEntry", connection: Connection):
        pass

    async def on_final_connection_leave(self, entry: "QueueEntry", connection: Connection):
        if self.ending_safely:
            await self.cleanup(entry)
        else:
            self.linkdead = True
            await self.puppet.announce_linkdead(entry)

    async def cleanup(self, entry: "QueueEntry"):
        self.puppet.session = None
        if self.character.session:
            self.character.session = None
        self.user.account_sessions.remove(self)
        await self.puppet.announce_logout(entry, from_linkdead=self.linkdead)

    def can_end_safely(self):
        return True, None

    async def end_safely(self, entry: "QueueEntry"):
        self.ending_safely = True
        conns = list(self.connections)
        for conn in conns:
            await conn.leave_session(entry)
            await conn.show_select_screen(entry)
        self.user.game.sessions.pop(self.character.dbid, None)

    def see_tracebacks(self):
        return self.get_alevel(ignore_fake=True) >= 10
