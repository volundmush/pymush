import re

from mudrich.encodings.pennmush import ansi_fun, send_menu

from pymush.utils import formatter as fmt

from .base import Command, MushCommand, CommandException, PythonCommandMatcher
from .shared import PyCommand, HelpCommand, QuitCommand


class _LoginCommand(Command):
    """
    Simple bit of logic added for the login commands to deal with syntax like:
    connect "user name" password
    """

    re_quoted = re.compile(
        r'^"(?P<name>.+)"(: +(?P<password>.+)?)?', flags=re.IGNORECASE
    )
    re_unquoted = re.compile(
        r"^(?P<name>\S+)(?: +(?P<password>.+)?)?", flags=re.IGNORECASE
    )
    help_category = "Login"

    def parse_login(self, error):
        mdict = self.match_obj.groupdict()
        if not mdict["args"]:
            raise CommandException(error)

        result = self.re_quoted.match(mdict["args"])
        if not result:
            result = self.re_unquoted.match(mdict["args"])
        rdict = result.groupdict()
        if not (rdict["name"] and rdict["password"]):
            raise CommandException(error)
        return rdict["name"], rdict["password"]


class ConnectCommand(_LoginCommand):
    """
    Logs in to an existing User Account.

    Usage:
        connect <username> <password>

    If username contains spaces:
        connect "<user name>" <password>
    """

    name = "connect"
    re_match = re.compile(r"^(?P<cmd>connect)(?: +(?P<args>.+))?", flags=re.IGNORECASE)
    usage = (
        "Usage: "
        + ansi_fun("hw", "connect <username> <password>")
        + " or "
        + ansi_fun("hw", 'connect "<user name>" password')
    )

    async def execute(self):
        name, password = self.parse_login(self.usage)
        result, err = await self.entry.check_login(name, password)
        if not result:
            raise CommandException(err)


class CreateCommand(_LoginCommand):
    """
    Creates a new Account.

    Usage:
        create <username> <password>

    If username contains spaces:
        create "<user name>" <password>
    """

    name = "create"
    re_match = re.compile(r"^(?P<cmd>create)(?: +(?P<args>.+)?)?", flags=re.IGNORECASE)
    usage = (
        "Usage: "
        + ansi_fun("hw", "create <username> <password>")
        + " or "
        + ansi_fun("hw", 'create "<user name>" <password>')
    )

    async def execute(self):
        name, password = self.parse_login(self.usage)
        result, err = await self.entry.create_user(name, password)
        if not result:
            raise CommandException(err)


class LoginCommandMatcher(PythonCommandMatcher):
    def at_cmdmatcher_creation(self):
        self.add(CreateCommand)
        self.add(ConnectCommand)
        self.add(HelpCommand)
        self.add(QuitCommand)
