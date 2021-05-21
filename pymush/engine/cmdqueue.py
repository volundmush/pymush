import sys
import time
from collections import OrderedDict
from .commands.base import CommandException
import traceback
from typing import Optional, Set
from enum import IntEnum
from athanor_server.conn import Connection
from pymush.db.objects.base import GameObject
import asyncio
import weakref
from .parser import Parser


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
        self.session: Optional["GameSession"] = None
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
        self.created: Optional[float] = time.time()

    @property
    def game(self):
        return self.queue.service

    def get_alevel(self, ignore_quell=False):
        if self.type == QueueEntryType.SCRIPT:
            return self.executor.admin_level
        elif self.session:
            return self.session.get_alevel(ignore_quell=ignore_quell)
        else:
            return self.executor.admin_level

    @classmethod
    def from_login(cls, conn: Connection, command: str) -> "QueueEntry":
        entry = cls(QueueEntryType.LOGIN)
        entry.enactor = weakref.proxy(conn)
        entry.executor = entry.enactor
        entry.caller = entry.enactor
        entry.connection = entry.enactor
        entry.actions = command
        return entry

    @classmethod
    def from_selectscreen(cls, user: GameObject, command: str, connection: Optional[Connection] = None) -> "QueueEntry":
        entry = cls(QueueEntryType.SELECTSCREEN)
        if connection:
            entry.connection = weakref.proxy(connection)
        entry.user = weakref.proxy(user)
        entry.enactor = entry.connection
        entry.executor = entry.connection
        entry.caller = entry.connection
        entry.actions = command
        entry.parser = Parser(entry, entry.enactor, entry.executor, entry.caller)
        return entry

    @classmethod
    def from_session(cls, sess: "GameSession", command: str, connection: Optional[Connection] = None) -> "QueueEntry":
        entry = cls(QueueEntryType.SESSION)
        if connection:
            entry.connection = weakref.proxy(connection)
        entry.session = weakref.proxy(sess)
        entry.user = sess.user
        entry.enactor = sess.puppet
        entry.executor = sess.puppet
        entry.caller = sess.puppet
        entry.parser = Parser(entry, entry.enactor, entry.executor, entry.caller)
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
        entry.parser = Parser(entry, entry.enactor, entry.executor, entry.caller)
        entry.split_actions = True
        return entry

    def action_splitter(self, remaining: str):
        while len(remaining):
            result, remaining, stopped = self.parser.evaluate(remaining, noeval=True, stop_at=[';'])
            if result:
                yield result

    def execute(self):
        try:
            self.start_timer = time.time()
            if self.type == QueueEntryType.SCRIPT:
                self.execute_script_actions()
            else:
                cmd = None
                if self.type == QueueEntryType.LOGIN:
                    cmd = self.connection.find_login_cmd(self, self.actions)
                elif self.type == QueueEntryType.SELECTSCREEN:
                    cmd = self.connection.find_selectscreen_cmd(self, self.actions)
                elif self.type == QueueEntryType.SESSION:
                    cmd = self.session.find_cmd(self, self.actions)
                if cmd:
                    self.execute_cmd(cmd)
                else:
                    self.enactor.msg(text='Huh?  (Type "help" for help.)')
        except Exception as e:
            print(f"Something foofy happened: {e}")
            traceback.print_exc(file=sys.stdout)

    def execute_cmd(self, cmd):
        cmd.service = self.queue.service
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