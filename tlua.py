#!/usr/bin/env python
import lupa
import time
from lupa import LuaRuntime


class CpuTimeExceeded(Exception):
    pass


START_TIME = time.time()


LOOP_CODE = """
function(a)
    i = 0
    while true do
      print(a, ": ", i)
      i = i+1
    end
end
"""

SANITY_CODE = """
function()
   py_cpu_check()
end
"""


class LuaGlobals:
    api = ('py_cpu_check', 'cpu_check')
    write_protected = ('py_cpu_check', 'cpu_check')

    def __init__(self, runtime):
        self.runtime = runtime
        self._globals = runtime.globals()
        self._g = self._globals._G
        #self._globals._G = self

        #self._globals.cpu_check = runtime.eval(SANITY_CODE)

        #self.debug.sethook(self.cpu_check, "l", 50)

    def __getitem__(self, item):
        print(f"IS GET BEING CALLED?: {item}")
        if item in self.api:
            return getattr(self, item, None)
        return getattr(self._g, item, None)

    def __setitem__(self, key, value):
        print(f"IS SET BEING CALLED? {key} = {value}")
        if key in self.write_protected or key in self.api:
            return
        setattr(self._g, key, value)

    def py_cpu_check(self):
        delta = time.time() - START_TIME
        print(f"DELTA IS: {delta}")
        if delta > 3:
            raise CpuTimeExceeded("WHOOPS! CPU used 3 seconds")


def runtest():
    global START_TIME
    lua = LuaRuntime(unpack_returned_tuples=True)
    globals = LuaGlobals(lua)
    lua_check = lua.eval("_G._G._G")
    print(lua_check)
    for t in lua_check:
        print(t)
    lua_func = lua.eval(LOOP_CODE)
    START_TIME = time.time()
    try:
        pass
        #lua_func("BOO")
    except CpuTimeExceeded as err:
        print(f"{str(err)}")


if __name__ == '__main__':
    runtest()