import sys
from dataclasses import dataclass, field
from typing import Optional, Union, List, Dict, Set
from mudstring.patches.text import MudText, OLD_TEXT
from enum import IntEnum


@dataclass
class Attribute:
    manager: "AttributeManager"
    name: str
    holders: Set = field(default_factory=set)

    def __hash__(self):
        return hash(self.name)

    def __eq__(self, other):
        return (other is self) or (other.name == self.name)


class AttributeManager:
    attr_class = Attribute

    __slots__ = ['owner', 'attributes', 'roots']

    def __init__(self, owner):
        self.owner = owner
        self.attributes: Dict[str, Attribute] = dict()
        self.roots: Dict[str, Attribute] = dict()

    def create(self, name: Union[str, OLD_TEXT]) -> Attribute:
        plain = name.plain if isinstance(name, OLD_TEXT) else name
        name = plain.upper()
        if not self.valid_name(name):
            raise ValueError("Bad Name for an Attribute")
        s = sys.intern(name.upper())
        a = self.attr_class(manager=self, name=s)
        self.attributes[s] = a
        return a

    def get(self, name: str) -> Optional[Attribute]:
        plain = name.plain if isinstance(name, OLD_TEXT) else name
        return self.attributes.get(plain.upper(), None)

    def get_or_create(self, name: Union[str, OLD_TEXT]):
        plain = name.plain if isinstance(name, OLD_TEXT) else name
        name = plain.upper()
        if not self.valid_name(name):
            raise ValueError("Bad Name for an Attribute")
        s = sys.intern(name.upper())
        if (a := self.attributes.get(s, None)):
            return a
        a = self.attr_class(manager=self, name=s)
        self.attributes[s] = a
        return a

    def valid_name(self, name: str):
        return True


@dataclass
class AttributeValue:
    attribute: Attribute
    value: MudText

    def can_see(self, request: "AttributeRequest", handler: "AttributeHandler"):
        return True

    def can_set(self, request: "AttributeRequest", handler: "AttributeHandler"):
        return True

    def serialize(self) -> dict:
        return {"value": self.value.serialize()}


EMPTY = MudText("")


class AttributeRequestType(IntEnum):
    GET = 0
    SET = 1
    WIPE = 2


@dataclass
class AttributeRequest:
    accessor: "GameObject"
    req_type: AttributeRequestType
    name: Union[str, OLD_TEXT]
    parser: "Parser"
    value: Optional[Union[str, OLD_TEXT]] = None
    attr_base: Optional[Attribute] = None
    attr: Optional[AttributeValue] = None
    error: Optional[MudText] = None


class AttributeHandler:
    attr_class = AttributeValue

    def __init__(self, owner: "GameObject", manager: AttributeManager):
        self.owner: "GameObject" = owner
        self.manager: AttributeManager = manager
        self.attributes: Dict[Attribute, AttributeValue] = dict()

    def __len__(self):
        return len(self.attributes)

    def __bool__(self):
        return bool(self.attributes)

    def count(self):
        return len(self)

    def serialize(self) -> dict:
        return {attr.name: val.serialize() for attr, val in self.attributes.items()}

    def get(self, name: Union[str, OLD_TEXT]) -> Optional[AttributeValue]:
        attr = self.manager.get(name)
        if attr:
            return self.attributes.get(attr, None)
        return None

    def set_or_create(self, name: Union[str, OLD_TEXT], value: MudText):
        attr = self.manager.get_or_create(name)
        if attr:
            val = self.attributes.get(attr, None)
            if val:
                val.value = value
            else:
                val = self.attr_class(attr, value)
                self.attributes[attr] = val

    def wipe(self, pattern):
        pass

    def get_value(self, name: str) -> MudText:
        attr = self.get(name)
        if attr is None:
            return EMPTY
        else:
            return attr.value

    def api_access(self, request: AttributeRequest) -> bool:
        return True

    def api_can_see(self, accessor: "GameObject", name: Union[str, OLD_TEXT]) -> bool:
        return self.api_access(accessor)

    def _get_inherit(self, request: AttributeRequest):
        attr_base = self.manager.get(request.name)
        if not attr_base:
            return
        request.attr_base = attr_base
        attr = self.attributes.get(attr_base, None)
        if attr:
            request.attr = attr
        else:
            for ancestor in self.owner.ancestors:
                attr = ancestor.attributes.attributes.get(attr_base, None)
                if attr:
                    request.attr = attr

    def api_get(self, request: AttributeRequest):
        self._get_inherit(request)
        if request.attr is None:
            request.value = EMPTY
            return
        if not request.attr.can_see(request, self):
            request.error = MudText("NO PERMISSION TO GET ATTRIBUTE")
            return
        request.value = request.attr.value

    def api_set(self, request: AttributeRequest):
        try:
            attr_base = self.manager.get_or_create(request.name)
            request.attr_base = attr_base
        except ValueError as err:
            request.error = MudText(f"#-1 {str(err).upper()}")
            return
        attr = self.attributes.get(attr_base, None)
        if attr:
            request.attr = attr
            if not attr.can_set(request, self):
                request.error = MudText("#-1 NO PERMISSION TO SET ATTRIBUTE")
                return
            attr.value = request.value
        else:
            attr = self.attr_class(attr_base, request.value)
            self.attributes[attr_base] = attr
        return

    def api_request(self, request: AttributeRequest):
        if not self.api_access(request):
            request.error = MudText("PERMISSION DENIED FOR ATTRIBUTES")
            return

        if request.req_type == AttributeRequestType.SET:
            self.api_set(request)
        elif request.req_type == AttributeRequestType.GET:
            self.api_get(request)
        else:
            request.error = MudText("Malformed API request!")
