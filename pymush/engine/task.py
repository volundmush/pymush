import sys
import time
import traceback

from typing import Optional, Set, Tuple

from mudrich.text import Text
from mudrich.traceback import Traceback

from pymush.conn import GameMsg, SessionMsg
from pymush.db.objects.base import GameObject
from pymush.utils.text import find_notspace
from .commands.base import CommandException
from .parser import Parser
from pymush.utils import formatter as fmt

STD_OUT = sys.stdout


class TaskException(Exception):
    pass


class BreakQueueException(TaskException):
    pass


class CPUTimeExceeded(TaskException):
    pass


class BaseExecutableTask:

    async def execute(self, entry: "TaskEntry"):
        pass


class ActionListTask:
    """
    Suspended execution of a normal action list, possibly with some modifying kwargs.
    This is used by commands like @wait.
    """

    def __init__(self, actions: Text, **kwargs):
        self.actions = actions
        self.kwargs = kwargs

    async def execute(self, entry: "TaskEntry"):
        await entry.execute_action_list(self.actions, split_actions=True, **self.kwargs)


class TaskEntry:
    def __init__(self, holder: "GameObject", task, script: bool = True,
                 enactor: Optional["GameObject"] = None, caller: Optional["GameObject"] = None):
        self.pid = None
        self.holder = holder
        self.connection = None
        self.task = task
        self.start_timer: Optional[float] = None
        self.current_cmd = None
        self.wait: Optional[float] = None
        self.created: Optional[float] = time.time()
        self.function_invocation_count = 0
        self.recursion_count = 0
        self.parser = Parser(self, executor=holder, enactor=enactor or holder, caller=caller or holder)
        self.inline_depth = -1
        self.script = script

    @property
    def max_cpu_time(self):
        return self.game.options.get('max_cpu_time', 4.0)

    @property
    def function_recursion_limit(self):
        return self.game.options.get('function_recursion_limit', 3000)

    @property
    def function_invocation_limit(self):
        return self.game.options.get('function_invocation_limit', 10000)

    @property
    def game(self):
        return self.holder.game

    @property
    def owner(self):
        return self.holder.root_owner

    @property
    def session(self):
        return self.holder.session

    def get_alevel(self, ignore_fake=False):
        if self.script:
            return self.holder.get_alevel(ignore_fake=ignore_fake)
        elif self.session:
            return self.session.get_alevel(ignore_fake=ignore_fake)
        else:
            return self.holder.get_alevel(ignore_fake=ignore_fake)

    async def get_help(self):
        out = dict()
        await self.holder.gather_help(self, out)
        return out

    async def find_cmd(self, action: Text):
        return await self.holder.find_cmd(self, action)

    def action_splitter(self, actions: Text):
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
                if c == "\\":
                    escaped = True
                elif c == ";" and not (paren_depth or curly_depth or square_depth):
                    yield actions[start_segment:i].squish_spaces()
                    start_segment = i + 1
                elif c == "(":
                    paren_depth += 1
                elif c == ")" and paren_depth:
                    paren_depth -= 1
                elif c == "{":
                    curly_depth += 1
                elif c == "}" and curly_depth:
                    curly_depth -= 1
                elif c == "[":
                    square_depth += 1
                elif c == "]" and square_depth:
                    square_depth -= 1
            i += 1

        if i > start_segment:
            yield actions[start_segment:i].squish_spaces()

    valid_prefixes = {'}', ']', '|'}

    def parse_prefixes(self, prefixes: Set[str]) -> dict:
        out = dict()
        if '}' in prefixes:
            out['debug'] = True
        if ']' in prefixes:
            out['noeval'] = True
        if '|' in prefixes:
            out['nomenu'] = True
        return out

    def separate_prefixes(self, action: Text) -> Tuple[Text, dict]:
        prefixes = set()
        while action and action.plain[0] in self.valid_prefixes:
            prefixes.add(action.plain[0])
            action = action[1:].squish_spaces()
        return action, self.parse_prefixes(prefixes)

    async def execute_action_list(self, actions: Text, split_actions: bool = False, nobreak: bool = False, **kwargs):
        try:
            await self.inline(actions, split_actions=split_actions, nobreak=nobreak, **kwargs)
        except BreakQueueException as brk:
            pass
        except CPUTimeExceeded as cpu:
            pass

    async def inline(self, actions: Text, split_actions: bool = False, nobreak: bool = False, **kwargs):
        actions = actions.squish_spaces()
        if split_actions:
            while actions.startswith("{") and actions.endswith("}"):
                actions = actions[1:-1].squish_spaces()
            action_list = self.action_splitter(actions)
        else:
            action_list = [actions]

        self.parser.enter_frame(**kwargs)
        self.inline_depth += 1

        for action in action_list:
            debug_set = set()
            if await self.holder.controls(self, self.executor) and await self.holder.see_debug(self):
                debug_set.add(self.holder)
            if await self.executor.see_debug(self):
                debug_set.add(self.executor)
            for obj in debug_set:
                await obj.print_debug_cmd(self, action)
            action, options = self.separate_prefixes(action)
            cmd = await self.find_cmd(action)
            if cmd:
                try:
                    cmd.noeval = options.get('noeval', False)
                    await cmd.at_pre_execute()
                    await cmd.execute()
                    await cmd.at_post_execute()
                    after_time = time.time()
                    if cmd.timestamp_after and self.session:
                        self.session.last_cmd = after_time
                    total_time = after_time - self.start_timer
                    if total_time >= self.max_cpu_time:
                        raise CPUTimeExceeded(total_time)
                    if self.parser.frame.break_after:
                        raise BreakQueueException()
                except CommandException as cex:
                    self.executor.msg(text=str(cex))
                except BreakQueueException as br:
                    if not nobreak:
                        raise br
                    else:
                        break
            else:
                self.executor.msg(text='Huh?  (Type "help" for help.)')

        self.parser.exit_frame()
        self.inline_depth -= 1

    async def do_execute(self):
        if isinstance(self.task, (GameMsg, SessionMsg)):
            if isinstance(self.task, SessionMsg):
                self.connection = self.task.connection
                msg = self.task.msg
            else:
                msg = self.task
            if msg.cmd.lower() in ('line', 'text'):
                actions = msg.args[0] if isinstance(msg.args[0], Text) else Text(msg.args[0])
                await self.execute_action_list(actions)
            else:
                pass  # This'll handle OOB data.
        elif isinstance(self.task, BaseExecutableTask):
            await self.task.execute(self)

    async def execute(self):
        self.start_timer = time.time()
        try:
            await self.do_execute()
        except Exception as e:
            if self.session and await self.session.see_tracebacks(self):
                exc_type, exc_value, tb = sys.exc_info()
                trace = Traceback.extract(exc_type, exc_value, tb, show_locals=False)
                out = fmt.FormatList(self.session)
                out.add(fmt.PyException(trace))
                self.session.send(out)
            traceback.print_exc(file=sys.stdout)

    @property
    def frame(self):
        return self.parser.frame

    @property
    def enactor(self):
        return self.parser.enactor

    @property
    def executor(self):
        return self.parser.executor

    @property
    def caller(self):
        return self.parser.caller
