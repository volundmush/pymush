import sys
from typing import Union, Set, Optional, List, Dict, Tuple
from athanor.utils import lazy_property
from ..conn import Connection
from .attributes import AttributeHandler
from athanor.shared import ConnectionOutMessage, ConnectionOutMessageType, ConnectionInMessageType, ConnectionInMessage


class GameSession:

    def __init__(self, sid: int, user: "User", character: "GameObject"):
        self.sid: int = sid
        self.user: "User" = user
        self.character: "GameObject" = character
        self.puppet: "GameObject" = character
        self.connections: Set[Connection] = set()
        self.in_events: List[ConnectionInMessage] = list()
        self.out_events: List[ConnectionOutMessage] = list()


class NameSpace:

    def __init__(self, owner: "GameObject", name: str):
        self.owner = owner
        self.name = name
        self.objects: Dict[str, "GameObject"] = dict()

    def serialize(self) -> Dict:
        return dict()


class Inventory:
    pass


class GameObject:
    type_name = None
    type_ancestor: Optional["GameObject"] = None

    __slots__ = ["service", "dbid", "dbref", "name", "parent", "parent_of", "home", "home_of", "db_quota", "cpu_quota",
                 "zone", "zone_of", "owner", "owner_of", "namespaces", "namespace", "session",
                 "attributes", "sys_attributes", "location", "contents", "aliases", "created", "modified"]

    def __init__(self, service: "GameService", dbref: int, name: str, owner: "User"):
        self.service = service
        self.dbid = dbref
        self.dbref = f"#{dbref}"
        self.created: int = 0
        self.modified: int = 0
        self.name = sys.intern(name)
        self.aliases: List[str] = list()
        self.owner: "User" = owner
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
        self.attributes = AttributeHandler(self, self.service.attributes)
        self.sys_attributes = AttributeHandler(self, self.service.sysattributes)
        self.location: Optional[Tuple[GameObject, str, Optional[Union[Tuple[int, int, int], Tuple[float, float, float]]]]] = None
        self.contents: Dict[str, Inventory] = dict()
        self.db_quota: int = 0
        self.cpu_quota: float = 0.0

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

        if self.sys_attributes.count():
            out["sys_attributes"] = self.sys_attributes.serialize()

        return out

    def listeners(self):
        out = list()
        if self.session:
            out.append(self.session)
        return out

    def parser(self):
        return Parser(self.core, self.objid, self.objid, self.objid)

    def msg(self, text, **kwargs):
        flist = fmt.FormatList(self, **kwargs)
        flist.add(fmt.Text(text))
        self.send(flist)

    def send(self, message: fmt.FormatList):
        self.receive_msg(message)
        for listener in self.listeners():
            if listener not in message.relay_chain:
                listener.send(message.relay(self))

    def receive_msg(self, message: fmt.FormatList):
        pass


class Alliance(GameObject):
    type_name = 'ALLIANCE'


class Board(GameObject):
    type_name = 'BOARD'


class Channel(GameObject):
    type_name = 'CHANNEL'


class Dimension(GameObject):
    type_name = 'DIMENSION'


class District(GameObject):
    type_name = 'District'


class Exit(GameObject):
    type_name = 'EXIT'


class Faction(GameObject):
    type_name = 'FACTION'


class Gateway(GameObject):
    type_name = 'GATEWAY'


class HeavenlyBody(GameObject):
    type_name = 'HEAVENLYBODY'


class Item(GameObject):
    type_name = 'ITEM'


class Mobile(GameObject):
    type_name = 'MOBILE'


class Player(GameObject):
    type_name = 'PLAYER'


class Room(GameObject):
    type_name = 'ROOM'


class Sector(GameObject):
    type_name = 'SECTOR'


class Thing(GameObject):
    type_name = 'THING'


class Vehicle(GameObject):
    type_name = 'VEHICLE'


class Wilderness(GameObject):
    type_name = 'WILDERNESS'


class Zone(GameObject):
    type_name = 'ZONE'
