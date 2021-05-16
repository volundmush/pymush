import re
import sys
import time
import traceback
from from pymush.utils import partial_match
from . base import Command, MushCommand, CommandException, PythonCommandMatcher
from rich.text import Text

from pymush_server.db.importer import Importer
from pymush_server.db.flatfile import check_password
from pymush_server.utils import formatter as fmt
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
    usage = "Usage: " + AnsiString.from_args("hw", "connect <username> <password>") + " or " + AnsiString.from_args("hw", 'connect "<user name>" password')

    def execute(self):
        name, password = self.parse_login(self.usage)
        account, error = self.core.search_tag("account", name, exact=True)
        if error:
            raise CommandException("Sorry, that was an incorrect username or password.")
        if not account:
            raise CommandException("Sorry, that was an incorrect username or password.")
        if not account.verify_password(password):
            raise CommandException("Sorry, that was an incorrect username or password.")
        self.enactor.login(account)
        self.core.selectscreen(self.enactor)


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
    usage = "Usage: " + AnsiString.from_args("hw", 'create <username> <password>') + ' or ' + AnsiString.from_args("hw", 'create "<user name>" <password>')

    def execute(self):
        name, password = self.parse_login(self.usage)
        pass_hash = CRYPT_CON.hash(password)
        namespace = self.enactor.core.namespace_prefix['A']
        account, error = self.core.mapped_typeclasses["account"].create(name=name, namespace=namespace)
        if error:
            raise CommandException(error)
        account.set_password(pass_hash, nohash=True)
        # just ignoring password for now.
        cmd = f'connect "{account.name}" <password>' if ' ' in account.name else f'connect {account.name} <password>'
        self.msg(text="Account created! You can login with " + AnsiString.from_args('hw', cmd))


class WelcomeScreenCommand(_LoginCommand):
    name = "look"
    re_match = re.compile(r"^(?P<cmd>look)(?: +(?P<args>.+)?)?", flags=re.IGNORECASE)

    def execute(self):
        self.core.welcomescreen(self.enactor)


class QuitCommand(Command):
    """
    Disconnects this connection from the game.
    """
    name = 'QUIT'
    re_match = re.compile(r"^(?P<cmd>QUIT)(?: +(?P<args>.+)?)?", flags=re.IGNORECASE)
    help_category = 'System'

    def execute(self):
        if (pview := self.enactor.relations.get('playview', None)):
            mdict = self.match_obj.groupdict()
            args = mdict.get('args', "")
            if args is None or not args.upper().startswith('FORCE'):
                raise CommandException("Use QUIT FORCE to disconnect while IC. This may leave your character linkdead for a time. Use @ooc then QUIT to cleanly logout.")
        out = fmt.FormatList(self.enactor)
        out.add(fmt.Text("See you again!"))
        out.disconnect = True
        out.reason = 'quit'
        self.enactor.send(out)


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
    usage = "Usage: " + AnsiString.from_args("hw", "pconnect <username> <password>") + " or " + AnsiString.from_args("hw", 'pconnect "<user name>" password')

    def execute(self):
        name, password = self.parse_login(self.usage)
        character, error = self.core.search_tag("penn_character", name, exact=True)
        if error:
            raise CommandException("Sorry, that was an incorrect username or password.")
        if not character:
            raise CommandException("Sorry, that was an incorrect username or password.")
        if not (old_hash := character.attributes.get('core', 'penn_hash')):
            raise CommandException("Sorry, that was an incorrect username or password.")
        if not check_password(old_hash, password):
            raise CommandException("Sorry, that was an incorrect username or password.")
        if not (acc := character.relations.get('account', None)):
            raise CommandException("Character found! However this character has no account. To continue, create an account and bind the character after logging in.")
        self.enactor.login(acc)
        self.core.selectscreen(self.enactor)
        self.msg(text=f"Your Account password has been set to the password you entered just now. Next time, you can login using the normal connect command. pconnect will not work on your currently bound characters again.")
        acc.set_password(password)
        for char in acc.characters.all():
            char.attributes.delete('core', 'penn_hash')


