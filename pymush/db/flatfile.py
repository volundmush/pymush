import re
import hashlib
from collections import defaultdict
from athanor.utils import partial_match
from mudstring.encodings.pennmush import decode

class FlatLine:

    def __init__(self, text: str):
        self.text = text
        self.header = text[0] in ('+', '~', '!', '*')
        self.name = None
        self.value = None
        self.valtype = None
        self.depth = 0
        if self.header:
            if text.startswith("!"):
                self.value = int(text[1:])
                self.valtype = "dbref"
        else:
            self.depth = len(text) - len(text.lstrip(' '))
            name, value = text.lstrip(' ').split(" ", 1)
            self.name = name
            if value.startswith('"'):
                self.value = value[1:-1]
                self.valtype = "text"
            elif value.startswith("#"):
                self.value = int(value[1:])
                self.valtype = "dbref"
            else:
                self.value = int(value)
                self.valtype = "number"

    def __repr__(self):
        return f'{self.__class__.__name__}: ({self.depth}) {self.name} "{self.value}"'


def parse_flatlines(generator: callable):
    for line in generator:
        yield FlatLine(line)
    else:
        return None


def parse_flatfile(path: str, chunk_size: int = 50):
    """
    Opens up a PennMUSH flatfile and parses it generator-style so that escaped values with newlines are treated as single lines.

    This totally ignores any \r it sees but considers a \n a newline.

    Args:
        path (path-like): the file to open.
        chunk_size (int): bytes-at-a-time to read the file

    Returns:
        generator of parsed lines.
    """
    f = open(path, encoding="latin_1")
    scratch = ""
    escaped = False
    quoted = False

    while buffer := f.read(chunk_size):
        for c in buffer:
            # just ignore any CR's we see. We only care about LF.
            if c == "\r":
                continue

            if quoted:
                if escaped:
                    escaped = False
                    scratch += c
                else:
                    if c == '"':
                        quoted = False
                        scratch += c
                    elif c == "\\":
                        escaped = True
                    else:
                        scratch += c
            else:
                if c == '"':
                    quoted = True
                    scratch += c
                elif c == "\n":
                    yield scratch
                    scratch = ""
                else:
                    scratch += c
    else:
        return None


class Flag:
    def __init__(self, name):
        self.name = name
        self.letter = ""
        self.type = set()
        self.perms = set()
        self.negate_perms = set()
        self.aliases = set()

        self.objects = set()

    def set_line(self, line: FlatLine):
        if line.name == "letter":
            self.letter = line.value
        elif line.name == "type":
            self.type = set(line.value.split(' '))
        elif line.name == "perms":
            self.perms = set(line.value.split(' '))
        elif line.name == "negate_perms":
            self.negate_perms = set(line.value.split(' '))
        elif line.name == "alias":
            self.aliases.add(line.value)


class Attribute:
    def __init__(self, name):
        self.name = name
        self.flags = set()
        self.creator = -1
        self.data = ""
        self.aliases = set()

    def set_line(self, line: FlatLine):
        if line.name == "flags":
            self.flags = set(line.value.split(' '))
        elif line.name == "creator":
            self.creator = line.value
        elif line.name == "data":
            self.data = line.value


class ObjAttribute:
    def __init__(self, name):
        self.name = name
        self.value = ""
        self.owner = -1
        self.flags = set()
        self.derefs = -1

    def set_line(self, line: FlatLine):

        if line.name == "owner":
            self.owner = line.value
        elif line.name == "flags":
            self.flags = set(line.value.split(' '))
        elif line.name == "derefs":
            self.derefs = line.value
        elif line.name == "value":
            self.value = decode(line.value)


class ObjLock:
    def __init__(self, name):
        self.name = name
        self.creator = -1
        self.flags = set()
        self.derefs = -1
        self.key = ""

    def set_line(self, line: FlatLine):
        if line.name == "creator":
            self.creator = line.value
        elif line.name == "flags":
            self.flags = set(line.value.split(' '))
        elif line.name == "derefs":
            self.derefs = line.value
        elif line.name == "value":
            self.value = line.value


