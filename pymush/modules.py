from typing import Dict, Union, Optional, List, Tuple, Set
from collections import defaultdict, namedtuple, OrderedDict
import weakref
from pymush.utils import formatter as fmt
import sys
import os
from pathlib import Path
from pymush.models import Module as ModuleModel
from git import Repo
import rapidjson
import uuid
import asyncio


class ModuleManager:

    def __init__(self, game):
        self.game = game
        self.modules = dict()
        self.obj_type_map = game.app.config.classes['objects']
        self.proto_type_map = game.app.config.classes['prototypes']
        self.module_type_map = game.app.config.classes['modules']

    async def load(self):
        cwd = os.getcwd()
        result = await ModuleModel.all()

        for m in result:
            path = os.path.join(cwd, m.name)
            repo = Repo(path)
            if m.type_name:
                if not (module_class := self.module_type_map.get(m.type_name, None)):
                    raise ValueError(f"Module Type-Class '{m.type_name}' not found!")
            else:
                module_class = Module

            module = module_class(self, m.name, path, repo)
            self.modules[m.name] = module
            await module.load_init()

        for m in self.modules.values():
            await m.load_finish()

    async def name_available(self, name: str):
        path = os.path.join(os.getcwd(), name)
        if os.path.exists(path):
            raise ValueError("Path already exists!")
        if await ModuleModel.filter(name=name).first():
            raise ValueError("Module already exists!")
        return path

    async def new_module(self, name: str, path: str, repo: Repo, type_name: str = None):
        if type_name:
            if not (module_class := self.module_type_map.get(type_name, None)):
                raise ValueError(f"Module Type-Class '{type_name}' not found!")
        else:
            module_class = Module
        new_m = module_class(self, name, path, repo)
        self.modules[name] = new_m
        await new_m.load_init()
        await new_m.load_finish()

    async def create(self, user, name: str, type_name: str = None):
        path = await self.name_available(name)
        r = Repo.init(path=path, mkdir=True)
        await self.new_module(name, path, r, type_name=type_name)

    async def clone(self, user, name: str, url: str, api, type_name: str = None):
        path = await self.name_available(name)
        r = Repo.clone_from(url=url, to_path=path)
        await self.new_module(name, path, r, type_name=type_name)

    def get_entry(self, module: str, key: str, attr: str, entry_name: str = "Entry"):
        if not (m := self.modules.get(module, None)):
            raise ValueError(f"Module '{module}' not found.")
        if not (a := m.entries.get(attr, None)):
            raise ValueError(f"Module '{module}' does not have entries: {attr}")
        if not (found := a.get(key, None)):
            raise ValueError(f"{entry_name} '{key}' not found in Module '{module}'")
        return found

    def locate_prototype(self, prototype: Union[str, List[str], "Prototype"]):
        if isinstance(prototype, Prototype):
            return prototype

        if not prototype:
            raise ValueError(f"Prototype cannot be empty!")

        if isinstance(prototype, str):
            if '/' not in prototype:
                raise ValueError(f"Prototypes must be addresses as <module>/<key>")
            p_module_name, p_key = prototype.split('/', 1)
            prototype = [p_module_name.name.strip(), p_key.strip()]

        if isinstance(prototype, list):
            if not len(prototype) >= 2:
                raise ValueError(f"Malformed Prototype path: {prototype}")
            if not (p_module := self.modules.get(prototype[0], None)):
                raise ValueError(f"Module '{prototype[0]}' not found.")
            if not (prototype := p_module.entries['prototypes'].get(prototype[1], None)):
                raise ValueError(f"Prototype '{prototype[1]}' not found in Module {p_module}")

        return prototype

    def locate_module(self, module: Union[str, "Module"]):
        if isinstance(module, Module):
            return module

        if not module:
            raise ValueError(f"Module cannot be empty!")

        if isinstance(module, str):
            orig_module = module
            if not (module := self.modules.get(module, None)):
                raise ValueError(f"Module '{orig_module}' not found.")

        return module

    async def spawn_object(self, module: Union[str, "Module"], prototype: Union[str, List[str], "Prototype"],
                           key: Optional[str] = None, **kwargs):

        module = self.locate_module(module)
        prototype = self.locate_prototype(prototype)

        if key:
            if module.locate_object(key):
                raise ValueError(f"Key '{module.name}/{key}' is already in use.")
        else:
            key = prototype.generate_key(module)

        obj_class = prototype.obj_class
        obj_class.validate_data(kwargs)


