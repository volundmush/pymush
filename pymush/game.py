from athanor.app import Service
import asyncio
from typing import Optional, Union, Dict, Set, List
from .engine.cmdqueue import CmdQueue
from collections import OrderedDict
from .db.gameobject import GameSession, GameObject
from .db.attributes import AttributeManager, SysAttributeManager
from athanor.shared import ConnectionDetails
from athanor.shared import ConnectionInMessageType, ConnectionOutMessage, ConnectionInMessage, ConnectionOutMessageType
from athanor.shared import PortalOutMessageType, PortalOutMessage, ServerInMessageType, ServerInMessage
from .conn import Connection


class GameService(Service):

    def __init__(self):
        self.app.game = self
        self.queue = CmdQueue(self)
        self.next_id: int = 0
        self.objects: OrderedDict[int, GameObject] = OrderedDict()
        self.attributes = AttributeManager(self)
        self.sysattributes = SysAttributeManager(self)
        self.connections: Dict[str, Connection] = dict()
        self.sessions: OrderedDict[int, GameSession] = OrderedDict()
        self.in_events: Optional[asyncio.Queue] = None
        self.out_events: Optional[asyncio.Queue] = None
