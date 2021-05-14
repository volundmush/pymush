from pymush.shared import ConnectionDetails, MudProtocol, ConnectionInMessage, ConnectionInMessageType
from pymush.shared import ConnectionOutMessage, ConnectionOutMessageType
from typing import Optional, Set, List, Dict, Union
#from .db.gameobject import GameObject, GameSession


class Connection:
    def __init__(self, details: ConnectionDetails):
        self.details: ConnectionDetails = details
        self.user: Optional["GameObject"] = None
        self.session: Optional["GameSession"] = None
        self.in_events: List[ConnectionInMessage] = list()
        self.out_events: List[ConnectionOutMessage] = list()