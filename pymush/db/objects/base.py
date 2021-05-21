import sys
from typing import Union, Set, Optional, List, Dict, Tuple, Iterable
from athanor.utils import lazy_property
from pymush.db.attributes import AttributeHandler
from athanor.shared import ConnectionOutMessage, ConnectionOutMessageType, ConnectionInMessageType, ConnectionInMessage
from pymush.utils import formatter as fmt
from pymush.utils.styling import StyleHandler
from collections import defaultdict


class NameSpace:

    def __init__(self, owner: "GameObject", name: str):
        self.owner = owner
        self.name = name
        self.objects: Dict[str, "GameObject"] = dict()

    def serialize(self) -> Dict:
        return dict()


class Inventory:

    def __init__(self):
        self.coordinates = defaultdict(set)
        self.reverse = dict()

    def add(self, obj: "GameObject", coordinates=None):
        if obj in self.reverse:
            old_coor = self.reverse[obj]
            self.coordinates[old_coor].remove(obj)
            if not len(self.coordinates):
                del self.coordinates[old_coor]
        self.coordinates[coordinates].add(obj)
        self.reverse[obj] = coordinates

    def remove(self, obj: "GameObject"):
        if obj in self.reverse:
            old_coor = self.reverse[obj]
            self.coordinates[old_coor].remove(obj)
            if not len(self.coordinates):
                del self.coordinates[old_coor]
            del self.reverse[obj]

    def all(self):
        return self.reverse.keys()


class ContentsHandler:
    def __init__(self, owner):
        self.owner = owner
        self.inventories = defaultdict(Inventory)
        self.reverse = dict()

    def add(self, name: str, obj: "GameObject", coordinates=None):
        destination = self.inventories[name]
        if obj in self.reverse:
            rev = self.reverse[obj]
            if rev == destination:
                rev.add(obj, coordinates)
            else:
                self.reverse[obj].remove(obj)
                destination.add(obj, coordinates)
                self.reverse[obj] = destination
        else:
            destination.add(obj, coordinates)
            self.reverse[obj] = destination
        obj.location = (self.owner, name, coordinates)

    def remove(self, obj: "GameObject"):
        if obj in self.reverse:
            rev = self.reverse[obj]
            rev.remove(obj)
            del self.reverse[obj]
            obj.location = None

    def all(self, name=None):
        if name:
            return self.inventories[name].all()
        return self.reverse.keys()


class GameObject:
    type_name = None
    unique_names = False

    __slots__ = ["service", "dbid", "dbref", "name", "parent", "parent_of", "home", "home_of", "db_quota", "cpu_quota",
                 "zone", "zone_of", "owner", "owner_of", "namespaces", "namespace", "session", "connections",
                 "admin_level", "attributes", "sys_attributes", "location", "contents", "aliases", "created",
                 "modified", "style_holder", "account_sessions"]

    def __init__(self, service: "GameService", dbref: int, name: str):
        self.service = service
        self.dbid = dbref
        self.dbref = f"#{dbref}"
        self.created: int = 0
        self.modified: int = 0
        self.name = sys.intern(name)
        self.aliases: List[str] = list()
        self.owner: Optional["GameObject"] = None
        self.parent: Optional[GameObject] = None
        self.parent_of: Set[GameObject] = set()
        self.home: Optional[GameObject] = None
        self.home_of: Set[GameObject] = set()
        self.zone: Optional[GameObject] = None
        self.zone_of: Set[GameObject] = set()
        self.owner: Optional[GameObject] = None
        self.owner_of: Set[GameObject] = set()
        self.namespaces: Dict[str, NameSpace] = dict()
        self.namespace: Optional[Tuple[GameObject, str]] = None
        self.session: Optional["GameSession"] = None
        self.account_sessions: Set["GameSession"] = set()
        self.connections: Set["Connection"] = set()
        self.attributes = AttributeHandler(self, self.service.attributes)
        self.sys_attributes = dict()
        self.location: Optional[Tuple[GameObject, str, Optional[Union[Tuple[int, ...], Tuple[float, ...]]]]] = None
        self.contents: ContentsHandler = ContentsHandler(self)
        self.db_quota: int = 0
        self.cpu_quota: float = 0.0
        self.admin_level: int = 0
        self.style_holder: Optional[StyleHandler] = None

    def __hash__(self):
        return hash(self.dbid)

    @property
    def style(self):
        if self.session:
            return self.session.style
        if not self.style_holder:
            self.style_holder = StyleHandler(self, save=True)
        return self.style_holder

    @property
    def game(self):
        return self.service

    def __int__(self):
        return self.dbid

    def __repr__(self):
        return f"<{self.__class__.__name__} {self.dbid}: {self.name}>"

    def serialize(self) -> Dict:
        out: Dict = {
            "dbid": self.dbid,
            "name": self.name
        }
        if self.parent:
            out["parent"] = self.parent.dbid

        if self.namespaces:
            n_dict = dict()
            for k, n in self.namespaces.items():
                n_dict[k] = n.serialize()
            out["namespaces"] = n_dict

        if self.namespace:
            out["namespace"] = [self.namespace[0].dbid, self.namespace[1]]

        if self.attributes.count():
            out["attributes"] = self.attributes.serialize()

        if self.sys_attributes:
            out["sys_attributes"] = self.sys_attributes

        if self.location:
            out["location"] = (self.location[0].dbid, self.location[1], self.location[2])

        return out

    def listeners(self):
        if self.session:
            return [self.session]
        return []

    def parser(self):
        return Parser(self.core, self.objid, self.objid, self.objid)

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

    def get_alevel(self, ignore_quell=False):
        if self.session:
            return self.session.get_alevel(ignore_quell=ignore_quell)

        if self.owner:
            return self.owner.admin_level
        else:
            return self.admin_level