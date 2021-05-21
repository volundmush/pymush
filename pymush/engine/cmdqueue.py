import sys
import time
from collections import OrderedDict
from .commands.base import CommandException
import traceback
from typing import Optional, Union, List, Set
from enum import IntEnum
from athanor_server.conn import Connection
from pymush.db.gameobject import GameObject, GameSession
import asyncio


class QueueEntryType(IntEnum):
    LOGIN = 0
    SELECTSCREEN = 1
    SESSION = 2
    SCRIPT = 3


class QueueEntry:

    def __init__(self, qtype: int):
        self.queue = None
        self.type: QueueEntryType = QueueEntryType(qtype)
        self.user: Optional[GameObject] = None
        self.enactor: Optional[GameObject] = None
        self.executor: Optional[GameObject] = None
        self.caller: Optional[GameObject] = None
        self.spoof: Optional[GameObject] = None
        self.actions: str = ""
        self.connection: Optional[Connection] = None
        self.parser = None
        self.semaphore_obj = None
        self.inplace = None
        self.next = None
        self.pid = None
        self.start_timer: Optional[float] = None
        self.cmd = None
        self.core = None
        self.split_actions = False
        self.pid: Optional[int] = None
        self.wait: Optional[float] = None
        self.created: Optional[float] = None

    @classmethod
    def from_login(cls, conn: Connection, command: str) -> "QueueEntry":
        entry = cls(QueueEntryType.LOGIN)
        entry.connection = conn
        entry.actions = command
        return entry

    @classmethod
    def from_selectscreen(cls, user: GameObject, command: str, connection: Optional[Connection] = None) -> "QueueEntry":
        entry = cls(QueueEntryType.SELECTSCREEN)
        if connection:
            entry.connection = connection
        entry.user = user
        entry.enactor = user
        entry.executor = user
        entry.caller = user
        entry.actions = command
        return entry

    @classmethod
    def from_session(cls, sess: GameSession, command: str, connection: Optional[Connection] = None) -> "QueueEntry":
        entry = cls(QueueEntryType.SESSION)
        if connection:
            entry.connection = connection
        entry.user = sess.user
        entry.enactor = sess.puppet
        entry.executor = sess.puppet
        entry.caller = sess.puppet
        entry.actions = command
        return entry

    @classmethod
    def from_script(cls, enactor: GameObject, command: str, executor: Optional[GameObject] = None,
                    caller: Optional[GameObject] = None, spoof: Optional[GameObject] = None) -> "QueueEntry":
        entry = cls(QueueEntryType.SESSION)
        entry.enactor = enactor
        entry.executor = executor if executor else enactor
        entry.caller = caller if caller else enactor
        entry.spoof = spoof
        entry.actions = command
        entry.split_actions = True
        return entry

    def process_action(self, enactor, text):
        try:
            cmd = enactor.find_cmd(text)
            if cmd:
                cmd.core = self.core
                self.cmd = cmd
                cmd.entry = self
                cmd.parser = self.parser
                try:
                    cmd.at_pre_execute()
                    cmd.execute()
                    cmd.at_post_execute()
                except CommandException as e:
                    cmd.msg(str(e))
                except Exception as e:
                    cmd.msg(text=f"EXCEPTION: {str(e)}")
                    traceback.print_exc(file=sys.stdout)
                self.cmd = None
            else:
                enactor.msg('Huh?  (Type "help" for help.)')
        except Exception as e:
            print(f"Something foofy happened: {e}")
            traceback.print_exc(file=sys.stdout)

    def action_splitter(self, remaining: str):
        while len(remaining):
            result, remaining, stopped = self.parser.evaluate(remaining, noeval=True, stop_at=[';'])
            if result:
                yield result

    def execute(self):
        self.start_timer = time.time()
        if self.type == QueueEntryType.LOGIN:
            self.execute_login_actions()
        elif self.type == QueueEntryType.SELECTSCREEN:
            self.execute_selectscreen_actions()
        elif self.type == QueueEntryType.SESSION:
            self.execute_session_actions()
        elif self.type == QueueEntryType.SCRIPT:
            self.execute_script_actions()

    def execute_login_actions(self):
        enactor = self.connection
        try:
            cmd = None
            for matcher in self.queue.service.command_matchers.get('login', list()):
                cmd = matcher.match(enactor, self.actions)
                if cmd:
                    break
            if cmd:
                cmd.service = self.queue.service
                self.cmd = cmd
                cmd.entry = self
                cmd.parser = self.parser
                try:
                    cmd.at_pre_execute()
                    cmd.execute()
                    cmd.at_post_execute()
                except CommandException as e:
                    cmd.msg(str(e))
                except Exception as e:
                    cmd.msg(text=f"EXCEPTION: {str(e)}")
                    traceback.print_exc(file=sys.stdout)
                self.cmd = None
            else:
                enactor.msg('Huh?  (Type "help" for help.)')
        except Exception as e:
            print(f"Something foofy happened: {e}")
            traceback.print_exc(file=sys.stdout)

    def execute_selectscreen_actions(self):
        try:
            cmd = None
            for matcher in self.queue.service.command_matchers.get('selectscreen', list()):
                cmd = matcher.match(self.enactor, self.actions)
                if cmd:
                    break
            if cmd:
                cmd.service = self.queue.service
                self.cmd = cmd
                cmd.entry = self
                cmd.parser = self.parser
                try:
                    cmd.at_pre_execute()
                    cmd.execute()
                    cmd.at_post_execute()
                except CommandException as e:
                    cmd.msg(str(e))
                except Exception as e:
                    cmd.msg(text=f"EXCEPTION: {str(e)}")
                    traceback.print_exc(file=sys.stdout)
                self.cmd = None
            else:
                self.enactor.msg('Huh?  (Type "help" for help.)')
        except Exception as e:
            print(f"Something foofy happened: {e}")
            traceback.print_exc(file=sys.stdout)

    def execute_session_actions(self):
        pass

    def execute_script_actions(self):
        pass


class CmdQueue:
    def __init__(self, service):
        self.service = service
        self.queue_data: OrderedDict[int, QueueEntry] = OrderedDict()
        self.wait_queue: Set[QueueEntry] = set()
        self.queue = asyncio.PriorityQueue()
        self.pid: int = 0

    def push(self, entry: QueueEntry, priority: int = 100):
        self.pid += 1
        entry.queue = self
        entry.pid = self.pid
        self.queue_data[self.pid] = entry
        entry.created = time.clock_gettime(time.CLOCK_PROCESS_CPUTIME_ID)
        if entry.wait:
            self.wait_queue.add(entry)
        else:
            self.queue.put_nowait((priority, self.pid))

    def queue_elapsed(self):
        if self.wait_queue:
            elapsed = set()
            current = time.time()
            for entry in self.wait_queue:
                if (current - entry.created) > entry.wait:
                    self.queue.put_nowait((50, entry.pid))
                    elapsed.add(entry)
            self.wait_queue -= elapsed

    async def run(self):
        while True:
            self.queue_elapsed()
            if self.queue_data:
                priority, pid = await self.queue.get()
                try:
                    if (entry := self.queue_data.pop(pid, None)):
                        entry.execute()
                except Exception as e:
                    print(f"Oops, CmdQueue encountered Exception: {str(e)}")
            else:
                await asyncio.sleep(0.05)