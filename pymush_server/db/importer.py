from . flatfile import PennDB
from pymush_server.utils import partial_match


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
        return self.find_obj(attr.value.clean)

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
        self.core = connection.core
        connection.penn = self
        self.complete = set()
        self.obj_map = dict()

    def create_obj(self, dbobj, mode, namespace=None):
        obj, error = self.core.mapped_typeclasses[mode].create(name=dbobj.name, objid=dbobj.objid, namespace=namespace)
        if error:
            print(f"OOPS: {error}")
        self.obj_map[dbobj.id] = obj
        return obj

    def get_or_create_obj(self, dbobj, mode, namespace=None):
        if not (obj := self.obj_map.get(dbobj.id, None)):
            obj = self.create_obj(dbobj, mode, namespace=namespace)
            obj.attributes.set('core', 'datetime_created', dbobj.created)
            obj.attributes.set('core', 'datetime_modified', dbobj.modified)
            for k, v in dbobj.attributes.items():
                if k == 'ALIAS':
                    for a in [a for a in v.value.clean.split(';') if a]:
                        obj.aliases.append(a)
                else:
                    owner = self.obj_map.get(v.owner, None)
                    flags = v.flags
                    obj.attributes.set('mush', k, {"owner": owner.objid if owner else None, "flags": list(flags), 'value': v.value.encoded()})
        return obj

    def import_grid(self):
        districts = dict()
        dis_data = self.db.list_districts()
        for k, v in dis_data.items():
            obj = self.get_or_create_obj(v, 'district')
            obj.add_tag('penn_district')
            districts[k] = obj
        for k, v in districts.items():
            dbobj = dis_data[k]
            if (parent := self.obj_map.get(dbobj.parent, None)):
                parent.districts.add(v)
            if (ic := dbobj.get('D`IC', inherit=False)) and ic.value.truthy():
                v.attributes.set('core', 'ic', True)

        room_data = self.db.list_rooms()
        room_total = dict()
        room_districts = dict()
        nodist_room = dict()
        for k, v in room_data.items():
            obj = self.get_or_create_obj(v, 'room')
            if (district := districts.get(v.parent, None)):
                district.rooms.add(obj)
                room_districts[k] = obj
            else:
                nodist_room[k] = obj
            room_total[k] = v
            obj.add_tag('penn_room')

        exit_data = self.db.list_exits()
        exit_total = dict()
        exit_dist = dict()
        exit_nodist = dict()
        for k, v in exit_data.items():
            if not (location := self.obj_map.get(v.exits, None)):
                continue  # No reason to make an Exit for a room that doesn't exist, is there?
            if not (destination := self.obj_map.get(v.location, None)):
                continue  # No reason to make an Exit for a room that doesn't exist, is there?
            obj = self.get_or_create_obj(v, 'exit')
            location.exits.add(obj)
            destination.entrances.add(obj)
            if (dist := location.relations.get('room_district')):
                dist.exits.add(obj)
                exit_dist[k] = obj
            else:
                exit_nodist[k] = obj

            obj.add_tag('penn_exit')
            exit_total[k] = obj
        return {
            'districts': districts.values(),
            'room_total': room_total.values(),
            'room_nodist': nodist_room.values(),
            'room_dist': room_districts.values(),
            'exit_total': exit_total.values(),
            'exit_dist': exit_dist.values(),
            'exit_nodist': exit_nodist.values()
        }

    def import_accounts(self):
        namespace = self.core.namespace_prefix['A']
        data = self.db.list_accounts()
        total = list()
        for k, v in data.items():
            obj = self.get_or_create_obj(v, 'account', namespace=namespace)
            obj.add_tag('penn_account')
            total.append(obj)
        return total

    def import_characters(self):
        namespace = self.core.namespace_prefix['C']
        data = self.db.list_players()
        total = list()
        for k, v in data.items():
            if 'Guest' in v.powers:
                # Filtering out guests.
                continue
            obj = self.get_or_create_obj(v, 'mobile', namespace=namespace)
            obj.attributes.set("core", "penn_hash", v.get('XYXXY').value.clean)
            if (account := self.obj_map.get(v.parent, None)):
                # Hooray, we have an account!
                account.characters.add(obj)

                if 'WIZARD' in v.flags:
                    if not account.attributes.has('core', 'supervisor_level'):
                        account.attributes.set('core', 'supervisor_level', 10)
                elif 'ROYALTY' in v.flags:
                    if not account.attributes.has('core', 'supervisor_level'):
                        account.attributes.set('core', 'supervisor_level', 8)
                elif (va := obj.attributes.get('mush', 'V`ADMIN')):
                    if va == '1':
                        if not account.attributes.has('core', 'supervisor_level'):
                            account.attributes.set('core', 'supervisor_level', 6)

                # if we don't get an account, then this character can still be accessed using their password, but...
            if (location := self.obj_map.get(v.location, None)):
                obj.attributes.set('core', 'logout_location', location.objid)
            obj.add_tag('penn_character')
            total.append(obj)
        return total
