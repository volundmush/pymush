import re
import sys
import time
import traceback

from mudrich.encodings.pennmush import send_menu, ansi_fun

from athanor.utils import partial_match

from pymush.utils import formatter as fmt
from mudrich.traceback import Traceback

from .base import Command, MushCommand, CommandException, PythonCommandMatcher


class PyCommand(Command):
    name = "@py"
    re_match = re.compile(r"^(?P<cmd>@py)(?: +(?P<args>.+)?)?", flags=re.IGNORECASE)
    help_category = "System"

    def available_vars(self):
        return {}

    @classmethod
    async def access(cls, entry):
        return entry.get_alevel() >= 10

    def flush(self):
        pass

    def write(self, text):
        out = fmt.FormatList(self.executor)
        out.add(fmt.PyDebug(text.rsplit("\n", 1)[0]))
        self.executor.send(out)

    async def execute(self):
        mdict = self.match_obj.groupdict()
        args = mdict.get("args", None)
        if not args:
            raise CommandException("@py requires arguments!")
        out = fmt.FormatList(self.executor)
        out.add(fmt.Line(f">>> {args}"))
        duration = ""
        ret = None

        try:
            # reroute standard output to game client console
            old_stdout = sys.stdout
            old_stderr = sys.stderr

            sys.stdout = self
            sys.stderr = self

            try:
                pycode_compiled = compile(args, "", "eval")
            except Exception:
                pycode_compiled = compile(args, "", "exec")

            measure_time = True

            if measure_time:
                t0 = time.time()
                ret = eval(pycode_compiled, {}, self.available_vars())
                t1 = time.time()
                duration = " (runtime ~ %.4f ms)" % ((t1 - t0) * 1000)
            else:
                ret = eval(pycode_compiled, {}, self.available_vars())
        except Exception:
            exc_type, exc_value, tb = sys.exc_info()
            trace = Traceback.extract(exc_type, exc_value, tb, show_locals=False)
            out.add(fmt.PyException(trace))
        finally:
            # return to old stdout
            sys.stdout = old_stdout
            sys.stderr = old_stderr

        out.add(fmt.PyDebug(repr(ret)))
        if duration:
            out.add(fmt.Line(duration))
        self.executor.send(out)


class HelpCommand(Command):
    """
    This is the help command.
    """

    name = "help"
    re_match = re.compile(r"^(?P<cmd>help)(?: +(?P<args>.+)?)?", flags=re.IGNORECASE)

    async def get_help(self):
        return await self.entry.get_help()

    async def execute(self):
        categories = await self.get_help()

        gdict = self.match_obj.groupdict()
        args = gdict.get("args", None)

        if not args:
            self.display_help(categories)
        else:
            self.display_help_file(categories, args)

    def display_help(self, data):
        cat_sort = sorted(data.keys())
        out = fmt.FormatList(self.entry.executor)
        out.add(fmt.Header("Help: Available Commands"))
        for cat_key in cat_sort:
            cat = data[cat_key]
            out.add(fmt.Subheader(cat_key))
            cmds = sorted([cmd for cmd in cat], key=lambda x: x.name)
            out.add(
                fmt.TabularTable(
                    [
                        send_menu(
                            cmd.name,
                            commands=[(f"help {cmd.name}", f"help {cmd.name}")],
                        )
                        for cmd in cmds
                    ]
                )
            )
        out.add(fmt.Footer("help <command> for further help"))
        self.entry.executor.send(out)

    def display_help_file(self, data, name):
        total = set()
        for k, v in data.items():
            total.update(v)

        if not (found := partial_match(name, total, key=lambda x: x.name)):
            raise CommandException(f"No help for: {name}")
        found.help(self.entry)


class QuitCommand(Command):
    """
    Disconnects this connection from the game.
    """

    name = "QUIT"
    re_match = re.compile(r"^(?P<cmd>QUIT)(?: +(?P<args>.+)?)?", flags=re.IGNORECASE)
    help_category = "System"

    async def execute(self):
        out = fmt.FormatList(self.executor)
        out.add(fmt.Line("See you again!"))
        out.reason = "quit"
        self.executor.send(out)
        self.executor.terminate()
