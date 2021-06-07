import re

from typing import Dict, Union, Tuple, List, Set


class Script:

    def __init__(self, handler: "ScriptHandler", name: str, matcher, attr: str, locks: str):
        self.handler = handler
        self.name = name
        self.matcher = matcher
        self.locks = locks
        self.attr = attr


class ScriptHandler:

    def __init__(self, owner: "GameObject"):
        self.owner = owner
        self.scripts: Dict[str, Script] = dict()

    def serialize(self):
        return {key: {'matcher': val.matcher.pattern, 'attr': val.attr, 'locks': val.locks} for
                key, val in self.scripts.items()}
