import re

from athanor.utils import partial_match

from mudstring.encodings.pennmush import ansi_fun

from . base import Command, MushCommand, CommandException, PythonCommandMatcher
from . shared import PyCommand, HelpCommand, QuitCommand


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
        character, error = self.game.search_tag("penn_character", target, exact=True)
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
    character_type = 'PLAYER'

    def execute(self):
        mdict = self.match_obj.groupdict()
        if not (name := mdict.get("args", None)):
            raise CommandException("Must enter a name for the character!")
        owner = self.interpreter.user
        char, error = self.game.create_object(self.character_type, name, namespace=owner, owner=owner)
        if error:
            raise CommandException(error)
        self.msg(text=ansi_fun("", f"Character '{char.name}' created! Use ") + ansi_fun("hw", f"@ic {char.name}") + " to join the game!")


class CharSelectCommand(Command):
    name = "@ic"
    re_match = re.compile(r"^(?P<cmd>@ic)(?: +(?P<args>.+)?)?", flags=re.IGNORECASE)
    help_category = 'Character Management'
    character_type = 'PLAYER'

    def execute(self):
        mdict = self.match_obj.groupdict()
        acc = self.interpreter.user

        if not (chars := acc.namespaces[self.character_type]):
            raise CommandException("No characters to join the game as!")
        if not (args := mdict.get("args", None)):
            names = ', '.join([obj.name for obj in chars])
            self.msg(text=f"You have the following characters: {names}")
            return
        if not (found := partial_match(args, chars, key=lambda x: x.name)):
            self.msg(text=f"Sorry, no character found named: {args}")
            return
        error = self.entry.game.create_or_join_session(self.entry.connection, found)
        if error:
            raise CommandException(error)


class SelectScreenCommand(Command):
    name = "look"
    re_match = re.compile(r"^(?P<cmd>look)(?: +(?P<args>.+)?)?", flags=re.IGNORECASE)

    def execute(self):
        self.game.selectscreen(self.enactor)


class ThinkCommand(MushCommand):
    name = "think"
    aliases = ['th', 'thi', 'thin']
    help_category = 'System'

    def execute(self):
        if self.args:
            result, remaining, stopped = self.entry.evaluate(self.remaining)
            if result:
                self.msg(text=result)


class LogoutCommand(MushCommand):
    name = '@logout'
    aliases = ['@logo', '@logou']
    help_category = 'System'

    def execute(self):
        self.enactor.logout()
        self.enactor.show_welcome_screen()


class OOCPyCommand(PyCommand):

    @classmethod
    def access(cls, interpreter):
        return interpreter.user.get_alevel() >= 10

    def available_vars(self):
        out = super().available_vars()
        out["user"] = self.entry.user
        return out


class SelectCommandMatcher(PythonCommandMatcher):

    def access(self, enactor):
        return True

    def at_cmdmatcher_creation(self):
        self.add(CharSelectCommand)
        self.add(CharCreateCommand)
        self.add(SelectScreenCommand)
        self.add(ThinkCommand)
        self.add(PennBindCommand)
        self.add(HelpCommand)
        self.add(LogoutCommand)
        self.add(QuitCommand)
        self.add(OOCPyCommand)
