from athanor.app import Service
import asyncio
from typing import Optional, Union, Dict, Set, List
from .engine.cmdqueue import CmdQueue
from collections import OrderedDict
from .db.gameobject import GameSession, GameObject
from .db.attributes import AttributeManager, SysAttributeManager
from .db.user import UserManager
import time


class GameService(Service):

    def __init__(self):
        self.app.game = self
        self.queue = CmdQueue(self)
        self.next_id: int = 0
        self.objects: OrderedDict[int, GameObject] = OrderedDict()
        self.attributes = AttributeManager(self)
        self.sysattributes = SysAttributeManager(self)
        self.sessions: OrderedDict[int, GameSession] = OrderedDict()
        self.in_events: Optional[asyncio.Queue] = None
        self.out_events: Optional[asyncio.Queue] = None
        self.obj_classes = self.app.classes['gameobject']
        self.users = UserManager(self)

    async def async_setup(self):
        pass

    async def async_run(self):
        await self.queue.run()

    def serialize(self) -> dict:
        out = dict()
        out["next_id"] = self.next_id
        out["objects"] = {k: v.serialize() for k, v in self.objects.items()}
        out["attributes"] = self.attributes.serialize()
        out["sysattributes"] = self.attributes.serialize()
        return out

    def create_object(self, type_name: str, name: str, dbid: Optional[int] = None, namespace: Optional[GameObject] = None):
        if dbid is not None:
            if dbid < 0:
                raise ValueError("DBID cannot be less than 0!")
            if dbid in self.objects:
                raise ValueError(f"DBID {dbid} is already in use!")
        else:
            dbid = self.next_id
            while dbid in self.objects:
                self.next_id += 1
                dbid = self.next_id

        # ignoring namespace check for now...

        obj_class = self.obj_classes.get(type_name.upper(), None)
        if not obj_class:
            raise ValueError(f"{type_name} does not map to an Object Class!")

        if not name:
            raise ValueError("Objects must have a name!")

        obj = obj_class(self, dbid, name)
        now = int(time.time())
        obj.created = now
        obj.modified = now
        if namespace:
            obj.set_namespace(namespace)
        self.objects[dbid] = obj
        return obj
