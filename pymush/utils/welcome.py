from rich.text import Text


logo = AnsiString.from_args("hy", r"""
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
           /__________\/__________\                     """) + AnsiString.from_args("hr", "M U S H") + AnsiString.from_args("hy", """
                      \\/
------------------------------------------------------------------------------\n""")

instructions = AnsiString.from_args("hw", 'connect <username> <password>') + " connects you to an existing Account.\n"
instructions2 = AnsiString.from_args("hw", 'create <username> <password>') + " creates a new Account.\n"
instructions3 = "Enclose multi-word names in quotations. Example: " + AnsiString.from_args("hw", 'connect "<user name>" <password>') + "\n"
instructions4 = AnsiString.from_args("hw", 'QUIT') + " exits the game and disconnects.\n"

last_line = AnsiString.from_args("hy", "------------------------------------------------------------------------------")

message = logo + instructions + instructions2 + instructions3 + instructions4 + last_line

def render_welcome_screen(enactor):

    enactor.msg(message)