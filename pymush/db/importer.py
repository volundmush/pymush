from . flatfile import PennDB
from athanor.utils import partial_match


class VolDB(PennDB):
    def __init__(self):
        super().__init__()
        self.ccp = None

    def cobj(self, abbr):
        if self.ccp is None:
            if not (code_object := partial_match("Core Code Parent <CCP>", self.objects.values(), key=lambda x: x.name)):
                raise Exception("Oops. No Core Code Parent in database!")
            self.ccp = code_object
        if not (attr := self.ccp.get(f"COBJ`{abbr.upper()}")):
            return None
        return self.find_obj(attr.value.plain)

    def list_accounts(self):
        if not (account_parent := self.cobj('accounts')):
            return dict()
        return {o.id: o for o in account_parent.children}

    def list_groups(self):
        if not (group_parent := self.cobj('gop')):
            return dict()
        return {o.id: o for o in group_parent.children}

    def list_index(self, number: int):
        return {o.id: o for o in self.type_index.get(number, set())}

    def list_players(self):
        return self.list_index(8)

    def list_rooms(self):
        return self.list_index(1)

    def list_exits(self):
        return self.list_index(4)

    def list_things(self):
        return self.list_index(2)

    def list_districts(self):
        return {k: v for k, v in self.list_things().items() if v.get('D`DISTRICT', inherit=False)}


class Importer:
    def __init__(self, connection, path):
        self.db = VolDB.from_outdb(path)
        self.connection = connection
        self.game = connection.game
        connection.penn = self
        self.complete = set()
        self.obj_map = dict()
        self.old_new = dict()

    def create_obj(self, dbobj, mode):
        if not (type_class := self.game.obj_classes.get(mode, None)):
            raise ValueError(f"{mode} does not map to a type class!")
        if dbobj.id in self.game.objects:
            raise ValueError(f"DBREF conflict for #{dbobj.id}, cannot continue!")
        obj = type_class(self.game, dbobj.id, dbobj.name)
        obj.created = dbobj.created
        obj.modified = dbobj.modified
        for key, attr in dbobj.attributes.items():
            if key == 'ALIAS':
                for a in [a for a in attr.value.plain.split(';') if a]:
                    obj.aliases.append(a)
            else:
                obj.attributes.set_or_create(key, attr.value)
        self.obj_map[dbobj.id] = obj
        self.old_new[dbobj] = obj
        self.game.objects[dbobj.id] = obj
        self.game.type_index[type_class].add(obj)
        return obj

    def import_skeleton(self):
        for data, mode in ((self.db.list_accounts(), 'USER'), (self.db.list_groups(), 'FACTION'),
                           (self.db.list_districts(), 'DISTRICT'), (self.db.list_players(), 'PLAYER'),
                           (self.db.list_rooms(), 'ROOM'), (self.db.list_exits(), 'EXIT'),
                           (self.db.list_things(), 'THING')):
            for k, v in data.items():
                if k in self.obj_map:
                    continue
                self.create_obj(v, mode)

    def process_reverse(self):
        for old, new in self.old_new.items():

            if (zone := self.obj_map.get(old.zone, None)):
                new.zone = zone
                zone.zone_of.add(new)

            if old.type == 8:  # a player
                if (parent := self.obj_map.get(old.parent, None)):
                    if parent.type_name == 'USER':
                        parent.add_character(new)
            else:
                if (parent := self.obj_map.get(old.parent, None)):
                    new.parent = parent
                    parent.parent_of.add(new)
                if (owner := self.obj_map.get(old.owner, None)):
                    new.owner = owner
                    owner.owner_of.add(new)

            if old.type == 4:  # an exit
                if (destination := self.obj_map.get(old.location, None)):
                    new.home = destination
                    destination.home_of.add(new)
                if (location := self.obj_map.get(old.exits, None)):
                    location.contents.add('exits', new, None)
            elif old.type == 8: # a player
                if (location := self.obj_map.get(old.location, None)):
                    new.set_saved_location('_logout', (location, '', None))
            else:
                if (location := self.obj_map.get(old.location, None)):
                    location.contents.add('', new, None)


    def process_finalize(self):
        for old, new in self.old_new.items():
            if old.type == 8:
                if new.account:
                    account = new.account
                    if 'WIZARD' in old.flags:
                        account.admin_level = max(account.admin_level, 10)
                    elif 'ROYALTY' in old.flags:
                        account.admin_level = max(account.admin_level, 8)
                    elif (va := old.attributes.get('mush', 'V`ADMIN')):
                        if va == '1':
                            account.admin_level = max(account.admin_level, 6)


    def run(self):
        try:
            self.import_skeleton()
            self.process_reverse()
            self.process_finalize()
            self.connection.msg("IMPORT COMPLETE!?")
        except Exception as e:
            self.connection.msg(f"SOMETHING WENT WRONG: {e}")