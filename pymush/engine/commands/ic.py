import re

from . base import MushCommand, CommandException, PythonCommandMatcher, BaseCommandMatcher, Command
from .shared import PyCommand, HelpCommand


class OOCCommand(Command):
    name = '@ooc'
    re_match = re.compile(r"^(?P<cmd>@ooc)(?: +(?P<args>.+)?)?", flags=re.IGNORECASE)

    def execute(self):
        for con in self.enactor.connections.all():
            con.leave(self.enactor)
            self.enactor.core.selectscreen(con)
        self.msg(text="Character returned to storage.")


class SessionPyCommand(PyCommand):

    @classmethod
    def access(cls, interpreter):
        return interpreter.session.get_alevel() >= 10

    def available_vars(self):
        out = super().available_vars()
        out["session"] = self.entry.session
        return out


class QuellCommand(PyCommand):
    name = '@admin'
    re_match = re.compile(r"^(?P<cmd>@quell)(?: +(?P<args>.+)?)?", flags=re.IGNORECASE)

    @classmethod
    def access(cls, interpreter):
        return interpreter.session.get_alevel(ignore_fake=True) > 0

    def execute(self):
        self.entry.session.admin = not self.entry.session.admin
        if self.entry.session.admin:
            self.msg(text="You are now in admin mode! Admin permissions enabled.")
        else:
            self.msg(text="You are no longer in admin mode. Admin permissions suppressed.")


class BuildCommand(PyCommand):
    name = '@build'
    re_match = re.compile(r"^(?P<cmd>@build)(?: +(?P<args>.+)?)?", flags=re.IGNORECASE)

    @classmethod
    def access(cls, interpreter):
        return interpreter.session.get_alevel() >= 1

    def execute(self):
        self.entry.session.build = not self.entry.session.build
        if self.entry.session.build:
            self.msg(text="You are now in building mode! Scripting commands enabled.")
        else:
            self.msg(text="You are no longer building! Scripting commands disabled.")


class SessionCommandMatcher(PythonCommandMatcher):

    def access(self, interpreter: "Interpreter"):
        return bool(interpreter.session)

    def at_cmdmatcher_creation(self):
        self.add(OOCCommand)
        self.add(SessionPyCommand)
        self.add(QuellCommand)
        self.add(HelpCommand)
        self.add(BuildCommand)
