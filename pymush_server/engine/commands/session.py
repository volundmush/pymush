from . base import MushCommand, CommandException, PythonCommandMatcher, BaseCommandMatcher, Command
from pymush_server.utils import formatter as fmt
import re


class OOCCommand(Command):
    name = '@ooc'
    re_match = re.compile(r"^(?P<cmd>@ooc)(?: +(?P<args>.+)?)?", flags=re.IGNORECASE)

    async def execute(self):
        for con in self.enactor.connections.all():
            con.leave(self.enactor)
            self.enactor.core.selectscreen(con)
        self.msg(text="Character returned to storage.")


class PlayViewCommandMatcher(PythonCommandMatcher):

    def at_cmdmatcher_creation(self):
        self.add(OOCCommand)
