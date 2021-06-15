import time
import weakref
import asyncio
import sys
import traceback

from collections import OrderedDict, namedtuple
from typing import Optional, Set, List, Tuple

from mudrich.console import Console
from mudrich.color import ColorSystem
from mudrich.console import _null_highlighter
from mudrich.traceback import Traceback
from mudrich import box
from mudrich.text import Text

from athanor.shared import (
    ConnectionDetails,
    ConnectionInMessage,
    ConnectionInMessageType,
)
from athanor.shared import ConnectionOutMessage, ConnectionOutMessageType, ColorSystem
from athanor.tasks import TaskMaster
from athanor_server.conn import Connection as BaseConnection
from athanor.utils import lazy_property

from .welcome import message as WELCOME
from .utils import formatter as fmt
from .selectscreen import render_select_screen
from .utils.styling import StyleHandler
from .engine.commands.base import CommandException


COLOR_MAP = {
    ColorSystem.STANDARD: "standard",
    ColorSystem.EIGHT_BIT: "256",
    ColorSystem.TRUECOLOR: "truecolor",
    ColorSystem.WINDOWS: "windows",
}

GameMsg = namedtuple("GameMsg", ['cmd', 'args', 'kwargs'])
SessionMsg = namedtuple("SessionMsg", ["connection", "msg"])


class Connection(BaseConnection):
    login_matchers = ("login",)
    select_matchers = ("ooc",)

    def __init__(self, service: "ConnectionService", details: ConnectionDetails):
        BaseConnection.__init__(self, service, details)
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
        self._print_mode = 'line'

    @property
    def executor(self):
        return self

    @property
    def enactor(self):
        return self

    @property
    def caller(self):
        return self

    @property
    def style(self):
        if self.user:
            return self.user.style
        return self.conn_style

    @property
    def game(self):
        return self.service.app.game

    def write(self, b: str):
        self.out_gamedata.append((self._print_mode, (b,), dict()))

    def flush(self):
        """
        Do not remove this method. It's needed to trick Console into treating this object
        as a file.
        """

    async def on_update(self, details: ConnectionDetails):
        self.details = details
        self.console._color_system = (
            ColorSystem(int(details.color)) if details.color else None
        )
        self.console.mxp = details.mxp_active
        self.console._width = details.width

    async def on_process_event(self, ev: ConnectionInMessage):
        if ev.msg_type == ConnectionInMessageType.GAMEDATA:
            for cmd, args, kwargs in ev.data:
                msg = GameMsg(cmd, args, kwargs)
                await self._queue.put((0, msg))
            self.last_activity = time.time()

    async def run_task(self, task: GameMsg):
        if self.session:
            await self.session.on_connection_event(self, task)
        else:
            await self.handle_msg(task)

    async def handle_msg(self, task: GameMsg):
        if task.cmd.lower() in ('line', 'text'):
            cmd_text = Text(task.args[0].strip())
            if cmd_text.plain.upper() == 'IDLE':
                return
            if self.user:
                cmd = await self.find_selectscreen_cmd(cmd_text)
            else:
                cmd = await self.find_login_cmd(cmd_text)
            if cmd:
                try:
                    await cmd.at_pre_execute()
                    await cmd.execute()
                    await cmd.at_post_execute()
                except CommandException as err:
                    self.msg(text=str(err))
                except Exception as err:
                    print(f"OI! {err}")
                    traceback.print_exc(file=sys.stdout)
            else:
                self.msg(text="Huh? (Type 'help' for help.)")

    def print(self, *args, **kwargs):
        self._print_mode = 'line'
        self.console.print(*args, highlight=False, **kwargs)

    def print_prompt(self, *args, **kwargs):
        self._print_mode = 'prompt'
        self.console.print(*args, highlight=False, **kwargs)

    def print_text(self, *args, **kwargs):
        self._print_mode = 'text'
        self.console.print(*args, highlight=False, **kwargs)

    def print_exception(self, trace):
        tb = Traceback(trace=trace, width=self.console.width, box=box.MINIMAL)
        self.console.print(tb)

    def print_python(self, *args, **kwargs):
        self.console.highlighter = self._repr_highlighter
        self.console.print(*args, **kwargs)
        self.console.highlighter = _null_highlighter

    async def on_client_connect(self):
        await self.show_welcome_screen()

    async def show_welcome_screen(self):
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

    async def create_user(self, entry: "TaskEntry", name: str, password: str) -> Tuple[bool, Optional[Text]]:
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

    async def check_login(self, name: str, password: str) -> Tuple[bool, Optional[Text]]:
        candidates = self.game.type_index["USER"]
        user, error = self.game.search_objects(name, candidates=candidates, exact=True)
        if error:
            return False, Text("Sorry, that was an incorrect username or password.")
        if not user:
            return False, Text("Sorry, that was an incorrect username or password.")
        if not await user.check_password(password):
            return False, Text("Sorry, that was an incorrect username or password.")
        await self.login(user)
        return True, None

    async def login(self, user: "GameObject"):
        self.user = user
        user.last_login = time.time()
        user.connections.add(self)
        await self.show_select_screen()
        if len(user.connections) == 1:
            await user.on_first_connection_login(self)
        await user.on_connection_login(self)

    async def show_select_screen(self):
        self.receive_msg(render_select_screen(self))

    async def terminate(self, entry: "TaskEntry"):
        if self.session:
            await self.leave_session(entry)
        if self.user:
            await self.logout(entry)
        self.disconnect = True

    async def logout(self, entry: "TaskEntry"):
        user = self.user
        if user:
            self.user = None
            user.connections.remove(self)
            await user.on_connection_logout(self)
            if not user.connections:
                await user.on_final_connection_logout(self)

    async def leave_session(self):
        if not self.session:
            return
        session = self.session
        session.connections.remove(self)
        await session.on_connection_leave(self)
        if not session.connections:
            await session.on_final_connection_leave(self)
        self.session = None

    async def join_session(self, session: "GameSession"):
        session.connections.add(self)
        self.session = session
        if len(session.connections) == 1:
            await session.on_first_connection(self)
        await self.on_join_session(session)

    async def on_join_session(self, session: "GameSession"):
        pass

    async def _find_cmd(self, cmd_text: str, matcher_categories):
        for matcher_name in matcher_categories:
            matchers = self.game.command_matchers.get(matcher_name, list())
            for matcher in matchers:
                if matcher and await matcher.access(self):
                    cmd = await matcher.match(self, cmd_text)
                    if cmd:
                        return cmd

    async def _gather_help(self, data, matcher_categories):
        for matcher_name in matcher_categories:
            matchers = self.game.command_matchers.get(matcher_name, list())
            for matcher in matchers:
                if matcher and await matcher.access(self):
                    await matcher.populate_help(self, data)

    async def find_login_cmd(self, cmd_text: Text):
        return await self._find_cmd(cmd_text, self.login_matchers)

    async def find_selectscreen_cmd(self, cmd_text: Text):
        return await self._find_cmd(cmd_text, self.select_matchers)

    async def get_help(self, data):
        out = dict()
        if self.user:
            await self._gather_help(data, self.select_matchers)
        else:
            await self._gather_help(data, self.login_matchers)
        return out

    def get_alevel(self, ignore_fake=False):
        if self.user:
            return self.user.get_alevel(ignore_fake=ignore_fake)
        else:
            return -1


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