class PennBindCommand(MushCommand):
    """
    Binds a character imported from PennMUSH to an Account. This is
    mostly useful for cases where a character never had an Account
    before the game was migrated.

    Usage:
        @pbind <name>=<password>
    """
    name = '@pbind'
    aliases = ['@pbi', '@pbin']
    help_category = 'Character Management'

    def execute(self):
        target = self.gather_arg()
        password = self.gather_arg()
        if not (target and password):
            raise CommandException("Usage: @pbind <name>=<password>")
        character, error = self.core.search_tag("penn_character", target, exact=True)
        if error:
            raise CommandException("Sorry, that was an incorrect username or password.")
        if not character:
            raise CommandException("Sorry, that was an incorrect username or password.")
        if not (old_hash := character.attributes.get('core', 'penn_hash')):
            raise CommandException("Sorry, that was an incorrect username or password.")
        if not check_password(old_hash, password):
            raise CommandException("Sorry, that was an incorrect username or password.")
        if character.relations.get('account', None):
            raise CommandException("Sorry, that character belongs to an account. use pconnect to access them from the connect screen.")
        acc = self.enactor.relations.get('account', None)
        acc.characters.add(character)
        character.attributes.delete('core', 'penn_hash')
        self.msg(text=f"Character bound to your account!")


class CharCreateCommand(Command):
    name = "@charcreate"
    re_match = re.compile(r"^(?P<cmd>@charcreate)(?: +(?P<args>.+)?)?", flags=re.IGNORECASE)
    help_category = 'Character Management'

    def execute(self):
        mdict = self.match_obj.groupdict()
        if not (name := mdict.get("args", None)):
            raise CommandException("Must enter a name for the character!")
        identity = self.enactor.core.identity_prefix['C']
        char, error = self.core.mapped_typeclasses["mobile"].create(name=name, identity=identity)
        if error:
            raise CommandException(error)
        acc = self.enactor.relations.get('account', None)
        acc.characters.add(char)
        self.msg(text=AnsiString(f"Character '{char.name}' created! Use ") + AnsiString.from_args("hw", f"charselect {char.name}") + " to join the game!")


class CharSelectCommand(Command):
    name = "@ic"
    re_match = re.compile(r"^(?P<cmd>@ic)(?: +(?P<args>.+)?)?", flags=re.IGNORECASE)
    help_category = 'Character Management'

    def execute(self):
        mdict = self.match_obj.groupdict()
        acc = self.enactor.relations.get('account', None)
        if not (chars := acc.characters.all()):
            raise CommandException("No characters to join the game as!")
        if not (args := mdict.get("args", None)):
            names = ', '.join([obj.name for obj in chars])
            self.msg(text=f"You have the following characters: {names}")
            return
        if not (found := partial_match(args, chars, key=lambda x: x.name)):
            self.msg(text=f"Sorry, no character found named: {args}")
            return
        if not (pview := found.playviews.all()):
            pview, errors = self.core.mapped_typeclasses['playview'].create(objid=f"playview_{found.objid}")
            if errors:
                raise CommandException(errors)
            pview.at_playview_creation(found, self.enactor)
        else:
            pview = pview[0]
        self.enactor.join(pview)


class SelectScreenCommand(Command):
    name = "look"
    re_match = re.compile(r"^(?P<cmd>look)(?: +(?P<args>.+)?)?", flags=re.IGNORECASE)

    def execute(self):
        self.core.selectscreen(self.enactor)


class ThinkCommand(MushCommand):
    name = "think"
    aliases = ['th', 'thi', 'thin']
    help_category = 'System'

    def execute(self):
        if self.args:
            result, remaining, stopped = self.entry.evaluate(self.remaining)
            if result:
                self.msg(text=result)


