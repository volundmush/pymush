from athanor.app import Service
import asyncio
from typing import Optional, Iterable
from .engine.cmdqueue import CmdQueue
from collections import OrderedDict, defaultdict
from pymush.db.objects.base import GameObject
from .db.attributes import AttributeManager, SysAttributeManager
from passlib.context import CryptContext
from athanor.utils import import_from_module
import time
from .utils.misc import callables_from_module
from athanor.utils import partial_match


class GameService(Service):

    def __init__(self):
        self.app.game = self
        self.queue = CmdQueue(self)
        self.next_id: int = 0
        self.objects: OrderedDict[int, GameObject] = OrderedDict()
        self.attributes = AttributeManager(self)
        self.sysattributes = SysAttributeManager(self)
        self.sessions: OrderedDict[int, "GameSession"] = OrderedDict()
        self.in_events: Optional[asyncio.Queue] = None
        self.out_events: Optional[asyncio.Queue] = None
        self.obj_classes = self.app.classes['gameobject']
        self.type_index = defaultdict(set)
        self.crypt_con = crypt_con = CryptContext(schemes=['argon2'])
        self.command_matchers = dict()
        self.option_classes = dict()

    @property
    def styles(self):
        return self.app.config.styles

    def setup(self):
        super().setup()
        for k, v in self.app.config.command_matchers.items():
            match_list = list()
            for matcher_name, matcher_path in v.items():
                found_class = import_from_module(matcher_path)
                match_list.append(found_class(matcher_name))
            match_list.sort(key=lambda x: getattr(x, 'priority', 0))
            self.command_matchers[k] = match_list

        for path in self.app.config.option_class_modules:
            results = callables_from_module(path)
            if results:
                self.option_classes.update(results)

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
        name = name.strip()
        if not name:
            return None, f"Objects must have a name!"

        if not self.app.config.regex['basic_name'].match(name):
            return None, "Name contains invalid characters!"

        if dbid is not None:
            if dbid < 0:
                return None, "DBID cannot be less than 0!"
            if dbid in self.objects:
                return None, f"DBID {dbid} is already in use!"
        else:
            dbid = self.next_id
            while dbid in self.objects:
                self.next_id += 1
                dbid = self.next_id

        # ignoring specific namespace check for now...

        obj_class = self.obj_classes.get(type_name.upper(), None)
        if not obj_class:
            return None, f"{type_name} does not map to an Object Class!"


        if obj_class.unique_names:
            found, err = self.search_objects(name, self.type_index[obj_class], exact=True, aliases=True)
            if found:
                return None, f"That name is already in use by another {obj_class.type_name}!"

        obj = obj_class(self, dbid, name)
        now = int(time.time())
        obj.created = now
        obj.modified = now
        self.type_index[obj_class].add(obj)

        if namespace:
            obj.set_namespace(namespace)

        self.objects[dbid] = obj
        return obj, None

    def search_objects(self, name, candidates: Optional[Iterable] = None, exact=False, aliases=False):
        if candidates is None:
            candidates = self.objects.values()
        name_lower = name.strip().lower()
        if exact:
            for obj in candidates:
                if name_lower == obj.name.lower():
                    return obj, None
        else:
            if (found := partial_match(name, self.users.values(), key=lambda x: x.name)):
                return found, None
        return None, f"Sorry, nothing matches: {name}"

    def create_or_join_session(self, connection: "Connection", character: "GameObject"):
        if not (sess := self.sessions.get(character.dbid, None)):
            sess = self.app.classes['game']['gamesession'](connection.user, character)
        connection.join_session(sess)
