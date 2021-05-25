import re
from pymush.utils import formatter as fmt


class CommandException(Exception):
    pass


class Command:
    name = None  # Name must be set to a string!
    aliases = []
    help_category = None

    @classmethod
    def access(cls, entry: "QueueEntry"):
        """
        This returns true if <enactor> is able to see and use this command.

        Use this for admin permissions locks as well as conditional access, such as
        'is the enactor currently in a certain kind of location'.
        """
        return True

    @classmethod
    def help(cls, entry):
        """
        This is called by the command-help system if help is called on this command.
        """
        if cls.__doc__:
            out = fmt.FormatList(entry.enactor)
            out.add(fmt.Header(f"Help: {cls.name}"))
            out.add(fmt.Line(cls.__doc__))
            out.add(fmt.Footer())
            entry.enactor.send(out)
        else:
            entry.enactor.msg(text="Help is not implemented for this command.")

    @classmethod
    def match(cls, enactor, text):
        """
        Called by the CommandGroup to determine if this command matches.
        Returns False or a Regex Match object.

        Or any kind of match, really. The parsed match will be returned and re-used by .execute()
        so use whatever you want.
        """
        if (result := cls.re_match.fullmatch(text)):
            return result

    def __init__(self, entry, match_obj):
        """
        Instantiates the command.
        """
        self.match_obj = match_obj
        self.entry = entry
        self.parser = None
        self.service = None

    def execute(self):
        """
        Do whatever the command does.
        """

    def at_pre_execute(self):
        pass

    def at_post_execute(self):
        pass

    def msg(self, text=None, **kwargs):
        self.entry.enactor.msg(text=text, **kwargs)

    def send(self, message):
        self.entry.enactor.send(message)

    def __repr__(self):
        return f"<{self.__class__.__name__}: {self.name}>"


class MushCommand(Command):

    def gather_args(self, noeval=False, split_at=',', stop_at='='):
        out = list()
        stopped = split_at
        true_stop = [split_at, stop_at]
        while stopped == split_at:
            result, self.remaining, stopped = self.parser.evaluate(self.remaining, stop_at=true_stop, noeval=noeval)
            out.append(result)
        return out

    def gather_arg(self, noeval=False, stop_at=None):
        result, self.remaining, stopped = self.parser.evaluate(self.remaining, stop_at=stop_at, noeval=noeval)
        return result

    def eqsplit_args(self):
        escaped = False

        remaining = self.args
        plain = remaining.plain
        paren_depth = 0
        curly_depth = 0
        square_depth = 0
        i = -1

        while True:
            i += 1
            if i > len(remaining) - 1:
                break
            c = plain[i]

            if escaped:
                escaped = False
                continue
            else:
                if c == '\\':
                    escaped = True
                elif c == '(':
                    paren_depth += 1
                elif c == ')' and paren_depth:
                    paren_depth -= 1
                elif c == '[':
                    square_depth += 1
                elif c == ']' and square_depth:
                    square_depth -= 1
                elif c == '{':
                    curly_depth += 1
                elif c == '}' and curly_depth:
                    curly_depth -= 1
                elif c == '=':
                    if not (paren_depth or square_depth or curly_depth):
                        self.lsargs = remaining[:i]
                        self.rsargs = remaining[i+1:]
                        break



    @classmethod
    def match(cls, entry, text):
        """
        Called by the CommandGroup to determine if this command matches.
        Returns False or a Regex Match object.

        Or any kind of match, really. The parsed match will be returned and re-used by .execute()
        so use whatever you want.
        """
        if not (matcher := getattr(cls, 're_match', None)):
            names = [cls.name]
            names.extend(getattr(cls, 'aliases', []))
            names = '|'.join(names)
            cls.re_match = re.compile(
                f"^(?P<cmd>{names})(?P<switches>(/(\w+)?)+)?(?::(?P<mode>\S+)?)?(?:\s+(?P<args>(?P<lhs>[^=]+)(?:=(?P<rhs>.*))?)?)?",
                flags=re.IGNORECASE)
            matcher = cls.re_match

        if (result := matcher.fullmatch(text)):
            return result

    def __init__(self, entry, match_obj):
        super().__init__(entry, match_obj)
        self.mdict = self.match_obj.groupdict()
        self.cmd = self.mdict["cmd"]
        self.args = self.mdict["args"]
        self.remaining = self.args
        self.lsargs = None
        self.rsargs = None


class BaseCommandMatcher:
    priority = 0
    core = None

    def __init__(self, name):
        self.name = name
        self.at_cmdmatcher_creation()

    @classmethod
    def access(self, entry: "QueueEntry"):
        return True

    def at_cmdmatcher_creation(self):
        """
        This is called when the CommandGroup is instantiated in order to load
        Commands. use self.add(cmdclass) to add Commands.
        """
        pass

    def match(self, entry: "QueueEntry", text: str):
        pass

    def populate_help(self, entry: "QueueEntry", data):
        pass

    def __repr__(self):
        return f"<{self.__class__.__name__}: {self.name}>"


class PythonCommandMatcher(BaseCommandMatcher):

    def __init__(self, name):
        self.cmds = set()
        super().__init__(name)

    def add(self, cmd_class):
        self.cmds.add(cmd_class)

    def match(self, entry: "QueueEntry", text: str):
        for cmd in self.cmds:
            if cmd.access(entry) and (result := cmd.match(entry, text)):
                return cmd(entry, result)

    def populate_help(self, entry: "QueueEntry", data):
        for cmd in self.cmds:
            if cmd.help_category and cmd.access(entry):
                data[cmd.help_category].add(cmd)