class ImportCommand(Command):
    name = "@import"
    re_match = re.compile(r"^(?P<cmd>@import)(?: +(?P<args>.+)?)?", flags=re.IGNORECASE)
    help_category = 'System'

    @classmethod
    def access(cls, enactor):
        return True

    def execute(self):
        mdict = self.match_obj.groupdict()
        args = mdict.get("args", None)
        if not args:
            raise CommandException("@import requires arguments!")

        if not hasattr(self.enactor, 'penn'):
            Importer(self.enactor, 'outdb')
            self.msg("Database loaded and ready to Import!")

        op_map = {
            'grid': self.op_grid,
            'accounts': self.op_accounts
        }

        if not (op := partial_match(args, op_map.keys())):
            raise CommandException(f"Invalid operation for @import. supports: {op_map.keys()}")

        if op != 'start' and not hasattr(self.enactor, 'penn'):
            raise CommandException("@import database is not loaded. use @import start")
        op_map[op]()

    def op_grid(self):
        if 'grid' in self.enactor.penn.complete:
            raise CommandException("Those were already imported!")
        out = self.enactor.penn.import_grid()
        for k, v in out.items():
            self.msg(f"Imported: {k} - {len(v)}")
        self.enactor.penn.complete.add('grid')

    def op_accounts(self):
        if 'accounts' in self.enactor.penn.complete:
            raise CommandException("Those were already imported!")
        out = self.enactor.penn.import_accounts()
        self.msg(f"Imported {len(out)} Accounts!")
        out = self.enactor.penn.import_characters()
        self.msg(f"Imported {len(out)} Player Objects!")
        self.enactor.penn.complete.add('accounts')


class PyCommand(Command):
    name = '@py'
    re_match = re.compile(r"^(?P<cmd>@py)(?: +(?P<args>.+)?)?", flags=re.IGNORECASE)
    help_category = 'System'

    @classmethod
    def access(cls, enactor):
        return enactor.get_slevel() >= 10

    def execute(self):
        mdict = self.match_obj.groupdict()
        args = mdict.get("args", None)
        if not args:
            raise CommandException("@py requires arguments!")

        available_vars = {
            'self': self.enactor,
            'connection': self.enactor,
            "shinma": self.enactor.core.engine,
            "core": self.enactor.core
        }
        if (acc := self.enactor.relations.get('account')):
            available_vars['account'] = acc
            if (pv := self.enactor.relations.get('playview')):
                available_vars['playview'] = pv
                if (pup := pv.relations.get('puppet')):
                    available_vars['puppet'] = pup
                if (char := pv.relations.get('character')):
                    available_vars['character'] = char

        self.msg(text=f">>> {args}")

        try:
            # reroute standard output to game client console
            old_stdout = sys.stdout
            old_stderr = sys.stderr

            class FakeStd:
                def __init__(self, caller):
                    self.caller = caller

                def write(self, string):
                    self.caller.msg(text=string.rsplit("\n", 1)[0])

            fake_std = FakeStd(self.enactor)
            sys.stdout = fake_std
            sys.stderr = fake_std

            mode = "eval"
            try:
                pycode_compiled = compile(args, "", mode)
            except Exception:
                mode = "exec"
                pycode_compiled = compile(args, "", mode)

            measure_time = True
            duration = ""
            if measure_time:
                t0 = time.time()
                ret = eval(pycode_compiled, {}, available_vars)
                t1 = time.time()
                duration = " (runtime ~ %.4f ms)" % ((t1 - t0) * 1000)
                self.enactor.msg(text=duration)
            else:
                ret = eval(pycode_compiled, {}, available_vars)

        except Exception:
            errlist = traceback.format_exc().split("\n")
            if len(errlist) > 4:
                errlist = errlist[4:]
            ret = "\n".join("%s" % line for line in errlist if line)
        finally:
            # return to old stdout
            sys.stdout = old_stdout
            sys.stderr = old_stderr

        if ret is None:

            return
        elif isinstance(ret, tuple):

            # we must convert here to allow msg to pass it (a tuple is confused
            # with a outputfunc structure)
            ret = str(ret)

        self.enactor.msg(text=repr(ret))


class LoginCommandMatcher(PythonCommandMatcher):

    def access(self, enactor):
        return enactor.relations.get('account') is None

    def at_cmdmatcher_creation(self):
        self.add(CreateCommand)
        self.add(ConnectCommand)
        self.add(WelcomeScreenCommand)
        self.add(PennConnect)


class SelectCommandMatcher(PythonCommandMatcher):

    def access(self, enactor):
        return enactor.relations.get('account') and not enactor.relations.get('playview')

    def at_cmdmatcher_creation(self):
        self.add(CharSelectCommand)
        self.add(CharCreateCommand)
        self.add(SelectScreenCommand)
        self.add(ThinkCommand)


class ConnectionCommandMatcher(PythonCommandMatcher):

    def at_cmdmatcher_creation(self):
        self.add(PyCommand)
        self.add(ImportCommand)
        self.add(QuitCommand)
        self.add(HelpCommand)
