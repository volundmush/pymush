import asyncio
import time
import weakref

from typing import Optional, Iterable, Union
from collections import OrderedDict, defaultdict

from passlib.context import CryptContext

from mudstring.patches.text import OLD_TEXT

from athanor.app import Service
from athanor.utils import import_from_module
from athanor.utils import partial_match

from pymush.db.objects.base import GameObject

from .engine.cmdqueue import CmdQueue
from .utils.misc import callables_from_module


class GameService(Service):

    def __init__(self):
        self.app.game = self
        self.queue = CmdQueue(self)
        self.objects: OrderedDict[int, GameObject] = OrderedDict()
        self.db_objects: weakref.WeakValueDictionary[str, GameObject] = weakref.WeakValueDictionary()
        self.attributes = self.app.classes['game']['attributemanager'](self)
        self.sessions: OrderedDict[int, "GameSession"] = OrderedDict()
        self.in_events: Optional[asyncio.Queue] = None
        self.out_events: Optional[asyncio.Queue] = None
        self.obj_classes = self.app.classes['gameobject']
        self.type_index = defaultdict(weakref.WeakSet)
        self.crypt_con = CryptContext(schemes=['argon2'])
        self.command_matchers = dict()
        self.option_classes = dict()
        self.functions = dict()
        self.update_subscribers = weakref.WeakSet()

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

        for path in self.app.config.gather_modules['optionclasses']:
            self.option_classes.update(callables_from_module(path))

        for path in self.app.config.gather_modules['functions']:
            try:
                funcs = callables_from_module(path)
                results = dict()
                for v in funcs.values():
                    results[v.name] = v
                self.functions.update(results)
            except Exception as err:
                print(f"HAVING TROUBLE LOADING: {v}")
                raise err

    async def async_setup(self):
        pass

    async def async_run(self):
        await self.queue.run()

    def serialize(self) -> dict:
        out = dict()
        out["objects"] = {k: v.serialize() for k, v in self.objects.items()}
        out["attributes"] = self.attributes.serialize()
        return out

    def locate_dbref(self, text):
        if not text.startswith('#'):
            return None, "invalid dbref or objid format! Must start with a #"
        text = text[1:]
        objid_str = None
        if ':' in text:
            dbid_str, objid_str = text.split(':', 1)
        else:
            dbid_str = text

        secs = None
        try:
            dbid = int(dbid_str)
            if objid_str:
                secs = int(objid_str)
        except ValueError as err:
            return None, "Invalid dbref or objid format!"

        if dbid >= 0:
            found = self.objects.get(dbid, None)
            if found:
                if secs is not None:
                    if secs == int(found.created):
                        return found, None
                    else:
                        return None, "Objid not found!"
                else:
                    return found, None
            else:
                return None, "Dbref Not Found!"
        else:
            return None, "Invalid dbref!"

    def create_object(self, type_name: str, name: str, dbid: Optional[int] = None,
                      location: Union[GameObject, str, OLD_TEXT, int] = None, no_location=False,
                      namespace: Optional[GameObject] = None, owner: Optional[GameObject] = None):

        name = name.strip()
        type_name = type_name.upper().strip()
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
            dbid = 0
            while dbid in self.objects:
                dbid += 1

        if namespace:
            namespace = self.resolve_object(namespace)
        if namespace:
            found, err = self.search_objects(name, namespace.namespaces[type_name], exact=True, aliases=True)
            if found:
                return None, f"That name is already in use by another {type_name} managed by {namespace.objid}!"

        obj_class = self.obj_classes.get(type_name, None)
        if not obj_class:
            return None, f"{type_name} does not map to an Object Class!"

        if owner:
            owner = self.resolve_object(owner)

        if owner and obj_class.is_root_owner:
            owner = None
        if not obj_class.is_root_owner:
            if not owner:
                raise ValueError("All non-root_owner objects must have an Owner!")

        if obj_class.unique_names:
            found, err = self.search_objects(name, self.type_index[type_name], exact=True, aliases=True)
            if found:
                return None, f"That name is already in use by another {type_name}!"

        if no_location:
            location = None
        else:
            if location:
                orig = location
                location = self.resolve_object(location)
                if not location:
                    raise ValueError(f"{orig} cannot be resolved to a GameObject for location!")
            else:
                location = self.get_start_location(type_name)

        now = int(time.time())
        obj = obj_class(self, dbid, now, name)
        self.register_obj(obj)

        if namespace:
            obj.namespace = namespace
        if location:
            obj.location = location

        self.objects[dbid] = obj
        return obj, None

    def register_obj(self, obj: GameObject):
        self.objects[obj.dbid] = obj
        self.type_index[obj.type_name].add(obj)
        self.db_objects[obj.dbref] = obj
        self.db_objects[obj.objid] = obj

    def search_objects(self, name, candidates: Optional[Iterable] = None, exact=False, aliases=False):
        if candidates is None:
            candidates = self.objects.values()
        name_lower = name.strip().lower()
        if exact:
            for obj in candidates:
                if name_lower == obj.name.lower():
                    return obj, None
        else:
            if (found := partial_match(name, candidates, key=lambda x: x.name)):
                return found, None
        return None, f"Sorry, nothing matches: {name}"

    def create_or_join_session(self, connection: "Connection", character: "GameObject"):
        if not (sess := self.sessions.get(character.dbid, None)):
            sess = self.app.classes['game']['gamesession'](connection.user, character)
        connection.join_session(sess)

    def update(self, delta: float):
        for obj in self.update_subscribers:
            obj.update(delta)

    def get_start_location(self, type_name: str):
        o = self.app.config.game_options
        type_start = o['type_start'].get(type_name, o.get('default_start', 0))
        return self.resolve_object(type_start)

    def resolve_object(self, check: Union["GameObject", str, OLD_TEXT, int]) -> Optional[GameObject]:
        if isinstance(check, GameObject):
            return check
        elif isinstance(check, int):
            return self.objects.get(check, None)
        elif isinstance(check, str):
            return self.db_objects.get(check, None)
        elif isinstance(check, OLD_TEXT):
            check = check.plain
            return self.db_objects.get(check, None)