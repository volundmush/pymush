import re
import sys
import time
import traceback
from athanor.utils import partial_match
from . base import Command, MushCommand, CommandException, PythonCommandMatcher

class PyCommand(Command):
    name = '@py'
    re_match = re.compile(r"^(?P<cmd>@py)(?: +(?P<args>.+)?)?", flags=re.IGNORECASE)
    help_category = 'System'

    def available_vars(self):
        return {
            'parser': self.parser,
            'enactor': self.enactor,
            'connection': self.enactor,
            "game": self.service,
            "app": self.service.app
        }

    @classmethod
    def access(cls, enactor):
        return enactor.get_slevel() >= 10

    def flush(self):
        pass

    def write(self, text):
        self.caller.msg(text=text.rsplit("\n", 1)[0])


    def execute(self):
        mdict = self.match_obj.groupdict()
        args = mdict.get("args", None)
        if not args:
            raise CommandException("@py requires arguments!")

        self.msg(text=f">>> {args}")

        try:
            # reroute standard output to game client console
            old_stdout = sys.stdout
            old_stderr = sys.stderr

            sys.stdout = self
            sys.stderr = self

            mode = "eval"
            try:
                pycode_compiled = compile(args, "", mode)
            except Exception:
                mode = "exec"
                pycode_compiled = compile(args, "", mode)

            measure_time = True
            duration = ""
            if measure_time:
                t0 = time.time()
                ret = eval(pycode_compiled, {}, self.available_vars())
                t1 = time.time()
                duration = " (runtime ~ %.4f ms)" % ((t1 - t0) * 1000)
                self.enactor.msg(text=duration)
            else:
                ret = eval(pycode_compiled, {}, self.available_vars())

        except Exception:
            errlist = traceback.format_exc().split("\n")
            if len(errlist) > 4:
                errlist = errlist[4:]
            ret = "\n".join("%s" % line for line in errlist if line)
        finally:
            # return to old stdout
            sys.stdout = old_stdout
            sys.stderr = old_stderr

        if ret is None:

            return
        elif isinstance(ret, tuple):

            # we must convert here to allow msg to pass it (a tuple is confused
            # with a outputfunc structure)
            ret = str(ret)

        self.enactor.msg(text=repr(ret))
