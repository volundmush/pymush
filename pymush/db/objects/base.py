import sys
from typing import Union, Set, Optional, List, Dict, Tuple
from athanor.utils import lazy_property, partial_match
from pymush.utils import formatter as fmt
from pymush.utils.styling import StyleHandler
from collections import defaultdict
from mudstring.patches.text import MudText, OLD_TEXT
from mudstring.encodings.pennmush import ansi_fun, send_menu
import weakref
from pymush.db.scripts import ScriptHandler
from pymush.engine.parser import Parser


class Inventory:

    def __init__(self):
        self.coordinates = defaultdict(set)
        self.reverse = dict()

    def add(self, obj: "GameObject", coordinates=None):
        if obj in self.reverse:
            old_coor = self.reverse[obj]
            self.coordinates[old_coor].remove(obj)
            if not len(self.coordinates):
                del self.coordinates[old_coor]
        self.coordinates[coordinates].add(obj)
        self.reverse[obj] = coordinates

    def remove(self, obj: "GameObject"):
        if obj in self.reverse:
            old_coor = self.reverse[obj]
            self.coordinates[old_coor].remove(obj)
            if not len(self.coordinates):
                del self.coordinates[old_coor]
            del self.reverse[obj]

    def all(self):
        return self.reverse.keys()


class ContentsHandler:
    inventory_class = Inventory

    def __init__(self, owner):
        self.owner = owner
        self.inventories = defaultdict(self.inventory_class)
        self.reverse = dict()

    def add(self, name: str, obj: "GameObject", coordinates=None):
        destination = self.inventories[name]
        if obj in self.reverse:
            rev = self.reverse[obj]
            if rev == destination:
                rev.add(obj, coordinates)
            else:
                self.reverse[obj].remove(obj)
                destination.add(obj, coordinates)
                self.reverse[obj] = destination
        else:
            destination.add(obj, coordinates)
            self.reverse[obj] = destination
        obj.location = (self.owner, name, coordinates)

    def remove(self, obj: "GameObject"):
        if obj in self.reverse:
            rev = self.reverse[obj]
            rev.remove(obj)
            del self.reverse[obj]
            obj.location = None

    def all(self, name=None):
        if name is not None:
            return self.inventories[name].all()
        return self.reverse.keys()


