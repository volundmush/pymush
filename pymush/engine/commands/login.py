import re
import sys
import time
import traceback
from athanor.utils import partial_match
from . base import Command, MushCommand, CommandException, PythonCommandMatcher
from mudstring.encodings.pennmush import ansi_fun, send_menu
from . shared import PyCommand


from pymush.db.importer import Importer
from pymush.db.flatfile import check_password
from pymush.utils import formatter as fmt
from . help import HelpCommand


class _LoginCommand(Command):
    """
    Simple bit of logic added for the login commands to deal with syntax like:
    connect "user name" password
    """
    re_quoted = re.compile(r'"(?P<name>.+)"(: +(?P<password>.+)?)?', flags=re.IGNORECASE)
    re_unquoted = re.compile(r'^(?P<name>\S+)(?: +(?P<password>.+)?)?', flags=re.IGNORECASE)
    help_category = 'Login'

    def parse_login(self, error):
        mdict = self.match_obj.groupdict()
        if not mdict["args"]:
            raise CommandException(error)

        result = self.re_quoted.fullmatch(mdict["args"])
        if not result:
            result = self.re_unquoted.fullmatch(mdict["args"])
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
        candidates = self.service.type_index[self.service.obj_classes['USER']]
        account, error = self.service.search_objects(name, candidates=candidates, exact=True)
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
        pass_hash = self.service.crypt_con.hash(password)
        account, error = self.service.create_object('user', name)
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


class PennConnect(_LoginCommand):
    """
    This command will access a PennMUSH character and login using their
    old password. This will then initialize the imported Account and
    log you in.

    Usage:
        pconnect <character> <password>

    If a character name contains spaces, then:
        pconnect "<character name>" password
    """
    name = 'pconnect'
    re_match = re.compile(r"^(?P<cmd>pconnect)(?: +(?P<args>.+))?", flags=re.IGNORECASE)
    usage = "Usage: " + ansi_fun("hw", "pconnect <username> <password>") + " or " + ansi_fun("hw", 'pconnect "<user name>" password')

    def execute(self):
        name, password = self.parse_login(self.usage)
        candidates = self.service.type_index[self.service.obj_classes['PLAYER']]
        character, error = self.service.search_objects(name, candidates=candidates, exact=True)
        if error:
            raise CommandException("Sorry, that was an incorrect username or password.")
        if not character:
            raise CommandException("Sorry, that was an incorrect username or password.")
        if not (old_hash_attr := character.attributes.get('XYXXY')):
            raise CommandException("Sorry, that was an incorrect username or password.")
        if not check_password(old_hash_attr.value.plain, password):
            raise CommandException("Sorry, that was an incorrect username or password.")
        if not (acc := character.account):
            raise CommandException("Character found! However this character has no account. To continue, create an account and bind the character after logging in.")
        self.entry.connection.login(acc)

        self.msg(text=f"Your Account password has been set to the password you entered just now.\n"
                      f"Next time, you can login using the normal connect command.\n"
                      f"pconnect will not work on your currently bound characters again.\n"
                      f"If any imported characters are not appearing, try @pbind <name>=<password>\n"
                      f"Should that fail, contact an administrator.")
        acc.change_password(password)
        for char in acc.characters:
            char.attributes.wipe('XYXXY')


class LoginPyCommand(PyCommand):

    @classmethod
    def access(cls, entry):
        #if entry.game.objects:
        #    return False
        return True


class ImportCommand(Command):
    name = "@import"
    re_match = re.compile(r"^(?P<cmd>@import)(?: +(?P<args>.+)?)?", flags=re.IGNORECASE)
    help_category = 'System'

    @classmethod
    def access(cls, entry):
        if entry.game.objects:
            return False
        return True

    def execute(self):
        penn = Importer(self.entry.enactor, 'outdb')
        self.msg(f"Database loaded: {len(penn.db.objects)} objects detected!")
        penn.run()


class Test(Command):
    name = "test"
    re_match = re.compile(r"^(?P<cmd>test)(?: +(?P<args>.+)?)?", flags=re.IGNORECASE)

    @classmethod
    def access(cls, entry):
        return True

    def execute(self):
        menu = send_menu("testing", (("testing", "testing"),))
        self.entry.enactor.menu = menu
        out = fmt.FormatList(self.entry.enactor)
        out.add(fmt.Line(menu))
        self.entry.enactor.send(out)


class LoginCommandMatcher(PythonCommandMatcher):

    def access(self, enactor):
        return enactor.relations.get('account') is None

    def at_cmdmatcher_creation(self):
        self.add(CreateCommand)
        self.add(ConnectCommand)
        self.add(PennConnect)
        self.add(LoginPyCommand)
        self.add(ImportCommand)
        self.add(Test)


class ConnectionCommandMatcher(PythonCommandMatcher):

    def at_cmdmatcher_creation(self):
        self.add(PyCommand)
        self.add(QuitCommand)
        self.add(HelpCommand)