class Module:

    def __init__(self, manager: ModuleManager, name: str, path: str, repo: Repo):
        self.manager = manager
        self.name = name
        self.path = path
        self.repo = repo
        self.entries = defaultdict(dict)

    @property
    def game(self):
        return self.manager.game

    def locate_object(self, key: str):
        return self.entries['objects_spawned'].get(key, self.entries['objects'].get(key, None))

    async def load_init(self):
        await self.load_init_rooms()
        await self.load_init_prototypes()
        await self.load_init_objects()

    def ext_files(self, folder_name: str, ext: str = "json"):
        folder = Path(self.path) / "prototypes"
        if not folder.exists():
            return []
        return folder.glob(f"*.{ext}")

    async def load_init_rooms(self):
        for fname in self.ext_files("rooms"):
            key, ext = fname.name.split('.', 1)
            data = rapidjson.load(fname.absolute())

    async def load_init_prototypes(self):
        for fname in self.ext_files("prototypes"):
            key, ext = fname.name.split('.', 1)
            data = rapidjson.load(fname.absolute())
            if not (type_name := data.get('type_name', None)):
                raise ValueError(f"Prototype '{fname.absolute()}' must have a type_name!")
            if not (proto_class := self.manager.proto_type_map.get(type_name, None)):
                raise ValueError(f"Prototype Type-Class '{type_name}' not found!")
            proto_class.validate_data(data)
            new_proto = proto_class(self, key)
            self.entries['prototypes'][key] = new_proto
            await new_proto.load_init(data)

    async def load_init_objects(self):
        for fname in self.ext_files("objects"):
            key, ext = fname.name.split('.', 1)
            data = rapidjson.load(fname.absolute())

            if not (prototype := data.get("prototype", None)):
                raise ValueError(f"Error retrieving Prototype name from {fname.absolute()}")
            if isinstance(prototype, str):
                if '/' not in prototype:
                    prototype = f"{self.name}/{prototype}"
            prototype = self.manager.locate_prototype(prototype)

            obj_class = prototype.obj_class

            obj_class.validate_data(data)

            new_obj = obj_class(prototype, key)
            self.entries['objects'][key] = new_obj
            await new_obj.load_init(data)

    async def load_finish(self):
        await self.load_finish_prototypes()
        await self.load_finish_objects()

    async def load_finish_prototypes(self):
        for p in self.entries['prototypes'].values():
            await p.load_finish()

    async def load_finish_objects(self):
        for p in self.entries['objects'].values():
            await p.load_finish()


class Prototype:
    type_name = None

    def __init__(self, module: Module, key: str):
        self.module = module
        self.key = key
        self.objects = weakref.WeakSet()
        self.created: float = 0.0
        self.modified: float = 0.0
        self._data = None

    async def load_init(self, data):
        self._data = data

    async def load_finish(self):
        pass

    @property
    def obj_class(self):
        if not (o_class := self.module.manager.obj_type_map.get(self.type_name, None)):
            raise ValueError(f"GameObject Type-Class '{self.type_name}' not found!")
        return o_class

    def generate_key(self, module):
        key = str(uuid.uuid4())
        while module.locate_object(key):
            key = str(uuid.uuid4())
        return key

    @classmethod
    def validate_data(cls, data):
        pass


class RoomTemplate:

    def __init__(self, module, key):
        self.module = module
        self.key = key
        self._data = None

    async def load_init(self, data):
        self._data = data

    async def load_finish(self):
        pass


