import re

from typing import Union, Optional, Tuple, List

from mudrich.text import Text

from pymush.utils import formatter as fmt
from ..api import BaseApi


class MushCommandException(Exception):
    pass


class MushCommand(BaseApi):
    name = None  # Name must be set to a string!
    aliases = []
    help_category = None
    timestamp_after = True
    available_switches = []

    @classmethod
    async def access(cls, task):
        """
        This returns true if <executor> is able to see and use this command.

        Use this for admin permissions locks as well as conditional access, such as
        'is the enactor currently in a certain kind of location'.
        """
        return True

    @classmethod
    def help(cls, task):
        """
        This is called by the command-help system if help is called on this command.
        """
        executor = task.executor

        if cls.__doc__:
            out = fmt.FormatList(executor)
            out.add(fmt.Header(f"Help: {cls.name}"))
            out.add(fmt.Line(cls.__doc__))
            out.add(fmt.Footer())
            executor.send(out)
        else:
            executor.msg(text="Help is not implemented for this command.")

    @classmethod
    async def match(cls, task, text):
        """
        Called by the CommandMatcher to check if this command should be called.
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

        if (result := matcher.fullmatch(text.plain)):
            return result

    def __init__(self, entry: "TaskEntry", text: Text, match_obj):
        """
        Instantiates the command.
        """
        self.text = text
        self.match_obj = match_obj
        self.entry = entry
        self.mdict = self.match_obj.groupdict()
        self.cmd = text[match_obj.start("cmd"): match_obj.end("cmd")]
        self.args = text[match_obj.start("args"): match_obj.end("args")]
        switches = "" if self.mdict["switches"] is None else self.mdict["switches"]
        self.mode = self.mdict["mode"]
        self.switches = (
            {sw.strip().lower() for sw in switches.strip("/").split("/")}
            if switches
            else set()
        )

    async def execute(self):
        """
        Do whatever the command does.
        """

    async def at_pre_execute(self):
        for sw in self.switches:
            if sw not in self.available_switches:
                raise MushCommandException(
                    f"{self.name.upper()} doesn't know switch: /{sw}"
                )

    async def at_post_execute(self):
        pass

    def __repr__(self):
        return f"<{self.__class__.__name__}: {self.name}>"

    @property
    def executor(self):
        return self.entry.executor

    @property
    def caller(self):
        return self.entry.caller

    @property
    def enactor(self):
        return self.entry.enactor

    def msg(self, *args, **kwargs):
        self.executor.msg(*args, **kwargs)


class MushCommandMatcher:
    priority = 0

    def __init__(self, name):
        self.name = name
        self.at_cmdmatcher_creation()
        self.cmds = set()

    @classmethod
    async def access(cls, task):
        return True

    def at_cmdmatcher_creation(self):
        """
        This is called when the CommandGroup is instantiated in order to load
        Commands. use self.add(cmdclass) to add Commands.
        """
        pass

    async def match(self, task, text: Text):
        for cmd in self.cmds:
            if await cmd.access(task) and (result := await cmd.match(task, text)):
                return cmd(task, text, result)

    async def populate_help(self, task, data: dict):
        for cmd in self.cmds:
            if cmd.help_category and await cmd.access(task):
                data[cmd.help_category].add(cmd)

    def __repr__(self):
        return f"<{self.__class__.__name__}: {self.name}>"
