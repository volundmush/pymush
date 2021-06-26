import sys
import time
import traceback
import asyncio

from typing import Optional, Set, Tuple, Union

from mudrich.traceback import Traceback

from pymush.utils import formatter as fmt

STD_OUT = sys.stdout


class TaskException(Exception):
    pass


class BreakTaskException(TaskException):
    """This is raised if the Task wants to abort for any reason."""


class CPUTimeExceeded(TaskException):
    """Raised by task execution system monitoring if task has exceeded allotted CPU time."""


class BaseTask:
    def __init__(
        self,
        holder: "GameObject",
        enactor: Optional["GameObject"] = None,
        caller: Optional["GameObject"] = None,
    ):
        self.pid = None
        self.holder = holder
        self.start_timer: Optional[float] = 0.0
        self.created: Optional[float] = time.time()
        self._task = None
        self._running = False
        self._original_enactor = enactor or holder
        self._original_caller = caller or holder
        self._original_executor = holder

    def start(self):
        if not self._running:
            self._running = True
            self._task = asyncio.create_task(self.execute())

    async def setup(self):
        pass

    async def execute(self):
        await self.setup()
        self.start_timer = time.time()
        try:
            await self.do_execute()
        except CPUTimeExceeded as mxp:
            pass
        except BreakTaskException as brk:
            pass
        except Exception as e:
            if self.session and await self.session.see_tracebacks(self):
                exc_type, exc_value, tb = sys.exc_info()
                trace = Traceback.extract(exc_type, exc_value, tb, show_locals=False)
                out = fmt.FormatList(self.session)
                out.add(fmt.PyException(trace))
                self.session.send(out)
            traceback.print_exc(file=sys.stdout)

    async def do_execute(self):
        pass

    def stop(self):
        if self._running:
            self._running = False
            if self._task:
                self._task.cancel()

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
        return self.holder.get_alevel(ignore_fake=ignore_fake)
