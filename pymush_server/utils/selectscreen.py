from . import formatter as fmt
from rich.text import Text


def render_select_screen(enactor):
    acc = enactor.relations.get('account', None)

    out = fmt.FormatList(enactor)
    out.add(fmt.Header(f"Account: {acc.name}"))
    t1 = fmt.Table("Trait", "Value")
    t1.add_row("Email", f"{acc.attributes.get('core', 'email')}")
    t1.add_row('Last Logon', f"{acc.attributes.get('core', 'last')}")
    out.add(t1)
    if (conn := acc.connections.all()) and (conn := [c for c in conn if c.connection]):
        out.add(fmt.Subheader("Connections"))
        t2 = fmt.Table("Id", "Protocol", "Host", "Connected", "Client", "Width")
        for c in conn:
            c2 = c.connection
            t2.add_row(f"{c.name}", f"{c2.protocol}", f"{c2.address}", "", f"{c2.client_name}", f"{c2.width}")
        out.add(t2)
    if (chars := acc.characters.all()):
        out.add(fmt.Subheader("Characters"))
        t3 = fmt.Table("Id", "Name")
        for c in chars:
            t3.add_row(f"{c.objid}", AnsiString.send_menu(c.name, ((f'@ic {c.name}', f"Join the game as {c.name}"), (f"@examine {c.name}", f"@examine {c.name}"))))
        out.add(t3)
    out.add(fmt.Subheader("Commands"))
    t4 = fmt.Table("Command", "Description")
    out.add(t4)
    t4.add_row(AnsiString.from_args("hw", "@charcreate <name>"), "Create a character.")
    t4.add_row(AnsiString.from_args("hw", "@chardelete <name>=<password>"), "Delete a character.")
    t4.add_row(AnsiString.from_args("hw", "@charrename <name>=<newname>"), "Rename a character.")
    t4.add_row(AnsiString.from_args("hw", "@username <new name>"), "Change your username.")
    t4.add_row(AnsiString.from_args("hw", "@email <new email>"), "Change your email.")
    t4.add_row(AnsiString.from_args("hw", "@ic <name>"), "Enter the game as a character.")
    t4.add_row(AnsiString.from_args("hw", "help"), "See more information.")
    t4.add_row(AnsiString.from_args("hw", "QUIT"), "Terminate this connection.")
    t4.add_row(AnsiString.from_args("hw", "@kick <id>"), "Terminates another connection.")
    return enactor.send(out)