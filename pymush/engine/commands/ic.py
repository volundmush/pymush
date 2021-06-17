import re

from .base import (
    MushCommand,
    CommandException,
    PythonCommandMatcher,
    BaseCommandMatcher,
    Command,
)
from .shared import PyCommand, HelpCommand


class LogoutCommand(Command):
    name = "@logout"
    re_match = re.compile(r"^(?P<cmd>@logout)(?: +(?P<args>.+)?)?", flags=re.IGNORECASE)

    async def execute(self):
        mdict = self.match_obj.groupdict()
        args = mdict["args"]
        if args is None:
            args = ""
        can_end, why_not = self.entry.session.can_end_safely()
        if can_end:
            self.entry.session.end_safely()
            return
        elif args.lower() == "force":
            self.entry.session.end_unsafely()
        else:
            if why_not:
                self.enactor.msg(why_not)
            self.enactor.msg(
                "Cannot safely logout right now. To terminate cohnnections while leaving session linkdead, use @logout force"
            )


class OOCCommand(Command):
    name = "@ooc"
    re_match = re.compile(r"^(?P<cmd>@ooc)(?: +(?P<args>.+)?)?", flags=re.IGNORECASE)

    async def execute(self):
        mdict = self.match_obj.groupdict()
        args = mdict["args"]
        if args is None:
            args = ""
        if len(self.entry.session.connections) == 1:
            self.enactor.msg(
                "Cannot go @ooc with just one connection left on the session! To logout, use @logout instead."
            )
            return
        self.entry.connection.leave_session()
        self.entry.connection.show_select_screen()


class SessionPyCommand(PyCommand):
    @classmethod
    async def access(cls, entry):
        return entry.session.get_alevel() >= 10

    def available_vars(self):
        out = super().available_vars()
        out["entry"] = self.entry
        out["executor"] = self.entry.executor
        out["enactor"] = self.entry.enactor
        out["caller"] = self.entry.caller
        out["connection"] = self.entry.connection
        out["session"] = self.entry.session
        out["game"] = self.entry.game
        return out


class AdminCommand(PyCommand):
    name = "@admin"
    re_match = re.compile(r"^(?P<cmd>@admin)(?: +(?P<args>.+)?)?", flags=re.IGNORECASE)

    @classmethod
    async def access(cls, entry):
        return entry.session.get_alevel(ignore_fake=True) > 0

    async def execute(self):
        self.entry.session.admin = not self.entry.session.admin
        if self.entry.session.admin:
            self.msg(text="You are now in admin mode! Admin permissions enabled.")
        else:
            self.msg(
                text="You are no longer in admin mode. Admin permissions suppressed."
            )


class QuitCommand(Command):
    """
    Disconnects this connection from the game.
    """

    name = "QUIT"
    re_match = re.compile(r"^(?P<cmd>QUIT)(?: +(?P<args>.+)?)?", flags=re.IGNORECASE)
    help_category = "System"

    async def execute(self):
        raise Exception("This is a test of the command exception system!")
        # self.enactor.msg("Cannot QUIT while @ic! Please see @ooc and @logout instead!")


class SessionCommandMatcher(PythonCommandMatcher):
    async def access(self, entry: "TaskEntry"):
        return bool(entry.connection)

    def at_cmdmatcher_creation(self):
        self.add(OOCCommand)
        self.add(SessionPyCommand)
        self.add(AdminCommand)
        self.add(HelpCommand)
        self.add(QuitCommand)
        self.add(LogoutCommand)
