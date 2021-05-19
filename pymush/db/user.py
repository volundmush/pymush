import sys
from passlib.context import CryptContext
from typing import Optional, Union, List, Set, Tuple, Dict


class User:

    def __init__(self, manager: "UserManager", user_id: int, name: str):
        self.manager: "UserManager" = manager
        self.user_id: int = user_id
        self.name: str = name
        self.created: int = 0
        self.modified: int = 0
        self.admin_level: int = 0
        self.password_hash: Optional[str] = None
        self.db_quota: int = 0
        self.cpu_quota: float = 0.0
        self.objects: Set["GameObject"] = set()
        self.sessions: Set["GameSession"] = set()

    def listeners(self):
        out = list()
        for s in self.sessions:
            for c in s.connections:
                out.append(c)
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


class UserManager:
    crypt_con = CryptContext(schemes=['argon2'])

    def __init__(self, service: "GameService"):
        self.next_id: int = 0
        self.users: Dict[int, User] = dict()
        self.service = service
        self.user_class = service.app.classes['game']['user']


    def search(self, name, exact=False):
        name_lower = name.strip().lower()
        if exact:
            for obj in self.users.values():
                if name_lower == obj.name.lower():
                    return obj, None
        else:
            if (found := partial_match(name, self.users.values(), key=lambda x: x.name)):
                return found, None
        return None, f"Sorry, nothing matches: {name}"

    def create(self, name: str, password: str):
        cleaned = name.strip()
        found, err = self.search(name, exact=True)