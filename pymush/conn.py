from pymush.shared import ConnectionDetails, MudProtocol, ConnectionInMessage, ConnectionInMessageType
from pymush.shared import ConnectionOutMessage, ConnectionOutMessageType
from typing import Optional, Set, List, Dict, Union


class Connection:
    def __init__(self, game: "GameService", details: ConnectionDetails):
        self.game = game
        self.details: ConnectionDetails = details
        self.user: Optional["GameObject"] = None
        self.session: Optional["GameSession"] = None
        self.in_events: List[ConnectionInMessage] = list()
        self.out_events: List[ConnectionOutMessage] = list()

    def update(self, details: ConnectionDetails):
        self.details = details

    def process_event(self, ev: ConnectionInMessage):
        print(f"{self} received message: {ev}")
        pass

