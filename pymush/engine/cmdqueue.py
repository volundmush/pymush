import sys
import time
from collections import OrderedDict, defaultdict
from .commands.base import CommandException
import traceback
from typing import Optional, Set, Union
from enum import IntEnum
from athanor_server.conn import Connection
from pymush.db.objects.base import GameObject
import asyncio
import weakref
from .parser import Parser, StackFrame
from mudstring.patches.text import OLD_TEXT, MudText


class QueueEntryType(IntEnum):
    LOGIN = 0
    OOC = 1
    IC = 2
    SCRIPT = 3


class QueueException(Exception):
    pass


class BreakQueueException(Exception):
    pass


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
        self.stop_script = False
        self.stop_guard = False
        self.include_actions = list()

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
        frame = StackFrame.from_entry(entry)
        entry.parser = Parser(entry, frame)
        return entry

    @classmethod
    def from_ooc(cls, user: GameObject, command: str, connection: Optional[Connection] = None) -> "QueueEntry":
        entry = cls(QueueEntryType.OOC)
        if connection:
            entry.connection = weakref.proxy(connection)
        entry.user = weakref.proxy(user)
        entry.enactor = entry.connection
        entry.executor = entry.connection
        entry.caller = entry.connection
        entry.actions = command
        frame = StackFrame.from_entry(entry)
        entry.parser = Parser(entry, frame)
        return entry

    @classmethod
    def from_ic(cls, sess: "GameSession", command: str, connection: Optional[Connection] = None) -> "QueueEntry":
        entry = cls(QueueEntryType.IC)
        if connection:
            entry.connection = weakref.proxy(connection)
        entry.session = weakref.proxy(sess)
        entry.user = sess.user
        entry.enactor = sess.puppet
        entry.executor = sess.puppet
        entry.caller = sess.puppet
        frame = StackFrame.from_entry(entry)
        entry.parser = Parser(entry, frame)
        entry.actions = command
        return entry

    @classmethod
    def from_script(cls, enactor: GameObject, command: str, executor: Optional[GameObject] = None,
                    caller: Optional[GameObject] = None, spoof: Optional[GameObject] = None) -> "QueueEntry":
        entry = cls(QueueEntryType.SCRIPT)
        entry.enactor = enactor
        entry.executor = executor if executor else enactor
        entry.caller = caller if caller else enactor
        entry.spoof = spoof
        entry.actions = command
        frame = StackFrame.from_entry(entry)
        entry.parser = Parser(entry, frame)
        entry.split_actions = True
        return entry

    def action_splitter(self, actions: Union[str, OLD_TEXT]):
        i = 0
        if isinstance(actions, OLD_TEXT):
            plain = actions.plain
        else:
            plain = actions

        escaped = False
        paren_depth = 0
        square_depth = 0
        start_segment = i
        curly_depth = 0

        while i < len(plain):
            if escaped:
                escaped = False
                continue
            else:
                c = plain[i]
                if c == '\\':
                    escaped = True
                elif c == ';' and not (paren_depth or curly_depth or square_depth):
                    yield self.parser.evaluate(actions[start_segment:i], no_eval=True)
                    start_segment = i+1
                elif c == '(':
                    paren_depth += 1
                elif c == ')' and paren_depth:
                    paren_depth -= 1
                elif c == '{':
                    curly_depth += 1
                elif c == '}' and curly_depth:
                    curly_depth -= 1
                elif c == '[':
                    square_depth += 1
                elif c == ']' and square_depth:
                    square_depth -= 1
            i += 1

        if i > start_segment:
            yield self.parser.evaluate(actions[start_segment:i], no_eval=True)

    def get_help(self):
        categories = defaultdict(set)
        if self.type == QueueEntryType.LOGIN:
            self.connection.gather_login_help(self, categories)
        elif self.type == QueueEntryType.OOC:
            self.connection.gather_selectscreen_help(self, categories)
        elif self.type == QueueEntryType.IC:
            self.session.gather_help(self, categories)
        return categories

    def find_cmd(self, action: Union[str, OLD_TEXT]):
        plain = action.plain if isinstance(action, OLD_TEXT) else action
        if self.type == QueueEntryType.LOGIN:
            return self.connection.find_login_cmd(self, plain)
        elif self.type == QueueEntryType.OOC:
            return self.connection.find_selectscreen_cmd(self, plain)
        elif self.type == QueueEntryType.IC:
            return self.session.find_cmd(self, plain)
        elif self.type == QueueEntryType.SCRIPT:
            return self.enactor.find_cmd(self, plain)

    def execute(self):
        print(f"EXECUTING QUEUE ENTRY: {self.__dict__}")
        try:
            self.start_timer = time.time()
            self.execute_action_list(self.actions, split=self.split_actions)
        except BreakQueueException as br:
            pass
        except Exception as e:
            print(f"Something foofy happened: {e}")
            traceback.print_exc(file=sys.stdout)

    def spawn_action_list(self, actions: Union[str, OLD_TEXT], enactor: Optional["GameObject"] = None,
                          executor: Optional["GameObject"] = None, caller: Optional["GameObject"] = None,
                          spoof: Optional["GameObject"] = None, number_args=None, dnum=None, dvar=None):
        frame = self.parser.frame.make_child(inherit=False)
        if enactor:
            frame.enactor = weakref.proxy(enactor)
        if executor:
            frame.executor = weakref.proxy(executor)
        if caller:
            frame.caller = weakref.proxy(caller)
        if spoof:
            frame.spoof = weakref.proxy(spoof)
        if number_args:
            frame.number_args = number_args
        if dnum is not None:
            frame.dnum.insert(0, dnum)
            frame.dvars.insert(0, dvar)

        entry = self.__class__(QueueEntryType.SCRIPT)

        entry.enactor = frame.enactor
        entry.executor = frame.executor
        entry.caller = frame.caller
        entry.spoof = frame.spoof
        entry.actions = actions

        entry.parser = Parser(entry, frame)
        entry.split_actions = True
        self.queue.push(entry)

    def execute_action_list(self, actions: Union[str, OLD_TEXT], number_args=None, nobreak=False, split=True,
                            localize=False, dnum=None, dvar=None):
        plain = actions.plain if isinstance(actions, OLD_TEXT) else actions
        plain = plain.strip()
        if plain.startswith('{') and plain.endswith('}'):
            plain = plain[1:-1]
        if split:
            action_list = self.action_splitter(plain)
        else:
            action_list = [plain]

        self.parser.enter_frame(localize=localize, number_args=number_args, dnum=dnum, dvar=dvar)

        for action in action_list:
            cmd = self.find_cmd(action)
            if cmd:
                try:
                    cmd.game = self.queue.service
                    cmd.entry = self
                    cmd.parser = self.parser
                    cmd.at_pre_execute()
                    cmd.execute()
                    cmd.at_post_execute()
                except CommandException as cex:
                    self.enactor.msg(text=str(cex))
                except BreakQueueException as br:
                    if not nobreak:
                        raise br
            else:
                self.enactor.msg(text='Huh?  (Type "help" for help.)')

        self.parser.exit_frame()


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