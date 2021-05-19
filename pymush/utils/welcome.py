from mudstring.encodings.pennmush import ansi_fun

logo = ansi_fun("hy", r"""
           ___________/\___________                   
         __\      __  /\  __      /_____________________________________
        |   ______\ \ || / /   /\    ____ ________ _______  ______      |
        |   \ ____|\ \||/ /   /  \   \  | | _  _ | \   ___| \  __ \     |
        |   | |     \ \/ /   / /\ \   | | |/ || \|  | |      | | \ |    |
        |   | |______\  /___/ /__\ \  | |    ||     | |______| |__||    |
       <   <  _______ () ___  ____  > | |    ||     |  ______| |__||>    >
        |   | |      /  \   ||    ||  | |    ||     | |      | |  ||    |
        |   | |_____/ /\ \  ||    ||  | |__  ||     | |___   | |_/ |    |
        |   /______/ /||\ \/_|    |_\ /____\/__\   /______| /_____/     |
        |___      /_/ || \_\       _____________________________________|
           /__________\/__________\                     """) + ansi_fun("hr", "M U S H") + ansi_fun("hy", """
                      \\/
------------------------------------------------------------------------------\n""")

instructions = ansi_fun("hw", 'connect <username> <password>') + " connects you to an existing Account.\n"
instructions2 = ansi_fun("hw", 'create <username> <password>') + " creates a new Account.\n"
instructions3 = "Enclose multi-word names in quotations. Example: " + ansi_fun("hw", 'connect "<user name>" <password>') + "\n"
instructions4 = ansi_fun("hw", 'QUIT') + " exits the game and disconnects.\n"

last_line = ansi_fun("hy", "------------------------------------------------------------------------------")

message = logo + instructions + instructions2 + instructions3 + instructions4 + last_line

def render_welcome_screen(conn):

    conn.msg(message)