class GameObject:
    type_name = None
    unique_names = False
    cmd_matchers = ('script',)
    is_root_owner = False
    can_be_zone = False
    can_be_destination = False
    can_have_destination = False
    can_be_puppet = False
    no_location = False
    ignore_sessionless = False

    def __init__(self, game: "GameService", dbid: int, created: int, name: str):
        self.game = game
        self.dbid = dbid
        self.created: int = created
        self.modified: int = created
        self._name = sys.intern(name)
        self.aliases: List[str] = list()
        self._parent: Optional[GameObject] = None
        self._parent_of: weakref.WeakValueDictionary[str, GameObject] = weakref.WeakValueDictionary()
        self._zone: Optional[GameObject] = None
        self._zone_of: weakref.WeakValueDictionary[str, GameObject] = weakref.WeakValueDictionary()
        self._owner: Optional[GameObject] = None
        self._owner_of: weakref.WeakValueDictionary[str, GameObject] = weakref.WeakValueDictionary()
        self._owner_of_type: Dict[str, weakref.WeakValueDictionary] = defaultdict(weakref.WeakValueDictionary)
        self.namespaces: Dict[str, weakref.WeakSet] = defaultdict(weakref.WeakSet)
        self._namespace: Optional[GameObject] = None
        self.session: Optional["GameSession"] = None
        self.account_sessions: Set["GameSession"] = set()
        self.connections: Set["Connection"] = set()
        self.attributes = game.app.classes['game']['attributehandler'](self, self.game.attributes)
        self.sys_attributes = dict()
        self._location: Optional[GameObject] = None
        self._location_of: weakref.WeakValueDictionary[str, GameObject] = weakref.WeakValueDictionary()
        self._destination: Optional[GameObject] = None
        self.db_quota: int = 0
        self.cpu_quota: float = 0.0
        self.admin_level: int = 0
        self.style_holder: Optional[StyleHandler] = None
        self.scripts = ScriptHandler(self)

    @lazy_property
    def dbref(self):
        return f"#{self.dbid}"

    @lazy_property
    def objid(self):
        return f"#{self.dbid}:{int(self.created)}"

    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, value: Union[str, OLD_TEXT]):
        plain = value.plain if isinstance(value, OLD_TEXT) else value
        plain = plain.strip()
        if not self.game.app.config.regex['basic_name'].match(plain):
            raise ValueError("Name contains invalid characters!")
        if self.unique_names:
            found, err = self.game.search_objects(plain, self.game.type_index[self.type_name], exact=True, aliases=True)
            if found and found != self:
                raise ValueError("Name conflict within TYPE detected!")
        if self.namespace:
            found, err = self.game.search_objects(plain, self.namespace.namespaces[self.type_name], exact=True, aliases=True)
            if found and found != self:
                raise ValueError(f"Name conflict within namespace {self.objid}-{self.type_name} detected!")
        self._name = sys.intern(plain)

    @property
    def owner(self):
        return self._owner

    @owner.setter
    def owner(self, value: Optional[Union["GameObject", str, OLD_TEXT, int]]):
        if self.is_root_owner:
            raise ValueError(f"A {self.type_name} cannot be owned by anything! It is a root owner!")
        old = self._owner
        if value is not None:
            found = self.game.resolve_object(value)
            if not found:
                raise ValueError(f"Cannot resolve {value} to a GameObject!")
            if found == self:
                raise ValueError(f"{self.objid} cannot own itself!")
            if found == old:
                return
            if old and found != old:
                del old._owner_of[self.objid]
                del old._owner_of_type[self.type_name][self.objid]
            found._owner_of[self.objid] = self
            found._owner_of_type[self.type_name][self.objid] = self
            self._owner = weakref.proxy(found)
        else:
            if old:
                del old._owner_of[self.objid]
                del old._owner_of_type[self.type_name][self.objid]
            self._owner = None

    @property
    def root_owner(self):
        if self.is_root_owner:
            return None
        owner = self.owner
        while owner is not None:
            if owner.is_root_owner:
                return owner
            else:
                owner = owner.owner

    @property
    def zone(self):
        return self._zone

    @zone.setter
    def zone(self, value: Optional[Union["GameObject", str, OLD_TEXT, int]]):
        if self.can_be_zone:
            raise ValueError(f"{self.objid} cannot be assigned to a Zone as it is a zone candidate!")
        old = self._zone
        if value is not None:
            found = self.game.resolve_object(value)
            if not found:
                raise ValueError(f"Cannot resolve {value} to a GameObject!")
            if not found.can_be_zone:
                raise ValueError(f"{found.objid} cannot be used as a Zone!")
            if found == self:
                raise ValueError(f"{self.objid} cannot Zone to itself!")
            if found == old:
                return
            if self.objid in found.zdescendants:
                raise ValueError(f"That would create a circular relationship! Cannot be your own grandpa!")
            if old and found != old:
                del old._zone_of[self.objid]
            found._zone_of[self.objid] = self
            self._zone = weakref.proxy(found)
        else:
            if old:
                del old._zone_of[self.objid]
            self._zone = None

    def gather_zones(self, max_zones: Optional[int] = None, max_depth: Optional[int] = None):
        found = list()
        locations = weakref.WeakSet()
        location = self.location
        locations.add(location)
        cur_depth = 0
        while location is not None:
            if max_depth and cur_depth >= max_depth:
                break
            z = location.zone
            if z:
                if z not in found:
                    found.append(z)
                    if max_zones and len(found) >= max_zones:
                        break
            cur_depth += 1
            location = location.location
            if location in locations:
                # woops, recursion!
                break
            locations.add(location)

        return found


    @property
    def in_zone(self):
        location = self.location
        if location:
            return location._recurse_to_zone()
        return None

    def _recurse_to_zone(self):
        z = self.zone
        if z:
            return z
        else:
            location = self.location
            if location:
                return location._recurse_to_zone()
            else:
                return None

    @property
    def zdescendants(self):
        out = weakref.WeakValueDictionary()
        return self._zdescendants(out)

    def _zdescendants(self, out):
        out.update(self._zone_of)
        for obj in self._zone_of.values():
            obj._zdescendants(out)
        return out

    @property
    def parent(self):
        return self._parent

    @parent.setter
    def parent(self, value: Optional[Union["GameObject", str, OLD_TEXT, int]]):
        old = self._parent
        if value is not None:
            found = self.game.resolve_object(value)
            if not found:
                raise ValueError(f"Cannot resolve {value} to a GameObject!")
            if found == self:
                raise ValueError(f"{self.objid} cannot be its own parent!")
            if self.objid in found.descendants:
                raise ValueError(f"That would create a circular relationship! Cannot be your own grandpa!")
            if old and found != old:
                del old._parent_of[self.objid]
            found._parent_of[self.objid] = self
            self._parent = weakref.proxy(found)
        else:
            if old:
                del old._parent_of[self.objid]
            self._parent = None

    @property
    def ancestors(self):
        parent = self.parent
        while parent:
            yield parent
            parent = parent.parent

    @property
    def descendants(self):
        out = weakref.WeakValueDictionary()
        return self._descendants(out)

    def _descendants(self, out):
        out.update(self._parent_of)
        for obj in self._parent_of.values():
            obj._descendants(out)
        return out

    @property
    def location(self):
        return self._location

    @location.setter
    def location(self, value: Optional[Union["GameObject", str, OLD_TEXT, int]]):
        if self.no_location:
            raise ValueError(f"{self.objid} cannot have a location!")
        old = self._location
        if value is not None:
            found = self.game.resolve_object(value)
            if not found:
                raise ValueError(f"Cannot resolve {value} to a GameObject!")
            if found == self:
                raise ValueError(f"{self.objid} cannot be inside itself!")
            if found == old:
                return
            if old and found != old:
                del old._location_of[self.objid]
            found._location_of[self.objid] = self
            self._location = weakref.proxy(found)
        else:
            if old:
                del old._location_of[self.objid]
            self._location = None

    @property
    def contents(self):
        return self._location_of.values()

    @property
    def namespace(self):
        return self._namespace

    @namespace.setter
    def namespace(self, value: Optional[Union["GameObject", str, OLD_TEXT, int]]):
        old = self._namespace
        if value is not None:
            found = self.game.resolve_object(value)
            if not found:
                raise ValueError(f"Cannot resolve {value} to a GameObject!")
            if found == self:
                raise ValueError(f"{self.objid} cannot own itself!")
            if found == old:
                return
            obj, err = self.game.search_objects(self.name, found.namespaces[self.type_name], exact=True,
                                                  aliases=True)
            if obj and obj != self:
                raise ValueError(f"Name conflict within namespace {found.objid}-{self.type_name} detected!")

            if old and found != old:
                old.namespaces[self.type_name].remove(self)
            found.namespaces[self.type_name].add(self)
            self._namespace = weakref.proxy(found)
        else:
            if old:
                old.namespaces[self.type_name].remove(self)
            self._namespace = None

    @property
    def destination(self):
        return self._destination

    @destination.setter
    def destination(self, value: Optional[Union["GameObject", str, OLD_TEXT, int]]):
        if not self.can_have_destination:
            raise ValueError(f"{self.objid} cannot have a destination!")
        if value is not None:
            found = self.game.resolve_object(value)
            if not found:
                raise ValueError(f"Cannot resolve {value} to a GameObject!")
            if found == self:
                raise ValueError(f"{self.objid} cannot point at itself!")
            if not found.can_be_destination:
                raise ValueError(f"{found.objid} cannot be a destination!")
            self._destination = weakref.proxy(found)
        else:
            self._destination = None

    def __hash__(self):
        return hash(self.objid)

    @property
    def style(self):
        if self.session:
            return self.session.style
        if not self.style_holder:
            self.style_holder = StyleHandler(self, save=True)
        return self.style_holder

    def __int__(self):
        return self.dbid

    def __repr__(self):
        return f"<{self.__class__.__name__} {self.objid} : {self.name}>"

    def serialize(self) -> Dict:
        out: Dict = {
            "dbid": self.dbid,
            "name": self.name,
            "created": self.created,
            "modified": self.modified,
            "type_name": self.type_name
        }
        if self.parent:
            out["parent"] = self.parent.objid


        if self.locks:
            out["locks"] = self.locks.serialize()

        if self.namespace:
            out["namespace"] = self.namespace.objid

        if self.attributes:
            out["attributes"] = self.attributes.serialize()

        if self.sys_attributes:
            out["sys_attributes"] = self.sys_attributes

        if self.location:
            out["location"] = self.location.objid

        return out

    def listeners(self):
        if self.session:
            return [self.session]
        return []

    def msg(self, text, **kwargs):
        flist = fmt.FormatList(self, **kwargs)
        flist.add(fmt.Line(text))
        self.send(flist)

    def send(self, message: fmt.FormatList):
        self.receive_msg(message)
        for listener in self.listeners():
            if listener not in message.relay_chain:
                listener.send(message.relay(self))

    def access(self, accessor: "GameObject", access_type: str, default=False, no_superuser_bypass=False):
        return self.locks.check(accessor, access_type, default=default, no_superuser_bypass=no_superuser_bypass)

    def receive_msg(self, message: fmt.FormatList):
        pass

    def get_alevel(self, ignore_quell=False):
        if self.session:
            return self.session.get_alevel(ignore_quell=ignore_quell)

        if self.owner:
            return self.owner.admin_level
        else:
            return self.admin_level

    def get_dub(self, target):
        dubs = self.sys_attributes.get('dubs', dict())
        return dubs.get((target.dbid, target.created), None)

    def set_sub(self, target, value: str):
        dubs = self.sys_attributes.get('dubs', dict())
        if value:
            dubs[(target.dbid, target.created)] = value
        else:
            dubs.pop((target.dbid, target.created), None)
        self.sys_attributes['dubs'] = dubs

    def generate_name_for(self, target):
        return target.name

    def generate_aliases_for(self, target):
        return target.aliases

    def get_keyphrase_for(self, target):
        return target.name

    def get_dub_or_keyphrase_for(self, target):
        dubbed = self.get_dub(target)
        if dubbed:
            return dubbed
        return self.get_keyphrase_for(target)

    def generate_identifiers_for(self, target, names=True, aliases=True, nicks=True):
        whole, words = list(), list()
        if names:
            name = self.generate_name_for(target)
            whole.append(name)
            words.extend(name.split())
        if aliases:
            for alias in self.generate_aliases_for(target):
                whole.append(alias)
                words.extend(alias.split())
        if nicks:
            pass
        return whole, words

    def locate_object(self, name: str, general=True, dbref=True, location=True, contents=True, candidates=None,
                      use_names=True, use_nicks=True, use_aliases=True, use_dub=True, exact=False, first_only=False,
                      multi_match=False, filter_visible=True):
        name = name.strip()
        nlower = name.lower()
        out = list()

        loc = None
        if location is True:
            loc = self.location
        elif location:
            loc = location

        if general:
            dict_check = {
                'self': self,
                'me': self,
                'here': loc
            }

            if (found := dict_check.get(nlower, None)):
                out.append(found)
                return out, None

        if dbref and name.startswith('#'):
            found, err = self.game.locate_dbref(name)
            if found:
                out.append(found)
                return out, None
            else:
                return None, err

        quant = None
        if multi_match and '|' in name:
            quant_str, name = name.split('|', 1)
            quant_str = quant_str.strip().lower()
            if quant_str == 'all':
                quant = -1
            elif quant_str.isdigit():
                quant = max(int(quant_str), 1)
            else:
                return None, f"Unknown quantifier: {quant_str}"

        quoted = name.startswith('"') and name.endswith('"')
        name = name.strip('"')

        total_candidates = set()
        if candidates:
            total_candidates.update(candidates)
        if location and loc:
            total_candidates.update(loc.contents)
        if contents:
            total_candidates.update(self.contents)
        if self in total_candidates:
            total_candidates.remove(self)

        if filter_visible:
            total_candidates = [c for c in total_candidates if self.can_perceive(c)]
        else:
            total_candidates = list(total_candidates)

        keywords = defaultdict(list)
        full_names = defaultdict(list)

        simple_words = ('the', 'of', 'an', 'a', 'or', 'and')

        for can in total_candidates:
            whole, words = self.generate_identifiers_for(can, names=use_names, aliases=use_aliases, nicks=use_nicks)
            for word in words:
                ilower = word.lower()
                if ilower in simple_words:
                    continue
                keywords[ilower].append(can)
            for n in whole:
                full_names[n.lower()].append(can)

        nlower = name.lower()
        if exact:
            if (found := full_names.get(nlower, None)):
                out.extend(found)
        else:
            if quoted:
                m = partial_match(nlower, full_names.keys())
                if m:
                    out.extend(full_names[m])
            else:
                m = partial_match(nlower, keywords.keys())
                if m:
                    out.extend(keywords[m])

        if not out:
            return out, "Nothing was found."

        if first_only:
            out = [out[0]]
        elif multi_match:
            if quant is None:
                quant = 1

            if quant == -1:
                return out, None
            else:
                if len(out) >= quant:
                    out = [out[quant - 1]]
                else:
                    return [], "Nothing was found by that index."

        return out, None

    def can_perceive(self, target: "GameObject"):
        return True

    def can_interact_with(self, target: "GameObject"):
        return True
    
    def render_appearance(self, interpreter: "Interpreter", viewer: "GameObject", internal=False):
        parser = interpreter.make_parser(executor=self, enactor=viewer)
        out = fmt.FormatList(viewer)

        if (nameformat := self.attributes.get_value('NAMEFORMAT')):
            result = parser.evaluate(nameformat, executor=self, number_args={0: self.dbref, 1: self.name})
            out.add(fmt.Line(result))
        else:
            out.add(fmt.Line(ansi_fun('hw', self.name) + f" ({self.dbref})"))

        if internal and (idesc := self.attributes.get_value('IDESCRIBE')):
            idesc_eval = parser.evaluate(idesc, executor=self)
            if (idescformat := self.attributes.get_value('IDESCFORMAT')):
                result = parser.evaluate(idescformat, executor=self, number_args=(idesc_eval,))
                out.add(fmt.Line(result))
            else:
                out.add(fmt.Line(idesc_eval))

        elif (desc := self.attributes.get_value('DESCRIBE')):
            desc_eval = parser.evaluate(desc, executor=self)
            if (descformat := self.attributes.get_value('DESCFORMAT')):
                result = parser.evaluate(descformat, executor=self, number_args=(desc_eval,))
                out.add(fmt.Line(result))
            else:
                out.add(fmt.Line(desc_eval))

        if (contents := self.contents):
            if (conformat := self.attributes.get_value('CONFORMAT')):
                contents_objids = ' '.join([con.objid for con in contents])
                result = parser.evaluate(conformat, executor=self, number_args=(contents_objids,))
                out.add(fmt.Line(result))
            else:
                con = [MudText("Contents:")]
                for obj in contents:
                    con.append(f" * " + send_menu(ansi_fun('hw', obj.name), [(f'look {obj.name}', 'Look')]) + f" ({obj.dbref})")
                out.add(fmt.Line(MudText('\n').join(con)))

        if (contents := self.namespaces['EXIT']):
            if (conformat := self.attributes.get_value('EXITFORMAT')):
                contents_objids = ' '.join([con.objid for con in contents])
                result = parser.evaluate(conformat, executor=self, number_args=(contents_objids,))
                out.add(fmt.Line(result))
            else:
                con = [MudText("Exits:")]
                for obj in contents:
                    con.append(f" * " + send_menu(ansi_fun('hw', obj.name), [(f'look {obj.name}', 'Look')]) + f" ({obj.dbref})")
                out.add(fmt.Line(MudText('\n').join(con)))

        viewer.send(out)

    def find_cmd(self, entry: "QueueEntry", cmd_text: str):
        for matcher_name in self.cmd_matchers:
            matchers = self.game.command_matchers.get(matcher_name, None)
            if matchers:
                for matcher in matchers:
                    if matcher and matcher.access(entry):
                        cmd = matcher.match(entry, cmd_text)
                        if cmd:
                            return cmd

    def gather_help(self, entry: "QueueEntry", data):
        for matcher_name in self.cmd_matchers:
            matchers = self.game.command_matchers.get(matcher_name, None)
            if matchers:
                for matcher in matchers:
                    if matcher and matcher.access(entry):
                        matcher.populate_help(entry, data)

    def move_to(self, destination: Optional[Union["GameObject", str, OLD_TEXT, int]]):
        """
        Placeholder method for eventual version that calls hooks.
        """

        current_location = self.location
        if destination is not None:
            orig = destination
            destination = self.game.resolve_object(destination)
            if not destination:
                raise ValueError(f"Cannot resolve {orig} to a GameObject!")

        if current_location:
            pass

        if destination:
            pass

        self.location = destination

    def update(self, delta: float):
        pass

    def setup(self):
        pass
