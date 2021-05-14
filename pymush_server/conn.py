from pymush.shared import ConnectionDetails, MudProtocol
from typing import Optional, Set, List, Dict, Union
from .db.gameobject import GameObject, GameSession


class Connection:
    def __init__(self, details: ConnectionDetails):
        self.details: ConnectionDetails = details
        self.user: Optional[GameObject] = None
        self.session: Optional[GameSession] = None
