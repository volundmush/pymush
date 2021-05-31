import re
import sys
import time
import traceback
from athanor.utils import partial_match
from . base import Command, MushCommand, CommandException, PythonCommandMatcher
from mudstring.encodings.pennmush import send_menu, ansi_fun
from pymush.utils import formatter as fmt


class PyCommand(Command):
    name = '@py'
    re_match = re.compile(r"^(?P<cmd>@py)(?: +(?P<args>.+)?)?", flags=re.IGNORECASE)
    help_category = 'System'

    def available_vars(self):
        return {
            'entry': self.entry,
            'parser': self.parser,
            'enactor': self.entry.enactor,
            'connection': self.entry.connection,
            "game": self.game,
            "app": self.game.app
        }

    @classmethod
    def access(cls, enactor):
        return enactor.get_slevel() >= 10

    def flush(self):
        pass

    def write(self, text):
        self.msg(text=text.rsplit("\n", 1)[0])

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

            if measure_time:
                t0 = time.time()
                ret = eval(pycode_compiled, {}, self.available_vars())
                t1 = time.time()
                duration = " (runtime ~ %.4f ms)" % ((t1 - t0) * 1000)
                self.msg(text=duration)
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

        self.msg(text=repr(ret))


class HelpCommand(Command):
    """
    This is the help command.
    """
    name = "help"
    re_match = re.compile(r"^(?P<cmd>help)(?: +(?P<args>.+)?)?", flags=re.IGNORECASE)

    def execute(self):
        categories = self.interpreter.get_help()

        gdict = self.match_obj.groupdict()
        args = gdict.get('args', None)

        if not args:
            self.display_help(categories)
        else:
            self.display_help_file(categories, args)

    def display_help(self, data):
        cat_sort = sorted(data.keys())
        out = fmt.FormatList(self.entry.enactor)
        out.add(fmt.Header("Help: Available Commands"))
        for cat_key in cat_sort:
            cat = data[cat_key]
            out.add(fmt.Subheader(cat_key))
            cmds = sorted([cmd for cmd in cat], key=lambda x: x.name)
            out.add(fmt.TabularTable([send_menu(cmd.name, commands=[(f'help {cmd.name}', f"help {cmd.name}")]) for cmd in cmds]))
        out.add(fmt.Footer("help <command> for further help"))
        self.entry.enactor.send(out)

    def display_help_file(self, data, name):
        total = set()
        for k, v in data.items():
            total.update(v)

        if not (found := partial_match(name, total, key=lambda x: x.name)):
            raise CommandException(f"No help for: {name}")
        found.help(self.entry)
