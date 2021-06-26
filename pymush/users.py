from mudrich.text import Text
import weakref
from pymush.models import User as UserModel
from typing import Optional, Union, List, Dict, Tuple
import time


class UserManager:

    def __init__(self, game):
        self.game = game
        self.users = dict()

    async def load_users(self):
        """
        This is only to be used once - when the game loads.
        """
        for user in await UserModel.filter(deleted=False):
            self.users[user.id] = User(self, user)

    async def create_user(self, name: Text, password: str = None, admin_level: int = None, email: str = None):
        if self.find_user(name):
            raise ValueError("Username already exists!")
        password_hash = self.game.crypt_con.hash(password) if password else None
        created = int(time.time())
        modified = created
        user = await UserModel.create(name=name.plain.lower(), name_text=name, password_hash=password_hash,
                                      created=created, modified=modified, email=email)
        await user.save()
        new_user = User(self, user)
        self.users[user.id] = new_user
        return new_user

    def find_user(self, name: Text) -> Optional["User"]:
        candidates = self.users.values()
        lower = name.plain.lower()
        for can in candidates:
            if can.name.plain.lower() == lower:
                return can
        return None


class User:

    def __init__(self, manager: UserManager, model):
        self.manager = manager
        self.uuid = model.id
        self.name = model.name
        self.email = model.email
        self.admin_level = model.admin_level
        self.password_hash = model.password_hash
        self.created = model.created
        self.modified = model.modified
        self.userdata = model.userdata

        self.connections = weakref.WeakSet()
        self.sessions = weakref.WeakSet()

    @property
    def game(self):
        return self.manager.game

    async def change_password(self, password: str = None):
        password_hash = self.game.crypt_con.hash(password) if password else None
        user = await UserModel.filter(id=self.uuid).first()
        user.password_hash = password_hash
        self.password_hash = password_hash
        await user.save()

    async def check_password(self, password: str) -> bool:
        if not self.password_hash:
            return False
        return self.game.crypt_con.verify(password, self.password_hash)

    async def on_first_connection_login(self):
        pass

    async def on_connection_login(self):
        pass

    async def on_final_connection_logout(self):
        pass

    async def on_connection_logout(self):
        pass
