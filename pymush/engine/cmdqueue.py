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
from pymush.utils.text import find_matching, find_notspace


class QueueEntryType(IntEnum):
    LOGIN = 0
    OOC = 1
    IC = 2
    SCRIPT = 3


class QueueException(Exception):
    pass


class BreakQueueException(Exception):
    pass


class CPUTimeExceeded(Exception):
    pass


class QueueEntry:

    def __init__(self, qtype: int, actions: Union[str, MudText]):
        self.queue = None
        self.type: QueueEntryType = QueueEntryType(qtype)
        self.user: Optional[GameObject] = None
        self.session: Optional["GameSession"] = None
        self.actions: MudText = MudText(actions) if isinstance(actions, str) else actions
        self.connection: Optional[Connection] = None
        self.parsers = weakref.WeakSet()
        self.interpreters = weakref.WeakSet()
        self.pid = None
        self.start_timer: Optional[float] = None
        self.current_cmd = None
        self.split_actions = False
        self.pid: Optional[int] = None
        self.wait: Optional[float] = None
        self.created: Optional[float] = time.time()
        # Note: These counts are global for every single function call.
        self.function_invocation_count = 0
        self.recursion_count = 0
        self.start_frame = None

    @property
    def game(self):
        return self.queue.game

    def get_alevel(self, ignore_quell=False):
        if self.type == QueueEntryType.SCRIPT:
            return self.executor.admin_level
        elif self.session:
            return self.session.get_alevel(ignore_quell=ignore_quell)
        else:
            return self.executor.admin_level

    @classmethod
    def from_login(cls, conn: Connection, command: str) -> "QueueEntry":
        entry = cls(QueueEntryType.LOGIN, command)
        enactor = weakref.proxy(conn)
        f = StackFrame(enactor, enactor, enactor)
        entry.start_frame = f
        entry.connection = enactor
        return entry

    @classmethod
    def from_ooc(cls, user: GameObject, command: str, connection: Optional[Connection] = None) -> "QueueEntry":
        entry = cls(QueueEntryType.OOC, command)
        entry.user = user
        enactor = weakref.proxy(connection)
        entry.connection = enactor
        entry.start_frame = StackFrame(enactor, enactor, enactor)
        return entry

    @classmethod
    def from_ic(cls, sess: "GameSession", command: str, connection: Optional[Connection] = None) -> "QueueEntry":
        entry = cls(QueueEntryType.IC, command)
        entry.connection = weakref.proxy(connection)
        entry.session = weakref.proxy(sess)
        entry.user = sess.user
        entry.start_frame = StackFrame(sess.puppet, sess.puppet, sess.puppet)
        return entry

    @classmethod
    def from_script(cls, enactor: GameObject, command: str, executor: Optional[GameObject] = None,
                    caller: Optional[GameObject] = None) -> "QueueEntry":
        entry = cls(QueueEntryType.SCRIPT, command)
        entry.start_frame = StackFrame(enactor, executor if executor else enactor, caller if caller else enactor)
        entry.split_actions = True
        return entry

    def execute(self):
        self.start_timer = time.time()
        try:
            parser = Parser(self, self.enactor, self.executor, self.caller)
            interpreter = Interpreter(self, parser, self.actions, split=self.split_actions)
            try:
                interpreter.execute()
            except BreakQueueException as brk:
                pass
            except CPUTimeExceeded as cpu:
                pass
        except Exception as e:
            print(f"Something foofy happened: {e}")
            traceback.print_exc(file=sys.stdout)

    @property
    def enactor(self):
        return self.start_frame.enactor

    @property
    def executor(self):
        return self.start_frame.executor

    @property
    def caller(self):
        return self.start_frame.caller