class GameSession(TaskMaster):
    session_matchers = ("ic",)

    def __init__(self, user: "GameObject", character: "GameObject"):
        super().__init__()
        self.user: "GameObject" = user
        weakchar = weakref.proxy(character)
        self.character: "GameObject" = weakchar
        self.puppet: "GameObject" = weakchar
        self.connections: Set["Connection"] = weakref.WeakSet()
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

    async def on_first_connection(self, connection: "Connection"):
        await self.puppet.announce_login(from_linkdead=self.linkdead)
        self.linkdead = False

    def _find_cmd(self, entry: "TaskEntry", cmd_text: str, matcher_categories):
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

    def find_cmd(self, entry: "TaskEntry", cmd_text: str):
        cmd = self._find_cmd(entry, cmd_text, self.session_matchers)
        if cmd:
            return cmd
        return self.puppet.find_cmd(entry, cmd_text)

    def gather_help(self, entry: "TaskEntry", data):
        self._gather_help(entry, data, self.session_matchers)
        self.puppet.gather_help(entry, data)

    def update(self, now: float, delta: float):
        self.prompt.update(now, delta)

    async def on_connection_leave(self, connection: Connection):
        pass

    async def on_final_connection_leave(self, connection: Connection):
        if self.ending_safely:
            await self.cleanup()
        else:
            self.linkdead = True
            await self.puppet.announce_linkdead()

    async def cleanup(self):
        self.puppet.session = None
        if self.character.session:
            self.character.session = None
        self.user.account_sessions.remove(self)
        await self.puppet.announce_logout(from_linkdead=self.linkdead)

    def can_end_safely(self):
        return True, None

    async def end_safely(self):
        self.ending_safely = True
        # have to create a separate list so that we don't remove connections from the list while iterating.
        for conn in list(self.connections):
            await conn.leave_session()
            await conn.show_select_screen()
        self.user.game.sessions.pop(self.character.dbid, None)

    async def see_tracebacks(self, entry: "TaskEntry"):
        return self.get_alevel(ignore_fake=True) >= 10

    async def run_task(self, task: SessionMsg):
        await self.puppet.handle_msg(task, priority=100)

    async def on_connection_event(self, connection: "Connection", event: GameMsg):
        await self._queue.put((1000, SessionMsg(connection, event)))
