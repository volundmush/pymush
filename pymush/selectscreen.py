from mudstring.encodings.pennmush import ansi_fun, send_menu, ansify, ansi_fun_style
from .utils import formatter as fmt


def render_select_screen(connection):
    acc = connection.user

    out = fmt.FormatList(acc)
    out.add(fmt.Header(f"Account: {acc.name}"))
    t1 = fmt.Table()
    t1.add_column("Trait")
    t1.add_column("Value")
    t1.add_row("Email", f"{acc.email}")
    t1.add_row('Last Login', f"{acc.last_login}")
    out.add(t1)

    if acc.connections:
        out.add(fmt.Subheader("Connections"))
        t2 = fmt.Table()
        for t in ("Id", "Protocol", "Host", "Connected", "Client", "Width"):
            t2.add_column(t)
        for c in acc.connections:
            t2.add_row(f"{c.client_id}", f"{str(c.details.protocol)}", f"{c.details.host_address}", "", f"{c.details.client_name}", f"{c.details.width}")
        out.add(t2)

    if (chars := acc._owner_of_type['PLAYER']):
        out.add(fmt.Subheader("Characters"))
        t3 = fmt.Table()
        t3.add_column("Id")
        t3.add_column("Name")
        for objid, c in chars.items():
            t3.add_row(f"{objid}", send_menu(c.name, ((f'@ic {c.name}', f"Join the game as {c.name}"), (f"@examine {c.name}", f"@examine {c.name}"))))
        out.add(t3)

    out.add(fmt.Subheader("Commands"))

    cmd_style = ansi_fun_style('hw')

    t4 = fmt.Table()
    t4.add_column("Command")
    t4.add_column("Description")
    t4.add_row(ansify(cmd_style, "@charcreate <name>"), "Create a character.")
    t4.add_row(ansify(cmd_style, "@chardelete <name>=<password>"), "Delete a character.")
    t4.add_row(ansify(cmd_style, "@charrename <name>=<newname>"), "Rename a character.")
    t4.add_row(ansify(cmd_style, "@username <new name>"), "Change your username.")
    t4.add_row(ansify(cmd_style, "@email <new email>"), "Change your email.")
    t4.add_row(ansify(cmd_style, "@ic <name>"), "Enter the game as a character.")
    t4.add_row(ansify(cmd_style, "help"), "See more information.")
    t4.add_row(ansify(cmd_style, "QUIT"), "Terminate this connection.")
    t4.add_row(ansify(cmd_style, "@kick <id>"), "Terminates another connection.")

    out.add(t4)
    return out