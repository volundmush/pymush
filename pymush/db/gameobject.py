import sys
from typing import Union, Set, Optional, List, Dict, Tuple, Iterable
from athanor.utils import lazy_property
from .attributes import AttributeHandler
from athanor.shared import ConnectionOutMessage, ConnectionOutMessageType, ConnectionInMessageType, ConnectionInMessage
from ..utils import formatter as fmt
from ..utils.styling import StyleHandler


class GameSession:

    def __init__(self, sid: int, user: "GameObject", character: "GameObject"):
        self.sid: int = sid
        self.user: "GameObject" = user
        self.character: "GameObject" = character
        self.puppet: "GameObject" = character
        self.connections: Set["Connection"] = set()
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
    unique_names = False

    __slots__ = ["service", "dbid", "dbref", "name", "parent", "parent_of", "home", "home_of", "db_quota", "cpu_quota",
                 "zone", "zone_of", "owner", "owner_of", "namespaces", "namespace", "sessions", "connections",
                 "attributes", "sys_attributes", "location", "contents", "aliases", "created", "modified", "style_holder"]

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
        self.sessions: Set["GameSession"] = set()
        self.connections: Set["Connection"] = set()
        self.attributes = AttributeHandler(self, self.service.attributes)
        self.sys_attributes = dict()
        self.location: Optional[Tuple[GameObject, str, Optional[Union[Tuple[int, int, int], Tuple[float, float, float]]]]] = None
        self.contents: Dict[str, Inventory] = dict()
        self.db_quota: int = 0
        self.cpu_quota: float = 0.0
        self.admin_level: int = 0
        self.style_holder: Optional[StyleHandler] = None

    @property
    def style(self):
        if not self.style_holder:
            self.style_holder = StyleHandler(self)
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

        if self.sys_attributes.count():
            out["sys_attributes"] = self.sys_attributes.serialize()

        return out

    def listeners(self):
        return self.sessions if self.sessions else []

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
    unique_names = True

    @property
    def account(self):
        aid = self.sys_attributes.get('account', None)
        if aid is not None:
            account = self.service.objects.get(aid, None)
            if account:
                return account

    @account.setter
    def account(self, account: Optional[GameObject] = None):
        if account:
            self.sys_attributes['account'] = int(account)
        else:
            self.sys_attributes.pop('account', None)



class Room(GameObject):
    type_name = 'ROOM'


class Sector(GameObject):
    type_name = 'SECTOR'


class Thing(GameObject):
    type_name = 'THING'


class User(GameObject):
    type_name = 'USER'
    unique_names = True

    @property
    def email(self) -> Optional[str]:
        return self.sys_attributes.get('email', None)

    @email.setter
    def email(self, email: Optional[str]):
        if email:
            self.sys_attributes['email'] = email
        else:
            self.sys_attributes.pop('email', None)

    @property
    def last_login(self) -> Optional[float]:
        return self.sys_attributes.get('last_login', None)

    @last_login.setter
    def last_login(self, timestamp: Optional[float]):
        if timestamp:
            self.sys_attributes['last_login'] = timestamp
        else:
            self.sys_attributes.pop('last_login', None)

    @property
    def password(self):
        return self.sys_attributes.get('password', None)

    @password.setter
    def password(self, hash: Optional[str] = None):
        if hash:
            self.sys_attributes['password'] = hash
        else:
            self.sys_attributes.pop('password', None)

    def change_password(self, text, nohash=False):
        if not nohash:
            text = self.service.crypt_con.hash(text)
        self.password = text

    def check_password(self, text):
        hash = self.password
        if not hash:
            return False
        return self.service.crypt_con.verify(text, hash)

    def add_character(self, character: GameObject):
        characters = self.characters
        if character not in characters:
            characters.add(character)
            self.characters = characters
            character.account = self

    def remove_character(self, character: GameObject):
        characters = self.characters
        if character in characters:
            characters.remove(character)
            self.characters = characters
        if character.account == self:
            character.account = None

    @property
    def characters(self):
        ids = self.sys_attributes.get('characters', set())
        count = len(ids)
        result = set([i for f in ids if (i := self.service.objects.get(f, None))])
        if len(result) != count:
            self.characters = result
        return result

    @characters.setter
    def characters(self, characters: Optional[Iterable[GameObject]] = None):
        if characters:
            self.sys_attributes['characters'] = [int(c) for c in characters]
        else:
            self.sys_attributes.pop('characters', None)


class Vehicle(GameObject):
    type_name = 'VEHICLE'


class Wilderness(GameObject):
    type_name = 'WILDERNESS'


class Zone(GameObject):
    type_name = 'ZONE'