class Interpreter:

    def __init__(self, entry, parser, actions: MudText, split: bool, parent=None):
        self.entry = entry
        self.parser = parser
        self.parent = parent
        self.actions = actions
        self.split_actions = split

    def make_parser(self, **kwargs):
        return self.parser.make_child(**kwargs)

    def get_help(self):
        categories = defaultdict(set)
        if self.entry.type == QueueEntryType.LOGIN:
            self.entry.connection.gather_login_help(self.entry, categories)
        elif self.entry.type == QueueEntryType.OOC:
            self.entry.connection.gather_selectscreen_help(self.entry, categories)
        elif self.entry.type == QueueEntryType.IC:
            self.entry.session.gather_help(self.entry, categories)
        return categories

    def find_cmd(self, action: Union[str, OLD_TEXT]):
        plain = action.plain if isinstance(action, OLD_TEXT) else action
        if self.entry.type == QueueEntryType.LOGIN:
            return self.entry.connection.find_login_cmd(self.entry, plain)
        elif self.entry.type == QueueEntryType.OOC:
            return self.entry.connection.find_selectscreen_cmd(self.entry, plain)
        elif self.entry.type == QueueEntryType.IC:
            return self.entry.session.find_cmd(self.entry, plain)
        elif self.entry.type == QueueEntryType.SCRIPT:
            return self.entry.enactor.find_cmd(self.entry, plain)

    def action_splitter(self, actions: MudText):
        plain = actions.plain

        i = find_notspace(plain, 0)
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
                    yield actions[start_segment:i].squish_spaces()
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
            yield actions[start_segment:i].squish_spaces()

    def spawn_action_list(self, frame, actions: MudText):
        entry = self.entry.__class__(QueueEntryType.SCRIPT)
        entry.enactor = frame.enactor
        entry.executor = frame.executor
        entry.caller = frame.caller
        entry.actions = actions
        entry.split_actions = True
        entry.start_frame = frame
        self.entry.queue.push(entry)

    def execute(self, nobreak=False, localize=False, number_args=None, dnum=None, dvar=None):
        actions = self.actions
        actions = actions.squish_spaces()
        if self.split_actions:
            while actions.startswith('{') and actions.endswith('}'):
                actions = actions[1:-1].squish_spaces()
            action_list = self.action_splitter(actions)
        else:
            action_list = [actions]

        self.parser.enter_frame(localize=localize, number_args=number_args, dnum=dnum, dvar=dvar)

        for action in action_list:
            cmd = self.find_cmd(action)
            if cmd:
                try:
                    cmd.game = self.entry.game
                    cmd.entry = self.entry
                    cmd.parser = self.parser
                    cmd.interpreter = self
                    cmd.at_pre_execute()
                    cmd.execute()
                    cmd.at_post_execute()
                    after_time = time.time()
                    total_time = after_time - self.entry.start_timer
                    if total_time >= self.entry.queue.max_cpu_time:
                        raise CPUTimeExceeded(total_time)
                    if self.parser.frame.break_after:
                        raise BreakQueueException()
                except CommandException as cex:
                    self.entry.enactor.msg(text=str(cex))
                except BreakQueueException as br:
                    if not nobreak:
                        raise br
            else:
                self.entry.enactor.msg(text='Huh?  (Type "help" for help.)')

        self.parser.exit_frame()


class CmdQueue:

    def __init__(self, game):
        self.game = game
        self.queue_data: OrderedDict[int, QueueEntry] = OrderedDict()
        self.wait_queue: Set[QueueEntry] = set()
        self.queue = asyncio.PriorityQueue()
        self.pid: int = 0
        self.current_entry: Optional[QueueEntry] = None
        o = game.app.config.game_options
        self.function_invocation_limit = o.get('function_invocation_limit', 10000)
        self.function_recursion_limit = o.get('function_recursion_limit', 3000)
        self.max_cpu_time = o.get('max_cpu_time', 2.0)

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
                        self.current_entry = entry
                        entry.execute()
                except Exception as e:
                    print(f"Oops, CmdQueue encountered Exception: {str(e)}")
                finally:
                    self.current_entry = None
            else:
                await asyncio.sleep(0.05)