class DbObject:
    def __init__(self, db, dbref: int):
        self.db = db
        self.id = dbref
        self.name = ""
        self.location = -1
        self.exits = -1

        self.parent = -1
        self.owner = -1
        self.zone = -1
        self.pennies = 0
        self.type = -1
        self.flags = set()
        self.powers = set()
        self.warnings = set()
        self.created = -1
        self.modified = -1
        self.attributes = dict()
        self.locks = dict()

        self.children = set()
        self.contents = set()
        self.entrances = set()
        self.parent_obj = None
        self.owner_obj = None
        self.zone_obj = None
        self.location_obj = None
        self.exits_obj = None
        self.owns = set()
        self.zoned = set()

    def __repr__(self):
        return f"<DbObj {self.type} - {self.dbref}: {self.name}>"

    @property
    def dbref(self):
        return f"#{self.id}"

    @property
    def objid(self):
        return f"#{self.id}:{self.created}"

    @classmethod
    def from_lines(cls, db, dbref, lines):
        obj = cls(db, dbref)

        attr = None
        lock = None

        section = "header"
        for i, line in enumerate(lines):
            if line.depth == 0:
                if line.name == "attrcount" and line.value > 0:
                    section = "attributes"
                elif line.name == "lockcount" and line.value > 0:
                    section = "locks"
                else:
                    if section != "header":
                        section = "header"
                    obj.set_line(line)
            if line.depth == 1:
                if line.name in ("name", "type"):
                    if section == "attributes":
                        attr = db.attr_class(line.value)
                        obj.attributes[attr.name] = attr
                    elif section == "locks":
                        lock = ObjLock(line.value)
                        obj.locks[lock.name] = lock
            if line.depth == 2:
                if section == "attributes":
                    attr.set_line(line)
                elif section == "locks":
                    lock.set_line(line)

        return obj

    def set_line(self, line: FlatLine):
        if line.name == "name":
            self.name = line.value
        elif line.name == "location":
            self.location = line.value
        elif line.name == "parent":
            self.parent = line.value
        elif line.name == "owner":
            self.owner = line.value
        elif line.name == "pennies":
            self.pennies = line.value
        elif line.name == "type":
            self.type = line.value
        elif line.name == "flags":
            self.flags = set(line.value.split(' '))
        elif line.name == "powers":
            self.powers = set(line.value.split(' '))
        elif line.name == "warnings":
            self.warnings = set(line.value.split(' '))
        elif line.name == "created":
            self.created = line.value
        elif line.name == "modified":
            self.modified = line.value
        elif line.name == "exits":
            self.exits = line.value

    def get(self, attr, default=None, inherit=True):
        uattr = attr.upper()
        if (found := self.attributes.get(uattr, None)):
            return found
        else:
            if inherit and self.parent_obj:
                return self.parent_obj.get(uattr, default=default)
        return default

    def ancestors(self, reversed=False):
        out = list()
        if self.parent_obj:
            parent = self.parent_obj
            out.append(parent)
            while (parent := parent.parent_obj):
                out.append(parent)
        if reversed:
            out.reverse()
        return out

    def lattr(self, pattern, inherit=False):
        if not pattern:
            return dict()
        pattern = pattern.replace('`**', '`\S+').replace('*', '\w+')
        re_pattern = re.compile(f"^{pattern}$", flags=re.IGNORECASE)
        out = dict()
        if inherit:
            ancestors = self.ancestors(reversed=True)
            ancestors.append(self)
        else:
            ancestors = [self]
        for ancestor in ancestors:
            out.update({k: v for k, v in ancestor.attributes.items() if re_pattern.match(k)})
        return out

    def lattrp(self, pattern):
        return self.lattr(pattern, inherit=True)


