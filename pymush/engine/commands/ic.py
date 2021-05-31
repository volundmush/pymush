from . base import MushCommand, CommandException, PythonCommandMatcher, BaseCommandMatcher, Command
from pymush.utils import formatter as fmt
import re
from .shared import PyCommand, HelpCommand
from pymush.engine.cmdqueue import QueueEntry


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
    def access(cls, entry):
        return entry.session.get_alevel() >= 10

    def available_vars(self):
        out = super().available_vars()
        out["session"] = self.entry.session
        return out


class QuellCommand(PyCommand):
    name = '@quell'
    re_match = re.compile(r"^(?P<cmd>@quell)(?: +(?P<args>.+)?)?", flags=re.IGNORECASE)

    @classmethod
    def access(cls, entry):
        print(f"CHECKING QUELL... {entry}")
        print(f"alevel: {entry.session.get_alevel(ignore_quell=True)}")
        return entry.session.get_alevel(ignore_quell=True) > 0

    def execute(self):
        self.entry.session.quelled = not self.entry.session.quelled
        if self.entry.session.quelled:
            self.msg(text="You are now quelled! Admin permissions suppressed.")
        else:
            self.msg(text="You are no longer quelled! Admin permissions enabled!")


class RunCommand(MushCommand):
    name = '@run'
    aliases = ['@ru']
    help_category = 'System'

    def execute(self):
        if not self.args:
            raise CommandException("Nothing to run!")
        new_entry = QueueEntry.from_script(self.entry.enactor, self.args, self.entry.enactor, self.entry.enactor)
        self.entry.queue.push(new_entry)


class SessionCommandMatcher(PythonCommandMatcher):

    def at_cmdmatcher_creation(self):
        self.add(OOCCommand)
        self.add(SessionPyCommand)
        self.add(QuellCommand)
        self.add(HelpCommand)
        self.add(RunCommand)
