import re
import sys
import time
import traceback
from athanor.utils import partial_match
from . base import Command, MushCommand, CommandException, PythonCommandMatcher
from mudstring.encodings.pennmush import ansi_fun
from . shared import PyCommand


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
        self.msg(text=ansi_fun("", f"Character '{char.name}' created! Use ") + ansi_fun("hw", f"charselect {char.name}") + " to join the game!")


class CharSelectCommand(Command):
    name = "@ic"
    re_match = re.compile(r"^(?P<cmd>@ic)(?: +(?P<args>.+)?)?", flags=re.IGNORECASE)
    help_category = 'Character Management'

    def execute(self):
        mdict = self.match_obj.groupdict()
        acc = self.entry.user
        if not (chars := acc.characters):
            raise CommandException("No characters to join the game as!")
        if not (args := mdict.get("args", None)):
            names = ', '.join([obj.name for obj in chars])
            self.msg(text=f"You have the following characters: {names}")
            return
        if not (found := partial_match(args, chars, key=lambda x: x.name)):
            self.msg(text=f"Sorry, no character found named: {args}")
            return
        self.entry.game.create_or_join_session(self.entry.connection, found)


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



class SelectCommandMatcher(PythonCommandMatcher):

    def access(self, enactor):
        return True

    def at_cmdmatcher_creation(self):
        self.add(CharSelectCommand)
        self.add(CharCreateCommand)
        self.add(SelectScreenCommand)
        self.add(ThinkCommand)
        self.add(PennBindCommand)
