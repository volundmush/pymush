import sys
import time
from collections import OrderedDict
from .commands.base import CommandException
import traceback
from typing import Optional, Union, List, Set
from enum import IntEnum
from pymush_server.protocol import MudProtocolHandler
from pymush_server.db.gameobject import GameObject, GameSession


class QueueEntryType(IntEnum):
    LOGIN = 0
    USER = 1
    SESSION = 2
    SCRIPT = 3


class QueueEntry:

    def __init__(self, qtype: int):
        self.type: QueueEntryType = QueueEntryType(qtype)
        self.user: Optional[GameObject] = None
        self.enactor: Optional[GameObject] = None
        self.executor: Optional[GameObject] = None
        self.caller: Optional[GameObject] = None
        self.spoof: Optional[GameObject] = None
        self.actions: str = ""
        self.connection: Optional[MudProtocolHandler] = None
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
    def from_login(cls, conn: MudProtocolHandler, command: str) -> "QueueEntry":
        entry = cls(QueueEntryType.LOGIN)
        entry.connection = conn
        entry.actions = command
        return entry

    @classmethod
    def from_user(cls, user: GameObject, command: str, connection: Optional[MudProtocolHandler] = None) -> "QueueEntry":
        entry = cls(QueueEntryType.USER)
        if connection:
            entry.connection = connection
        entry.user = user
        entry.enactor = user
        entry.executor = user
        entry.caller = user
        entry.actions = command
        return entry

    @classmethod
    def from_session(cls, sess: GameSession, command: str, connection: Optional[MudProtocolHandler] = None) -> "QueueEntry":
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
        self.start_timer = time.clock_gettime(time.CLOCK_PROCESS_CPUTIME_ID)
        if self.type == QueueEntryType.LOGIN:
            self.execute_login_actions()
        elif self.type == QueueEntryType.USER:
            self.execute_user_actions()
        elif self.type == QueueEntryType.SESSION:
            self.execute_session_actions()
        elif self.type == QueueEntryType.SCRIPT:
            self.execute_script_actions()

    def execute_login_actions(self):
        pass

    def execute_user_actions(self):
        pass

    def execute_session_actions(self):
        pass

    def execute_script_actions(self):
        pass


class CmdQueue:
    def __init__(self, core):
        self.core = core
        self.queue_data: OrderedDict[int, QueueEntry] = OrderedDict()
        self.wait_queue: Set[QueueEntry] = set()
        self.queue: List[int] = list()
        self.pid: int = 0

    def push(self, entry: QueueEntry):
        self.pid += 1
        entry.pid = self.pid
        self.queue_data[self.pid] = entry
        entry.created = time.clock_gettime(time.CLOCK_PROCESS_CPUTIME_ID)
        if entry.wait:
            self.wait_queue.add(entry)
        else:
            self.queue.append(self.pid)

    def execute(self):
        if self.queue:
            try:
                pid = self.queue.pop(0)
                if (entry := self.queue_data.pop(pid, None)):
                    entry.execute()
            except Exception as e:
                print(f"Oops, CmdQueue encountered Exception: {str(e)}")

    def queue_elapsed(self):
        if self.wait_queue:
            elapsed = set()
            current = time.clock_gettime(time.CLOCK_PROCESS_CPUTIME_ID)
            for entry in self.wait_queue:
                if (current - entry.created) > entry.wait:
                    self.queue.insert(0, entry.pid)
                    elapsed.add(entry)
            self.wait_queue -= elapsed
