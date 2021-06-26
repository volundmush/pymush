import sys
import time
import traceback
import asyncio

from typing import Optional, Set, Tuple, Union

from asynclupa import AsyncLuaRuntime

from mudrich.text import Text
from mudrich.traceback import Traceback


from pymush.utils.text import find_notspace
from .commands.base import CommandException
from pymush.utils import formatter as fmt

from pymush.task import BreakTaskException, CPUTimeExceeded, BaseTask


class LuaTask(BaseTask):
    allowed_globals = ('assert', 'error', 'ipairs', 'next', 'pairs', 'pcall', 'select', 'tonumber', 'tostring', 'type',
                       'unpack', '_VERSION', 'xpcall')
    protected_globals = ('sanity_check', 'await')
    sanity_call = """function() await(sanity_check()) end"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.runtime = AsyncLuaRuntime()
        self._original_globals = {k: v for k, v in self.runtime.globals().items()}
        self._globals = dict()
        self._instructions_per_check = self.holder.instructions_per_check
        self._instruction_count = 0
        self.loader = self._original_globals['load']
        self.code = ""

    async def sanity_check(self):
        self._instruction_count += self._instructions_per_check
        if self._instruction_count > self.holder.max_lua_instructions:
            raise CPUTimeExceeded(f"Lua Instructions have exceeded holder's {self.holder.max_lua_instructions}")

    def __getitem__(self, item):
        return self._globals.get(item, None)

    def __setitem__(self, key, value):
        if key in self.protected_globals:
            return
        self._globals[key] = value

    async def sleep(self, duration: Union[int, float]):
        if not isinstance(duration, (int, float)):
            return
        await asyncio.sleep(abs(duration))

    async def setup(self):
        for key in self.allowed_globals:
            if (found := self._original_globals.get(key, None)):
                self._globals[key] = found

        self._globals['sleep'] = self.sleep
        self._globals["await"] = self._original_globals["python"]["await"]
        self._globals["print"] = self.print

        sanity = await self.runtime.eval(self.sanity_call)
        debug = self._original_globals['debug']
        debug.sethook(sanity, 'l', self._instructions_per_check)

    async def do_execute(self):
        compiled_code = self.loader(self.code, f"{self.holder.dbref}/{self.pid}", 't', self)
        self._globals['compiled'] = compiled_code
        await self.runtime.eval('compiled()')

    def print(self, *args):
        self.holder.msg(text="".join([str(arg) for arg in args]))