class PennDB:
    obj_class = DbObject
    attr_class = ObjAttribute

    def __init__(self):
        self.bitflags = 0
        self.dbversion = 0
        self.savetime = ""
        self.flags = dict()
        self.powers = dict()
        self.objects = dict()
        self.attributes = dict()

        self.type_index = defaultdict(set)
        self.dbrefs = dict()
        self.objids = dict()

    def setup(self):
        for k, v in self.objects.items():
            self.type_index[v.type].add(v)

            if (found := self.objects.get(v.location, None)):
                found.contents.add(v)
                v.location_obj = found

            if (found := self.objects.get(v.exits, None)):
                v.exits_obj = found

            if (parent := self.objects.get(v.parent, None)):
                v.parent_obj = parent
                parent.children.add(v)

            if (zone := self.objects.get(v.zone, None)):
                v.zone_obj = zone
                zone.zoned.add(v)

            if (owner := self.objects.get(v.owner, None)):
                v.owner_obj = owner
                owner.owns.add(v)

            for fname in v.flags:
                if (flag := self.flags.get(fname, None)):
                    flag.objects.add(v)

            for pname in v.powers:
                if (flag := self.powers.get(pname, None)):
                    flag.objects.add(v)

            self.dbrefs[v.dbref] = v
            self.objids[v.objid] = v

    @classmethod
    def from_outdb(cls, path: str):
        db = cls()
        flag_cur = None
        attr_cur = None
        section = "header"

        header_section = list()
        obj_storage = defaultdict(list)
        cur_obj = -1

        for i, line in enumerate(parse_flatlines(parse_flatfile(path))):

            if section == "header":
                if line.text.startswith(("+V-")):
                    header_section.append(line)
                elif line.text.startswith("dbversion"):
                    header_section.append(line)
                elif line.text.startswith("savedtime"):
                    header_section.append(line)
                elif line.text.startswith("+FLAGS"):
                    section = "flags"

            if section == "flags":
                if line.depth == 0:
                    if line.name == "flagcount":
                        flags_left = int(line.value)
                    if line.name == "flagaliascount":
                        if flag_cur:
                            db.flags[flag_cur.name] = flag_cur
                        flag_alias_left = int(line.value)
                        section = "flagaliases"
                        flag_cur = None
                if line.depth == 1 and line.name == "name":
                    if flag_cur:
                        db.flags[flag_cur.name] = flag_cur
                    flag_cur = Flag(line.value)
                if line.depth == 2:
                    flag_cur.set_line(line)

            if section == "flagaliases":
                if line.depth == 1 and line.name == "name":
                    flag_cur = db.flags.get(line.name, None)
                if line.depth == 2 and line.name == "alias" and flag_cur:
                    flag_cur.set_line(line)
                if line.depth == 0 and line.text.startswith("+POWER"):
                    section = "powers"
                    flag_cur = None

            if section == "powers":
                if line.depth == 0:
                    if line.name == "flagcount":
                        powers_left = int(line.value)
                    if line.name == "flagaliascount":
                        if flag_cur:
                            db.powers[flag_cur.name] = flag_cur
                        power_alias_left = int(line.value)
                        section = "poweraliases"
                        flag_cur = None
                if line.depth == 1 and line.name == "name":
                    if flag_cur:
                        db.powers[flag_cur.name] = flag_cur
                    flag_cur = Flag(line.value)
                if line.depth == 2:
                    flag_cur.set_line(line)

            if section == "poweraliases":
                if line.depth == 1 and line.name == "name":
                    flag_cur = db.powers.get(line.name, None)
                if line.depth == 2 and line.name == "alias" and flag_cur:
                    flag_cur.set_line(line)
                if line.depth == 0 and line.text.startswith("+ATTRIBUTES"):
                    section = "attributes"
                    flag_cur = None

            if section == "attributes":
                if line.depth == 0:
                    if line.name == "attrcount":
                        attr_left = int(line.value)
                    if line.name == "attraliascount":
                        if attr_cur:
                            db.attributes[attr_cur.name] = attr_cur
                        attr_alias_left = int(line.value)
                        section = "attraliases"
                if line.depth == 1 and line.name == "name":
                    if attr_cur:
                        db.attributes[attr_cur.name] = attr_cur
                    attr = Attribute(line.value)
                    attr_cur = attr
                if line.depth == 2:
                    attr_cur.set_line(line)

            if section == "attraliases":
                if line.depth == 1 and line.name == "name":
                    flag_cur = db.powers.get(line.name, None)
                if line.depth == 2 and line.name == "alias" and flag_cur:
                    flag_cur.set_line(line)
                if line.depth == 0 and line.text.startswith("~"):
                    section = "objects"
                    attr_cur = None

            if section == "objects":
                if line.depth == 0 and line.header:
                    cur_obj = line.value
                elif line.depth == 0 and line.text.startswith("***END OF DUMP"):
                    break
                else:
                    obj_storage[cur_obj].append(line)

        for k, v in obj_storage.items():
            db.objects[k] = cls.obj_class.from_lines(db, k, v)

        db.setup()
        return db

    def isdbref(self, dbref):
        return self.dbrefs.get(dbref, None)

    def isobjid(self, objid):
        return self.objids.get(objid, None)

    def find_obj(self, dbref):
        if isinstance(dbref, int):
            return self.objects.get(dbref, None)
        if not dbref:
            return None
        if ':' in dbref:
            return self.isobjid(dbref)
        else:
            return self.isdbref(dbref)


def check_password(old_hash, password):
    if not old_hash:
        return False
    old_hash = old_hash
    hash_against = old_hash.split(':')[2]
    check = hashlib.new('sha1')
    if old_hash.startswith('1:'):
        check.update(password.encode('utf-8'))
        return check.hexdigest() == hash_against
    elif old_hash.startswith('2:'):
        salt = hash_against[0:2]
        hash_against = hash_against[2:]
        check.update(f"{salt}{password}".encode('utf-8'))
        return check.hexdigest() == hash_against