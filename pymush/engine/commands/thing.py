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

    def execute(self):
        enactor = self.parser.frame.enactor
        if self.args:
            arg = self.gather_arg()
            if len(arg):
                found, err = enactor.locate_object(
                    arg.plain, first_only=True, multi_match=True
                )
                if found:
                    self.look_at(found[0])
                else:
                    raise CommandException("I don't see that here.")
            else:
                self.look_here()
        else:
            self.look_here()

    def look_at(self, target):
        enactor = self.parser.frame.enactor
        loc = enactor.location
        if loc:
            if loc == target:
                target.render_appearance(self.interpreter, enactor, internal=True)
            else:
                target.render_appearance(self.interpreter, enactor)
        else:
            target.render_appearance(self.interpreter, enactor)

    def look_here(self):
        enactor = self.parser.frame.enactor
        loc = enactor.location

        if loc:
            loc.render_appearance(self.interpreter, enactor, internal=True)
        else:
            raise CommandException("You are nowhere. There's not much to see.")


class ThinkCommand(MushCommand):
    name = "think"
    aliases = ["th", "thi", "thin"]
    help_category = "Misc"

    def execute(self):
        self.enactor.msg(self.parser.evaluate(self.args))


class ThingCommandMatcher(PythonCommandMatcher):
    priority = 10

    def at_cmdmatcher_creation(self):
        self.add(LookCommand)
        self.add(ThinkCommand)


class ExitCommand(Command):
    name = "goto"
    help_category = "Navigation"

    def execute(self):
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
            des[0].render_appearance(self.enactor, self.parser, internal=True)
        if loc:
            loc[0].send(out_here)


class ThingExitMatcher(BaseCommandMatcher):
    priority = 110

    def match(self, interpreter, text):
        loc = interpreter.enactor.location
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
            found, err = interpreter.enactor.locate_object(
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
                return ExitCommand(interpreter, text, found[0])

    def populate_help(self, enactor, data):
        data["Navigation"].add(ExitCommand)
