import asyncio
import time
import weakref
from uuid import UUID
from typing import Optional, Iterable, Union, Dict
from collections import OrderedDict, defaultdict
from enum import IntEnum

from passlib.context import CryptContext

from mudrich.text import Text

from athanor.app import Service
from athanor.utils import import_from_module
from athanor.utils import partial_match

from .utils.misc import callables_from_module
from .db.base import GameObjectKey, QueryResult
from .db.exceptions import DatabaseUnavailable
from .objects.base import GameObject


class GameStates(IntEnum):
    LOAD = 0
    UNLOAD = 1


class GameService(Service):
    states = GameStates

    def __init__(self, app):
        super().__init__(app)
        app.game = self
        self.sessions: OrderedDict[int, "GameSession"] = OrderedDict()
        self.in_events: Optional[asyncio.Queue] = None
        self.out_events: Optional[asyncio.Queue] = None
        self.users: Dict[UUID, dict] = dict()
        self.objects: Dict[UUID, dict] = dict()
        self.crypt_con = CryptContext(schemes=["argon2"])
        self.command_matchers = dict()
        self.option_classes = dict()
        self.functions = dict()
        self.update_subscribers = weakref.WeakSet()
        self.options = app.config.game_options
        self.queue = None
        self.loaded = False

    @property
    def db(self):
        return self.app.db

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
            match_list.sort(key=lambda x: getattr(x, "priority", 0))
            self.command_matchers[k] = match_list

        for path in self.app.config.gather_modules["optionclasses"]:
            self.option_classes.update(callables_from_module(path))

        for path in self.app.config.gather_modules["functions"]:
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
        self.queue = asyncio.Queue()

    async def async_run(self):
        while (state := await self.queue.get()):
            if state == self.states.LOAD and not self.loaded:
                try:
                    await self.load_game()
                    self.loaded = True
                except Exception as e:
                    print(f"FAILED TO LOAD GAME!")
                    import traceback, sys
                    traceback.print_exc(file=sys.stdout)
            elif state == self.states.UNLOAD and self.loaded:
                self.loaded = False
                await self.unload_game()

    async def create_object(self, type_name: str, name: Text, register: bool = True, **kwargs) -> QueryResult:
        result = await self.db.create_object(type_name, name, **kwargs)
        if result.error:
            return result
        if register:
            await self.register_object(result.data)
        return result

    async def register_object(self, key: GameObjectKey):
        obj_class = self.app.classes['game']['gameobject']
        obj = obj_class(self, key)
        self.objects[key.uuid] = obj
        obj.start()

    async def load_game(self):
        try:
            obj_class = self.app.classes['game']['gameobject']
            results = await self.db.list_objects()
            if results.data:
                for key in results.data:
                    self.objects[key.uuid] = obj_class(self, key)
                for obj in self.objects.values():
                    obj.start()
        except Exception as e:
            for obj in self.objects.values():
                obj.stop()
            self.objects.clear()
            raise e

    async def unload_game(self):
        for obj in self.objects.values():
            obj.stop()
        self.objects.clear()

    def locate_dbref(self, text):
        if not text.startswith("#"):
            return None, "invalid dbref or objid format! Must start with a #"
        text = text[1:]
        objid_str = None
        if ":" in text:
            dbid_str, objid_str = text.split(":", 1)
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

    async def find_user(self, name: Union[str, Text]):
        if isinstance(name, Text):
            name = name.plain
        results = await self.db.list_users(name=name)
        if not results.data:
            return None
        results = await self.db.get_user(results.data[0])
        return results.data

    async def search_objects(
        self, name: Union[str, Text], candidates: Optional[Iterable[GameObjectKey]] = None, exact=False, aliases=True
    ):
        if isinstance(name, Text):
            name = name.plain

        if candidates is None:
            candidates = [obj.key for obj in self.objects.values()]

        search_candidates = list()
        for can in candidates:
            results = await self.db.get_object(can)
            if results.data:
                search_candidates.append((can, results.data))

        name_lower = name.strip().lower()
        if exact:
            for obj in search_candidates:
                if name_lower == obj[1]['name'].lower():
                    return obj, None
        else:
            if (found := partial_match(name, search_candidates, key=lambda x: x[1]['name'])) :
                return found, None
        return None, f"Sorry, nothing matches: {name}"

    async def create_or_join_session(
        self, connection: "Connection", character: "GameObject"
    ):
        if not (sess := self.sessions.get(character.dbid, None)):
            if len(connection.user.account_sessions) > connection.user.max_sessions():
                return "Too many Sessions already in play for this User Account!"
            sess = self.app.classes["game"]["gamesession"](connection.user, character)
            self.sessions[character.dbid] = sess
            connection.user.account_sessions.add(sess)
            sess.start()
        await connection.join_session(sess)

    def update(self, now: float, delta: float):
        for obj in self.update_subscribers:
            obj.update(now, delta)

    def get_start_location(self, type_name: str):
        o = self.app.config.game_options
        type_start = o["type_start"].get(type_name, o.get("default_start", 0))
        return self.resolve_object(type_start)

    def resolve_object(
        self, check: Union["GameObject", str, Text, int]
    ) -> Optional[GameObject]:
        if isinstance(check, GameObject):
            return check
        elif isinstance(check, int):
            return self.objects.get(check, None)
        elif isinstance(check, str):
            return self.db_objects.get(check, None)
        elif isinstance(check, Text):
            check = check.plain
            return self.db_objects.get(check, None)

    def alevel_of(self, type_name: str):
        if type_name in self.app.config.game_options["type_alevel"]:
            return self.app.config.game_options["type_alevel"][type_name]
        return self.app.config.game_options["default_alevel"]
