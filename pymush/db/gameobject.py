import sys
from typing import Union, Set, Optional, List, Dict
from pymush.utils.misc import lazy_property
from pymush.protocol import MudProtocolHandler
from . attributes import AttributeHandler


class GameSession:

    def __init__(self, sid: int, user: "GameObject", character: "GameObject"):
        self.sid: int = sid
        self.user: "GameObject" = user
        self.character: "GameObject" = character
        self.puppet: "GameObject" = character
        self.connections: Set[MudProtocolHandler] = set()


class NameSpace:

    def __init__(self, owner: "GameObject", name: str):
        self.owner = owner
        self.name = name
        self.objects: Dict[str, "GameObject"] = dict()

    def serialize(self) -> Dict:
        return dict()


class GameObject:
    type_name = None
    type_abbr = None
    type_ancestor: Optional["GameObject"] = None

    def __init__(self, dbref: int, name: str):
        self.dbid = dbref
        self.dbref = f"#{dbref}"
        self.name = sys.intern(name)
        self.children: Set[GameObject] = set()
        self.parent: Optional[GameObject] = None
        self.namespaces: Dict[str, NameSpace] = dict()
        self.sessions: Set["GameSession"] = set()

    @lazy_property
    def attributes(self):
        return AttributeHandler(self)

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

        if self.attributes.count():
            out["attributes"] = self.attributes.serialize()

        return out


class Alliance(GameObject):
    type_name = 'ALLIANCE'
    type_abbr = 'A'


class Board(GameObject):
    type_name = 'BOARD'
    type_abbr = 'B'


class Channel(GameObject):
    type_name = 'CHANNEL'
    type_abbr = 'C'


class Dimension(GameObject):
    type_name = 'DIMENSION'
    type_abbr = 'D'


class Exit(GameObject):
    type_name = 'EXIT'
    type_abbr = 'E'


class Faction(GameObject):
    type_name = 'FACTION'
    type_abbr = 'F'


class Gateway(GameObject):
    type_name = 'GATEWAY'
    type_abbr = 'G'


class HeavenlyBody(GameObject):
    type_name = 'HEAVENLYBODY'
    type_abbr = 'H'


class Item(GameObject):
    type_name = 'ITEM'
    type_abbr = 'I'


class Mobile(GameObject):
    type_name = 'MOBILE'
    type_abbr = 'M'


class Player(GameObject):
    type_name = 'PLAYER'
    type_abbr = 'P'


class Room(GameObject):
    type_name = 'ROOM'
    type_abbr = 'R'


class Sector(GameObject):
    type_name = 'SECTOR'
    type_abbr = 'S'


class User(GameObject):
    type_name = 'USER'
    type_abbr = 'U'


class Vehicle(GameObject):
    type_name = 'VEHICLE'
    type_abbr = 'V'


class Wilderness(GameObject):
    type_name = 'WILDERNESS'
    type_abbr = 'W'


class Zone(GameObject):
    type_name = 'ZONE'
    type_abbr = 'Z'
