from . base import GameObject
from typing import Optional, Iterable


class User(GameObject):
    type_name = 'USER'
    unique_names = True

    def listeners(self):
        return self.account_sessions

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