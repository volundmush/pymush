import re

from typing import Union, Optional, Tuple, List

from rich.text import Text

from pymush.utils import formatter as fmt
from ..api import BaseApi


class CommandException(Exception):
    pass


class Command(BaseApi):
    name = None  # Name must be set to a string!
    aliases = []
    help_category = None

    @property
    def session(self):
        return self.interpreter.session

    @property
    def connection(self):
        return self.interpreter.connection

    @classmethod
    def access(cls, interpreter: "Interpreter"):
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
    def match(cls, enactor, text: Text):
        """
        Called by the CommandGroup to determine if this command matches.
        Returns False or a Regex Match object.

        Or any kind of match, really. The parsed match will be returned and re-used by .execute()
        so use whatever you want.
        """
        if (result := cls.re_match.fullmatch(text.plain)) :
            return result

    def __init__(self, interpreter, text, match_obj):
        """
        Instantiates the command.
        """
        self.text = text
        self.match_obj = match_obj
        self.interpreter = interpreter

    def split_args(self, text: Union[str, Text]):
        return self.split_cmd_args(text)

    @property
    def parser(self):
        return self.interpreter.parser

    def execute(self):
        """
        Do whatever the command does.
        """

    def at_pre_execute(self):
        pass

    def at_post_execute(self):
        pass

    def __repr__(self):
        return f"<{self.__class__.__name__}: {self.name}>"


class MushCommand(Command):
    available_switches = []

    def at_pre_execute(self):
        for sw in self.switches:
            if sw not in self.available_switches:
                raise CommandException(
                    f"{self.name.upper()} doesn't know switch: /{sw}"
                )

    @classmethod
    def match(cls, entry, text):
        """
        Called by the CommandGroup to determine if this command matches.
        Returns False or a Regex Match object.

        Or any kind of match, really. The parsed match will be returned and re-used by .execute()
        so use whatever you want.
        """
        if not (matcher := getattr(cls, "re_match", None)):
            names = [cls.name]
            names.extend(getattr(cls, "aliases", []))
            names = "|".join(names)
            cls.re_match = re.compile(
                f"^(?P<cmd>{names})(?P<switches>(/(\w+)?)+)?(?::(?P<mode>\S+)?)?(?:\s+(?P<args>(?P<lhs>[^=]+)(?:=(?P<rhs>.*))?)?)?",
                flags=re.IGNORECASE,
            )
            matcher = cls.re_match

        if (result := matcher.fullmatch(text.plain)) :
            return result

    def __init__(self, interpreter, text, match_obj):
        super().__init__(interpreter, text, match_obj)
        self.mdict = self.match_obj.groupdict()
        self.cmd = text[match_obj.start("cmd") : match_obj.end("cmd")]
        self.args = text[match_obj.start("args") : match_obj.end("args")]
        switches = "" if self.mdict["switches"] is None else self.mdict["switches"]
        self.mode = self.mdict["mode"]
        self.switches = (
            {sw.strip().lower() for sw in switches.strip("/").split("/")}
            if switches
            else set()
        )


class BaseCommandMatcher:
    priority = 0
    core = None

    def __init__(self, name):
        self.name = name
        self.at_cmdmatcher_creation()

    @classmethod
    def access(self, interpreter: "Interpreter"):
        return True

    def at_cmdmatcher_creation(self):
        """
        This is called when the CommandGroup is instantiated in order to load
        Commands. use self.add(cmdclass) to add Commands.
        """
        pass

    def match(self, interpreter: "Interpreter", text: Text):
        pass

    def populate_help(self, interpreter: "Interpreter", data):
        pass

    def __repr__(self):
        return f"<{self.__class__.__name__}: {self.name}>"


class PythonCommandMatcher(BaseCommandMatcher):
    def __init__(self, name):
        self.cmds = set()
        super().__init__(name)

    def add(self, cmd_class):
        self.cmds.add(cmd_class)

    def match(self, interpreter: "Interpreter", text: Text):
        for cmd in self.cmds:
            if cmd.access(interpreter) and (result := cmd.match(interpreter, text)):
                return cmd(interpreter, text, result)

    def populate_help(self, interpreter: "Interpreter", data):
        for cmd in self.cmds:
            if cmd.help_category and cmd.access(interpreter):
                data[cmd.help_category].add(cmd)
