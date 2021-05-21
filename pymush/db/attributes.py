import sys
from dataclasses import dataclass, field
from typing import Optional, Union, List, Dict, Set
from rich.text import Text


@dataclass
class Attribute:
    name: str
    holders: Set = field(default_factory=set)

    def __hash__(self):
        return hash(self.name)

    def __eq__(self, other):
        return (other is self) or (other.name == self.name)

class AttributeManager:

    __slots__ = ['owner', 'attributes', 'roots']

    def __init__(self, owner):
        self.owner = owner
        self.attributes: Dict[str, Attribute] = dict()
        self.roots: Dict[str, Attribute] = dict()

    def create(self, name: str) -> Attribute:
        s = sys.intern(name.upper())
        a = Attribute(name=s)
        self.attributes[s] = a
        return a

    def get(self, name: str) -> Optional[Attribute]:
        return self.attributes.get(name.upper(), None)

    def get_or_create(self, name: str):
        s = sys.intern(name.upper())
        if (a := self.attributes.get(s, None)):
            return a
        a = Attribute(name=s)
        self.attributes[s] = a
        return a


class SysAttributeManager(AttributeManager):
    pass


@dataclass
class AttributeValue:
    attribute: Attribute
    value: Text


class AttributeHandler:

    def __init__(self, owner: "GameObject", manager: AttributeManager):
        self.owner: "GameObject" = owner
        self.manager: AttributeManager = manager
        self.attributes: Dict[Attribute, AttributeValue] = dict()

    def get(self, name: str) -> Optional[AttributeValue]:
        attr = self.manager.get(name)
        if attr:
            return self.attributes.get(attr, None)
        return None

    def set_or_create(self, name: str, value: Text):
        attr = self.manager.get_or_create(name)
        if attr:
            val = self.attributes.get(attr, None)
            if val:
                val.value = value
            else:
                val = AttributeValue(attr, value)
                self.attributes[attr] = val

    def wipe(self, pattern):
        pass