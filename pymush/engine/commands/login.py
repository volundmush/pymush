import re
import sys
import time
import traceback
from athanor.utils import partial_match
from . base import Command, MushCommand, CommandException, PythonCommandMatcher
from mudstring.encodings.pennmush import ansi_fun, send_menu
from . shared import PyCommand, HelpCommand

from pymush.utils import formatter as fmt


class _LoginCommand(Command):
    """
    Simple bit of logic added for the login commands to deal with syntax like:
    connect "user name" password
    """
    re_quoted = re.compile(r'^"(?P<name>.+)"(: +(?P<password>.+)?)?', flags=re.IGNORECASE)
    re_unquoted = re.compile(r'^(?P<name>\S+)(?: +(?P<password>.+)?)?', flags=re.IGNORECASE)
    help_category = 'Login'

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
    Logs in to an existing Account.

    Usage:
        connect <username> <password>

    If username contains spaces:
        connect "<user name>" <password>
    """
    name = "connect"
    re_match = re.compile(r"^(?P<cmd>connect)(?: +(?P<args>.+))?", flags=re.IGNORECASE)
    usage = "Usage: " + ansi_fun("hw", "connect <username> <password>") + " or " + ansi_fun("hw", 'connect "<user name>" password')

    def execute(self):
        name, password = self.parse_login(self.usage)
        candidates = self.game.type_index['USER']
        account, error = self.game.search_objects(name, candidates=candidates, exact=True)
        if error:
            raise CommandException("Sorry, that was an incorrect username or password.")
        if not account:
            raise CommandException("Sorry, that was an incorrect username or password.")
        if not account.check_password(password):
            raise CommandException("Sorry, that was an incorrect username or password.")
        self.entry.connection.login(account)


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
    usage = "Usage: " + ansi_fun("hw", 'create <username> <password>') + ' or ' + ansi_fun("hw", 'create "<user name>" <password>')

    def execute(self):
        name, password = self.parse_login(self.usage)
        pass_hash = self.game.crypt_con.hash(password)
        account, error = self.game.create_object('USER', name)
        if error:
            raise CommandException(error)
        account.password = pass_hash
        # just ignoring password for now.
        cmd = f'connect "{account.name}" <password>' if ' ' in account.name else f'connect {account.name} <password>'
        self.msg(text="Account created! You can login with " + ansi_fun('hw', cmd))


class QuitCommand(Command):
    """
    Disconnects this connection from the game.
    """
    name = 'QUIT'
    re_match = re.compile(r"^(?P<cmd>QUIT)(?: +(?P<args>.+)?)?", flags=re.IGNORECASE)
    help_category = 'System'

    def execute(self):
        if (pview := self.entry.enactor.relations.get('playview', None)):
            mdict = self.match_obj.groupdict()
            args = mdict.get('args', "")
            if args is None or not args.upper().startswith('FORCE'):
                raise CommandException("Use QUIT FORCE to disconnect while IC. This may leave your character linkdead for a time. Use @ooc then QUIT to cleanly logout.")
        out = fmt.FormatList(self.entry.enactor)
        out.add(fmt.Line("See you again!"))
        out.disconnect = True
        out.reason = 'quit'
        self.send(out)


class LoginPyCommand(PyCommand):

    @classmethod
    def access(cls, interpreter):
        #if entry.game.objects:
        #    return False
        return True


class Test(Command):
    name = "test"
    re_match = re.compile(r"^(?P<cmd>test)(?: +(?P<args>.+)?)?", flags=re.IGNORECASE)

    @classmethod
    def access(cls, interpreter):
        return True

    def execute(self):
        menu = send_menu("testing", (("testing", "testing"),))
        self.entry.enactor.menu = menu
        out = fmt.FormatList(self.entry.enactor)
        out.add(fmt.Line(menu))
        self.entry.enactor.send(out)


class LoginCommandMatcher(PythonCommandMatcher):

    def at_cmdmatcher_creation(self):
        self.add(CreateCommand)
        self.add(ConnectCommand)
        self.add(LoginPyCommand)
        self.add(Test)
        self.add(HelpCommand)
