import re

from athanor.utils import partial_match

from mudrich.encodings.pennmush import ansi_fun

from .base import Command, MushCommand, CommandException, PythonCommandMatcher
from .shared import PyCommand, HelpCommand, QuitCommand


class PennBindCommand(MushCommand):
    """
    Binds a character imported from PennMUSH to an Account. This is
    mostly useful for cases where a character never had an Account
    before the game was migrated.

    Usage:
        @pbind <name>=<password>
    """

    name = "@pbind"
    aliases = ["@pbi", "@pbin"]
    help_category = "Character Management"

    async def execute(self):
        target = self.gather_arg()
        password = self.gather_arg()
        if not (target and password):
            raise CommandException("Usage: @pbind <name>=<password>")
        character, error = self.game.search_tag("penn_character", target, exact=True)
        if error:
            raise CommandException("Sorry, that was an incorrect username or password.")
        if not character:
            raise CommandException("Sorry, that was an incorrect username or password.")
        if not (old_hash := character.attributes.get("core", "penn_hash")):
            raise CommandException("Sorry, that was an incorrect username or password.")
        if not check_password(old_hash, password):
            raise CommandException("Sorry, that was an incorrect username or password.")
        if character.relations.get("account", None):
            raise CommandException(
                "Sorry, that character belongs to an account. use pconnect to access them from the connect screen."
            )
        acc = self.enactor.relations.get("account", None)
        acc.characters.add(character)
        character.attributes.delete("core", "penn_hash")
        self.msg(text=f"Character bound to your account!")


class CharCreateCommand(Command):
    name = "@charcreate"
    re_match = re.compile(
        r"^(?P<cmd>@charcreate)(?: +(?P<args>.+)?)?", flags=re.IGNORECASE
    )
    help_category = "Character Management"
    character_type = "PLAYER"

    async def execute(self):
        mdict = self.match_obj.groupdict()
        if not (name := mdict.get("args", None)):
            raise CommandException("Must enter a name for the character!")
        user = self.entry.user
        char, error = await self.game.create_object(self.entry,
            self.character_type, name, namespace=user, owner=user
        )
        if error:
            raise CommandException(error)
        self.msg(
            text=ansi_fun("", f"Character '{char.name}' created! Use ")
            + ansi_fun("hw", f"@ic {char.name}")
            + " to join the game!"
        )


class CharSelectCommand(Command):
    name = "@ic"
    re_match = re.compile(r"^(?P<cmd>@ic)(?: +(?P<args>.+)?)?", flags=re.IGNORECASE)
    help_category = "Character Management"
    character_type = "PLAYER"

    async def execute(self):
        mdict = self.match_obj.groupdict()
        acc = self.entry.user

        if not (chars := acc.namespaces[self.character_type]):
            raise CommandException("No characters to join the game as!")
        if not (args := mdict.get("args", None)):
            names = ", ".join([obj.name for obj in chars])
            self.msg(text=f"You have the following characters: {names}")
            return
        if not (found := partial_match(args, chars, key=lambda x: x.name)):
            self.msg(text=f"Sorry, no character found named: {args}")
            return
        error = await self.entry.game.create_or_join_session(self.entry, found)
        if error:
            raise CommandException(error)


class SelectScreenCommand(Command):
    name = "look"
    re_match = re.compile(r"^(?P<cmd>look)(?: +(?P<args>.+)?)?", flags=re.IGNORECASE)

    async def execute(self):
        await self.executor.show_select_screen(self.executor)


class LogoutCommand(Command):
    name = "look"
    re_match = re.compile(r"^(?P<cmd>@logout)(?: +(?P<args>.+)?)?", flags=re.IGNORECASE)
    help_category = "System"

    async def execute(self):
        await self.executor.logout(self.executor)
        await self.executor.show_welcome_screen(self.executor)


class OOCPyCommand(PyCommand):

    @classmethod
    async def access(cls, entry):
        return entry.user.get_alevel() >= 10

    def available_vars(self):
        out = super().available_vars()
        out["user"] = self.entry.user
        out["connection"] = self.entry
        out["game"] = self.entry.game
        return out


class SelectCommandMatcher(PythonCommandMatcher):
    async def access(self, enactor):
        return True

    def at_cmdmatcher_creation(self):
        self.add(CharSelectCommand)
        self.add(CharCreateCommand)
        self.add(SelectScreenCommand)
        self.add(PennBindCommand)
        self.add(HelpCommand)
        self.add(LogoutCommand)
        self.add(QuitCommand)
        self.add(OOCPyCommand)
