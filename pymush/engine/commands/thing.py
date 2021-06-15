from pymush.utils import formatter as fmt
from .base import (
    MushCommand,
    CommandException,
    PythonCommandMatcher,
    BaseCommandMatcher,
    Command,
)


class LookCommand(MushCommand):
    name = "look"
    aliases = ["l", "lo", "loo"]
    help_category = "Interaction"

    async def execute(self):
        enactor = self.parser.frame.enactor
        if self.args:
            arg = self.args
            if len(arg):
                found, err = await enactor.locate_object(self.entry,
                    arg.plain, first_only=True, multi_match=True
                )
                if found:
                    await self.look_at(found[0])
                else:
                    raise CommandException("I don't see that here.")
            else:
                await self.look_here()
        else:
            await self.look_here()

    async def look_at(self, target):
        enactor = self.parser.frame.enactor
        loc = enactor.location
        if loc:
            if loc == target:
                await target.render_appearance(self.entry, enactor, internal=True)
            else:
                await target.render_appearance(self.entry, enactor)
        else:
            await target.render_appearance(self.entry, enactor)

    async def look_here(self):
        enactor = self.parser.frame.enactor
        loc = enactor.location

        if loc:
            await loc.render_appearance(self.entry, enactor, internal=True)
        else:
            raise CommandException("You are nowhere. There's not much to see.")


class ThinkCommand(MushCommand):
    name = "think"
    aliases = ["th", "thi", "thin"]
    help_category = "Misc"

    async def execute(self):
        self.enactor.msg(await self.parser.evaluate(self.args))


class ThingCommandMatcher(PythonCommandMatcher):
    priority = 10

    def at_cmdmatcher_creation(self):
        self.add(LookCommand)
        self.add(ThinkCommand)


class ExitCommand(Command):
    name = "goto"
    help_category = "Navigation"

    async def execute(self):
        ex = self.match_obj
        des = ex.destination if ex.destination and ex.destination[0] else None
        if not des:
            raise CommandException("Sorry, that's going nowhere fast.")

        out_here = fmt.FormatList(ex)
        out_here.add(
            fmt.Line(f"{self.enactor.name} heads over to {des[0].name}.")
        )

        out_there = fmt.FormatList(ex)
        loc = self.enactor.location

        if not loc:
            out_there.add(
                fmt.Line(f"{self.enactor.name} arrives from somewhere...")
            )
        else:
            out_there.add(
                fmt.Line(f"{self.enactor.name} arrives from {loc[0].name}")
            )
        if des:
            des[0].send(out_there)
        self.enactor.move_to(des[0], inventory=des[1], coordinates=des[2])
        if des:
            await des[0].render_appearance(self.entry, self.enactor, self.parser, internal=True)
        if loc:
            loc[0].send(out_here)


class ThingExitMatcher(BaseCommandMatcher):
    priority = 110

    async def match(self, entry, text):
        ex = entry.executor
        loc = ex.location
        if not loc:
            return

        if text.plain.lower().startswith("goto "):
            text = text[5:]
        elif text.plain.lower().startswith("go "):
            text = text[3:]

        if text:
            exits = loc.namespaces["EXIT"]
            if not exits:
                return
            found, err = await ex.locate_object(entry,
                text,
                general=False,
                dbref=False,
                location=False,
                contents=False,
                candidates=exits,
                use_nicks=False,
                use_aliases=True,
                use_dub=False,
                first_only=True,
                multi_match=False,
            )
            if not found:
                return
            else:
                return ExitCommand(entry, text, found[0])

    async def populate_help(self, enactor, data):
        data["Navigation"].add(ExitCommand)
