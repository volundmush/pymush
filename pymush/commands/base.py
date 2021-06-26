import re

from typing import Union, Optional, Tuple, List

from mudrich.text import Text

from pymush.utils import formatter as fmt


class CommandException(Exception):
    pass


class Command:
    name = None  # Name must be set to a string!
    aliases = []
    help_category = None
    timestamp_after = True

    @classmethod
    async def access(cls, entry: "TaskEntry"):
        """
        This returns true if <enactor> is able to see and use this command.

        Use this for admin permissions locks as well as conditional access, such as
        'is the enactor currently in a certain kind of location'.
        """
        return True

    @classmethod
    def help(cls, entry: "TaskEntry"):
        """
        This is called by the command-help system if help is called on this command.
        """
        executor = entry.executor

        if cls.__doc__:
            out = fmt.FormatList(executor)
            out.add(fmt.Header(f"Help: {cls.name}"))
            out.add(fmt.Line(cls.__doc__))
            out.add(fmt.Footer())
            executor.send(out)
        else:
            executor.msg(text="Help is not implemented for this command.")

    @classmethod
    async def match(cls, entry: "TaskEntry", text: Text):
        """
        Called by the CommandGroup to determine if this command matches.
        Returns False or a Regex Match object.

        Or any kind of match, really. The parsed match will be returned and re-used by .execute()
        so use whatever you want.
        """
        if (result := cls.re_match.fullmatch(text.plain)) :
            return result

    def __init__(self, entry: "TaskEntry", text: Text, match_obj):
        """
        Instantiates the command.
        """
        self.text = text
        self.match_obj = match_obj
        self.entry = entry

    async def execute(self):
        """
        Do whatever the command does.
        """

    async def at_pre_execute(self):
        pass

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

    @property
    def game(self):
        return self.entry.game

    @property
    def db(self):
        return self.game.db

    def msg(self, *args, **kwargs):
        self.executor.msg(*args, **kwargs)


class BaseCommandMatcher:
    priority = 0
    core = None

    def __init__(self, name):
        self.name = name
        self.at_cmdmatcher_creation()

    @classmethod
    async def access(cls, entry: "TaskEntry"):
        return True

    def at_cmdmatcher_creation(self):
        """
        This is called when the CommandGroup is instantiated in order to load
        Commands. use self.add(cmdclass) to add Commands.
        """
        pass

    async def match(self, entry: "TaskEntry", text: Text):
        pass

    async def populate_help(self, entry: "TaskEntry", data):
        pass

    def __repr__(self):
        return f"<{self.__class__.__name__}: {self.name}>"


class PythonCommandMatcher(BaseCommandMatcher):
    def __init__(self, name):
        self.cmds = set()
        super().__init__(name)

    def add(self, cmd_class):
        self.cmds.add(cmd_class)

    async def match(self, entry: "TaskEntry", text: Text):
        for cmd in self.cmds:
            if await cmd.access(entry) and (result := await cmd.match(entry, text)):
                return cmd(entry, text, result)

    async def populate_help(self, entry: "TaskEntry", data):
        for cmd in self.cmds:
            if cmd.help_category and await cmd.access(entry):
                data[cmd.help_category].add(cmd)
