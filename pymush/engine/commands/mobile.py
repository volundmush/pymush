from . base import MushCommand, CommandException, PythonCommandMatcher, BaseCommandMatcher, Command
from pymush.utils import formatter as fmt


class LookCommand(MushCommand):
    name = 'look'
    aliases = ['l', 'lo', 'loo']
    help_category = 'Interaction'

    def execute(self):
        if self.args:
            arg = self.gather_arg()
            if len(arg):
                found, err = self.entry.enactor.locate_object(arg.plain, first_only=True, multi_match=True)
                if found:
                    self.look_at(found[0])
                else:
                    raise CommandException("I don't see that here.")
            else:
                self.look_here()
        else:
            self.look_here()

    def look_at(self, target):
        loc = self.entry.enactor.location[0] if self.entry.enactor.location else None
        if loc:
            if loc == target:
                target.render_appearance(self.entry.enactor, self.entry.parser, internal=True)
            else:
                target.render_appearance(self.entry.enactor, self.entry.parser)
        else:
            target.render_appearance(self.entry.enactor, self.entry.parser)

    def look_here(self):
        loc = self.entry.enactor.location[0] if self.entry.enactor.location else None
        if loc:
            loc.render_appearance(self.entry.enactor, self.entry.parser, internal=True)
        else:
            raise CommandException("You are nowhere. There's not much to see.")


class ThinkCommand(MushCommand):
    name = "think"
    aliases = ['th', 'thi', 'thin']
    help_category = 'Misc'

    def execute(self):
        self.entry.enactor.msg(self.parser.evaluate(self.args))


class MobileCommandMatcher(PythonCommandMatcher):
    priority = 10

    def at_cmdmatcher_creation(self):
        self.add(LookCommand)
        self.add(ThinkCommand)


class ExitCommand(Command):
    name = 'goto'
    help_category = 'Navigation'

    def execute(self):
        ex = self.match_obj
        des = ex.destination if ex.destination and ex.destination[0] else None
        if not des:
            raise CommandException("Sorry, that's going nowhere fast.")

        out_here = fmt.FormatList(ex)
        out_here.add(fmt.Line(f"{self.entry.enactor.name} heads over to {des[0].name}."))

        out_there = fmt.FormatList(ex)
        loc = self.entry.enactor.location if self.entry.enactor.location and self.entry.enactor.location[0] else None

        if not loc:
            out_there.add(fmt.Line(f"{self.entry.enactor.name} arrives from somewhere..."))
        else:
            out_there.add(fmt.Line(f"{self.entry.enactor.name} arrives from {loc[0].name}"))
        if des:
            des[0].send(out_there)
        self.entry.enactor.move_to(des[0], inventory=des[1], coordinates=des[2])
        if des:
            des[0].render_appearance(self.entry.enactor, self.parser, internal=True)
        if loc:
            loc[0].send(out_here)


class MobileExitMatcher(BaseCommandMatcher):
    priority = 110

    def match(self, entry, text):
        loc = entry.enactor.location[0] if entry.enactor.location else None
        if not loc:
            return

        if text.lower().startswith('goto '):
            text = text[5:]
        elif text.lower().startswith('go '):
            text = text[3:]

        if text:
            exits = loc.contents.all('exits')
            if not exits:
                return
            found, err = entry.enactor.locate_object(text, general=False, dbref=False, location=False, contents=False,
                                                     candidates=exits, use_nicks=False,
                                                     use_aliases=True, use_dub=False, first_only=True, multi_match=False)
            if not found:
                return
            else:
                return ExitCommand(entry, found[0])

    def populate_help(self, enactor, data):
        data['Navigation'].add(ExitCommand)
