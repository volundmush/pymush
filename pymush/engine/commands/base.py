import re
from pymush.utils import formatter as fmt
from mudstring.patches.text import MudText, OLD_TEXT
from typing import Union


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
    def help(cls, interpreter):
        """
        This is called by the command-help system if help is called on this command.
        """
        enactor = interpreter.frame.enactor
        if cls.__doc__:
            out = fmt.FormatList(enactor)
            out.add(fmt.Header(f"Help: {cls.name}"))
            out.add(fmt.Line(cls.__doc__))
            out.add(fmt.Footer())
            enactor.send(out)
        else:
            enactor.msg(text="Help is not implemented for this command.")

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
        self.game = None

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
    available_switches = []

    def at_pre_execute(self):
        for sw in self.switches:
            if sw not in self.available_switches:
                raise CommandException(f"{self.name.upper()} doesn't know switch: /{sw}")

    def split_args(self, text: Union[str, OLD_TEXT]):
        escaped = False
        curly_depth = 0
        i = 0
        start_segment = i
        plain = text.plain if isinstance(text, OLD_TEXT) else text

        while i < len(plain):
            if escaped:
                escaped = False
            else:
                c = plain[i]
                if c == '{':
                    curly_depth += 1
                elif c == '}' and curly_depth:
                    curly_depth -= 1
                elif c == '\\':
                    escaped = True
                elif c == ',':
                    yield self.parser.evaluate(text[start_segment:i], no_eval=True)
                    start_segment = i+1
            i += 1

        if i > start_segment:
            yield self.parser.evaluate(text[start_segment:i], no_eval=True)

    def split_by(self, text: Union[str, OLD_TEXT], delim=' '):
        plain = text.plain if isinstance(text, OLD_TEXT) else text

        i = self.parser.find_notspace(plain, 0)
        start_segment = i

        while i < len(plain):
            c = plain[i]
            if c == delim:
                elem = text[start_segment:i]
                if len(elem):
                    elem = self.parser.evaluate(elem, no_eval=True)
                    if len(elem):
                        yield elem
                start_segment = i
            else:
                pass
            i += 1

        if i > start_segment:
            elem = text[start_segment:i]
            if len(elem):
                elem = self.parser.evaluate(elem, no_eval=True)
                if len(elem):
                    yield elem

    def eqsplit_args(self, text: Union[str, OLD_TEXT]):
        escaped = False

        plain = text.plain if isinstance(text, OLD_TEXT) else text
        paren_depth = 0
        curly_depth = 0
        square_depth = 0
        i = -1

        while True:
            i += 1
            if i > len(plain) - 1:
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
                        lsargs = self.parser.evaluate(text[:i], no_eval=True)
                        if not len(lsargs):
                            lsargs = MudText("")
                        rsargs = self.parser.evaluate(text[i+1:], no_eval=True)
                        if not len(rsargs):
                            rsargs = MudText("")
                        return lsargs, rsargs

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
        switches = '' if self.mdict['switches'] is None else self.mdict['switches']
        self.switches = {sw.strip().lower() for sw in switches.strip('/').split('/')} if switches else set()
        self.remaining = self.args


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
