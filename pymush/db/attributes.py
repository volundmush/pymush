import sys
from dataclasses import dataclass, field
from typing import Optional, Union, List, Dict, Set
from rich.text import Text


@dataclass
class Attribute:
    name: str
    holders: Set = field(default_factory=set)


class AttributeManager:

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


@dataclass
class AttributeValue:
    attribute: Attribute
    value: Text


class AttributeHandler:

    def __init__(self, owner):
        self.owner = owner
        self.attributes: Dict[Attribute, AttributeValue] = dict()
