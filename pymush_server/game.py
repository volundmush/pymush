from pymush.app import Service


from .engine.cmdqueue import CmdQueue
from collections import OrderedDict
from .db.gameobject import GameSession, GameObject
from .db.attributes import AttributeManager, SysAttributeManager


class GameService(Service):

    def __init__(self):
        self.queue = CmdQueue(self)
        self.next_id: int = 0
        self.objects: OrderedDict[int, GameObject] = OrderedDict()
        self.attributes = AttributeManager(self)
        self.sysattributes = SysAttributeManager(self)
        self.sessions: OrderedDict[int, GameSession] = OrderedDict()