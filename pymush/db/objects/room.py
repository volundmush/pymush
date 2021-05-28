from . base import GameObject
from pymush.utils import formatter as fmt
from mudstring.encodings.pennmush import ansi_fun, send_menu
from mudstring.patches.text import MudText
from typing import Optional
from rich.columns import Columns


class RoomExitFormatter(fmt.BaseFormatter):

    def __init__(self, exits):
        super().__init__()
        self.exits = exits

    def text(self, formatter, conn: "Connection", user: Optional["User"] = None,
             character: Optional["GameObject"] = None):
        sections = list()
        for ex in self.exits:
            commands = [(f'goto {ex.name}', 'Head through exit')]
            alias = ex.aliases[0] if ex.aliases else ex.name[:3]
            start = '<' + send_menu(ansi_fun('hx', alias.upper()), commands=commands) + '>'
            start = start.ljust(6)
            if ex.destination and ex.destination[0]:
                destname = ex.destination[0].name
            else:
                destname = 'N/A'
            rest = send_menu(ex.name, commands=commands) + ' to ' + destname
            sections.append(start + rest)

        col = Columns(sections, width=37, equal=True)
        conn.print(col)


class RoomPlayersFormatter(fmt.BaseFormatter):

    def __init__(self, players):
        super().__init__()
        self.players = players

    def text(self, formatter, conn: "Connection", user: Optional["User"] = None,
             character: Optional["GameObject"] = None):
        table = fmt.Table()
        for col in ("Idl", "Name", "Template", "Short-Desc"):
            table.add_column(col)

        for p in self.players:
            table.add_row("NA", p.name, "Not Set", "Dunno Yet")
        table.text(formatter, conn, user, character)


class RoomItemsFormatter(fmt.BaseFormatter):

    def __init__(self, items):
        super().__init__()
        self.items = items

    def text(self, formatter, conn: "Connection", user: Optional["User"] = None,
             character: Optional["GameObject"] = None):
        table = fmt.Table()
        table.add_column("Name")
        table.add_column("Short-Desc")

        for p in self.items:
            table.add_row(p.name, "Dunno Yet")
        table.text(formatter, conn, user, character)


class Room(GameObject):
    type_name = 'ROOM'

    def render_appearance(self, viewer, parser, internal=False):
        out = fmt.FormatList(viewer)

        out.add(fmt.Header(self.name))

        if internal and (idesc := self.attributes.get_value('IDESCRIBE')):
            idesc_eval = parser.evaluate(idesc, executor=self)
            if (idescformat := self.attributes.get_value('IDESCFORMAT')):
                result = parser.evaluate(idescformat, executor=self, number_args={0: idesc_eval})
                out.add(fmt.Line(result))
            else:
                out.add(fmt.Line(idesc_eval))
        elif (desc := self.attributes.get_value('DESCRIBE')):
            desc_eval = parser.evaluate(desc, executor=self)
            if (descformat := self.attributes.get_value('DESCFORMAT')):
                result = parser.evaluate(descformat, executor=self, number_args={0: desc_eval})
                out.add(fmt.Line(result))
            else:
                out.add(fmt.Line(desc_eval))

        if (contents := self.contents.all('')):
            mobiles = [c for c in contents if c.type_name in ('MOBILE', 'PLAYER') and viewer.can_see(c)]
            other = [c for c in contents if c not in mobiles and viewer.can_see(c)]
            if mobiles:
                out.add(fmt.Subheader('Mobiles'))
                out.add(RoomPlayersFormatter(mobiles))
            if other:
                out.add(fmt.Subheader('Items'))
                out.add(RoomItemsFormatter(other))

        if (exits := self.contents.all('exits')):
            exits = [e for e in exits if viewer.can_see(e)]
            if exits:
                out.add(fmt.Subheader('Exits'))
                out.add(RoomExitFormatter(exits))
        out.add(fmt.Footer())
        viewer.send(out)