class ExitManager:

    def __init__(self, room):
        self.room = room


class Room:

    def __init__(self, manager, coordinates: Tuple[int, ...]):
        self.manager = manager
        self.coordinates = coordinates
        self.template = None
        self.exits = ExitManager(self)
        self._data = None

    @property
    def module(self):
        return self.manager.obj.module

    def contents(self):
        return self.manager.grid_reverse.get(self.coordinates, set())


class ContentsManager:

    def __init__(self, obj):
        self.obj = obj
        self.rooms: Dict[Tuple[int, ...], Room] = dict()
        self.grid_contents: Dict["GameObject", Tuple[int, ...]] = weakref.WeakKeyDictionary()
        self.grid_reverse: Dict[Tuple[int, ...], Set["GameObject"]] = defaultdict(weakref.WeakSet)
        self.space_contents: Dict["GameObject", Tuple[float, ...]] = weakref.WeakKeyDictionary()
        self.space_reverse: Dict[Tuple[float, ...], Set["GameObject"]] = defaultdict(weakref.WeakSet)

    def coordinates_of(self, gameobject):
        if (coordinates := self.grid_contents.get(gameobject, self.space_contents.get(gameobject, None))):
            return (self.obj.module.name, self.obj.key, *coordinates)
        return None

    def __contains__(self, item):
        return item in self.grid_contents or item in self.space_contents


class BasicQueue:

    def __init__(self, obj):
        self.obj = obj
        self.next_id = 0
        self.pending_queue = OrderedDict()
        self.queue = asyncio.PriorityQueue()
        self._task = None
        self.running = False

    def start(self):
        if not self.running:
            self.running = True
            self._task = asyncio.create_task(self.run())

    async def run(self):
        while (msg := await self.queue.get()):
            priority, pid = msg
            if (found := self.pending_queue.get(pid, None)):
                await self.execute_item(found)
        self._task = None

    async def execute_item(self, found):
        pass

    def stop(self):
        if self.running:
            self.queue.put_nowait((sys.maxsize, None))
            self.running = False


class ActionQueue(BasicQueue):
    pass


class CommandQueue(BasicQueue):
    pass


class GameObject:
    type_name = None

    def __init__(self, module: Module, prototype: Prototype, key: str):
        self.key = key
        self.module = module
        self.prototype = prototype
        self._data = None

        # Some objects can have sessions attached.
        self.session: Optional["GameSession"] = None
        self.cpu_quota: float = 0.0

        self.created: float = 0.0
        self.modified: float = 0.0

        self.contents = ContentsManager(self)

        self.holder: Optional["GameObject"] = None

        self.saved_locations: Dict[str, Tuple[str, str, Union[Tuple[int, ...], Tuple[float, ...]]]] = dict()

        self.action_queue = ActionQueue(self)
        self.cmd_queue = CommandQueue(self)

    def serialize_location(self):
        if not self.holder:
            return None
        return self.holder.contents.coordinates_of(self)

    @property
    def room(self):
        if not self.holder:
            return None
        if not (loc := self.holder.contents.grid_contents.get(self, None)):
            return None
        return self.holder.contents.rooms.get(loc, None)

    @property
    def game(self):
        return self.module.game

    def listeners(self):
        if self.session:
            return [self.session]
        return []

    def msg(self, text, **kwargs):
        flist = fmt.FormatList(self, **kwargs)
        flist.add(fmt.Line(text))
        self.send(flist)

    def send(self, message: fmt.FormatList):
        self.receive_msg(message)
        for listener in self.listeners():
            if listener not in message.relay_chain:
                listener.send(message.relay(self))

    def receive_msg(self, message: fmt.FormatList):
        pass

    async def load_init(self, data):
        self._data = data

    async def load_finish(self):
        self.prototype.objects.add(self)

    @classmethod
    def validate_data(cls, data):
        pass

    def can_perceive(self, target: "GameObject"):
        return True

    def can_interact_with(self, target: "GameObject"):
        return True

