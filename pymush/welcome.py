from mudstring.encodings.pennmush import ansi_fun

logo = ansi_fun("", r"""
.______   ____    ____ .___  ___.  __    __       _______. __    __  
|   _  \  \   \  /   / |   \/   | |  |  |  |     /       ||  |  |  | 
|  |_)  |  \   \/   /  |  \  /  | |  |  |  |    |   (----`|  |__|  | 
|   ___/    \_    _/   |  |\/|  | |  |  |  |     \   \    |   __   | 
|  |          |  |     |  |  |  | |  `--'  | .----)   |   |  |  |  | 
| _|          |__|     |__|  |__|  \______/  |_______/    |__|  |__| 
                                                                     
                                                                                                           
                                                                                                           \n""")

instructions = ansi_fun("hw", 'connect <username> <password>') + " connects you to an existing Account.\n"
instructions2 = ansi_fun("hw", 'create <username> <password>') + " creates a new Account.\n"
instructions3 = "Enclose multi-word names in quotations. Example: " + ansi_fun("hw", 'connect "<user name>" <password>') + "\n"
instructions4 = ansi_fun("hw", 'QUIT') + " exits the game and disconnects.\n"

line = ansi_fun("", "------------------------------------------------------------------------------\n")

message = logo + line + instructions + instructions2 + instructions3 + instructions4 + line
