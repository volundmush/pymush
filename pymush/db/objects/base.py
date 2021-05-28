import sys
from typing import Union, Set, Optional, List, Dict, Tuple, Iterable
from athanor.utils import lazy_property, partial_match
from pymush.db.attributes import AttributeHandler
from athanor.shared import ConnectionOutMessage, ConnectionOutMessageType, ConnectionInMessageType, ConnectionInMessage
from pymush.utils import formatter as fmt
from pymush.utils.styling import StyleHandler
from collections import defaultdict
from mudstring.patches.text import MudText
from mudstring.encodings.pennmush import ansi_fun, send_menu
import re
import weakref


class NameSpace:

    def __init__(self, owner: "GameObject", name: str):
        self.owner = owner
        self.name = name
        self.objects: Dict[str, "GameObject"] = dict()

    def serialize(self) -> Dict:
        return dict()


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
    def __init__(self, owner):
        self.owner = owner
        self.inventories = defaultdict(Inventory)
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
    re_search = re.compile(r"(?i)^(?P<pre>(?P<quant>all|\d+)\.)?(?P<target>[A-Z0-9_.-]+)")
    cmd_matchers = ('script',)


    __slots__ = ["service", "dbid", "dbref", "name", "parent", "parent_of", "home", "home_of", "db_quota", "cpu_quota",
                 "zone", "zone_of", "owner", "owner_of", "namespaces", "namespace", "session", "connections",
                 "admin_level", "attributes", "sys_attributes", "location", "contents", "aliases", "created",
                 "modified", "style_holder", "account_sessions", "saved_locations", "destination"]

    def __init__(self, service: "GameService", dbref: int, name: str):
        self.service = service
        self.dbid = dbref
        self.dbref = f"#{dbref}"
        self.created: int = 0
        self.modified: int = 0
        self.name = sys.intern(name)
        self.aliases: List[str] = list()
        self.owner: Optional["GameObject"] = None
        self.parent: Optional[GameObject] = None
        self.parent_of: Set[GameObject] = set()
        self.home: Optional[GameObject] = None
        self.home_of: Set[GameObject] = set()
        self.zone: Optional[GameObject] = None
        self.zone_of: Set[GameObject] = set()
        self.owner: Optional[GameObject] = None
        self.owner_of: Set[GameObject] = set()
        self.namespaces: Dict[str, NameSpace] = dict()
        self.namespace: Optional[Tuple[GameObject, str]] = None
        self.session: Optional["GameSession"] = None
        self.account_sessions: Set["GameSession"] = set()
        self.connections: Set["Connection"] = set()
        self.attributes = AttributeHandler(self, self.service.attributes)
        self.sys_attributes = dict()
        self.location: Optional[Tuple[GameObject, str, Optional[Union[Tuple[int, ...], Tuple[float, ...]]]]] = None
        self.destination: Optional[Tuple[GameObject, str, Optional[Union[Tuple[int, ...], Tuple[float, ...]]]]] = None
        self.contents: ContentsHandler = ContentsHandler(self)
        self.db_quota: int = 0
        self.cpu_quota: float = 0.0
        self.admin_level: int = 0
        self.style_holder: Optional[StyleHandler] = None
        self.saved_locations: dict = dict()

    def __hash__(self):
        return hash(self.dbid)

    def get_saved_location(self, name: str):
        if name in self.saved_locations:
            loc = self.saved_locations[name]
            if loc[0]:
                return loc
            else:
                del self.saved_locations[name]

    def set_saved_location(self, name: str, location):
        self.saved_locations[name] = (weakref.proxy(location[0]), location[1], location[2])

    @property
    def style(self):
        if self.session:
            return self.session.style
        if not self.style_holder:
            self.style_holder = StyleHandler(self, save=True)
        return self.style_holder

    @property
    def game(self):
        return self.service

    def __int__(self):
        return self.dbid

    def __repr__(self):
        return f"<{self.__class__.__name__} {self.dbid}: {self.name}>"

    def serialize(self) -> Dict:
        out: Dict = {
            "dbid": self.dbid,
            "name": self.name,
            "type_name": self.type_name
        }
        if self.parent:
            out["parent"] = self.parent.dbid

        if self.namespaces:
            n_dict = dict()
            for k, n in self.namespaces.items():
                n_dict[k] = n.serialize()
            out["namespaces"] = n_dict

        if self.namespace:
            out["namespace"] = [self.namespace[0].dbid, self.namespace[1]]

        if self.attributes.count():
            out["attributes"] = self.attributes.serialize()

        if self.sys_attributes:
            out["sys_attributes"] = self.sys_attributes

        if self.location and self.location[0]:
            out["location"] = (self.location[0].dbid, self.location[1], self.location[2])

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

    def generate_identifers_name_for(self, viewer):
        return self.name

    def get_keyphrase_for(self, viewer):
        return self.name

    def get_dub_or_keyphrase_for(self, viewer):
        dubbed = viewer.get_dub(self)
        if dubbed:
            return dubbed
        return self.get_keyphrase_for(viewer)

    def generate_identifiers_for(self, viewer, names=True, aliases=True, nicks=True):
        whole, words = list(), list()
        if names:
            identifiers = self.generate_identifers_name_for(viewer)
            whole.append(identifiers)
            words.extend(identifiers.split())
        if aliases:
            for alias in self.aliases:
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
            loc = self.location[0] if self.location else None
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
            total_candidates.update(loc.contents.all())
        if contents:
            total_candidates.update(self.contents.all())
        if self in total_candidates:
            total_candidates.remove(self)

        if filter_visible:
            total_candidates = [c for c in total_candidates if self.can_see(c)]
        else:
            total_candidates = list(total_candidates)

        keywords = defaultdict(list)
        full_names = defaultdict(list)

        for can in total_candidates:
            whole, words = can.generate_identifiers_for(self, names=use_names, aliases=use_aliases, nicks=use_nicks)
            for word in words:
                ilower = word.lower()
                if ilower in ('the', 'of', 'an', 'a', 'or', 'and'):
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

    def can_see(self, target: "GameObject"):
        return True
    
    def render_appearance(self, viewer, parser, internal=False):
        out = fmt.FormatList(viewer)
        if (nameformat := self.attributes.get_value('NAMEFORMAT')):
            result = parser.evaluate(nameformat, executor=self, number_args={0: self.dbref, 1: self.name})
            out.add(fmt.Line(result))
        else:
            out.add(fmt.Line(ansi_fun('hw', self.name) + f" ({self.dbref})"))
        if internal and (idesc := self.attributes.get_value('IDESCRIBE')):
            idesc_eval = parser.evaluate(idesc, executor=self)
            if (idescformat := self.attributes.get_value('IDESCFORMAT')):
                result = parser.evaluate(idescformat, executor=self, number_args={0: idesc_eval})
                out.add(fmt.Line(result))
            else:
                out.add(fmt.Line(idesc_eval))
        elif (desc := self.attributes.get_value('DESCRIBE')):
            desc_eval = parser.evaluate(desc, executor=self)
            if (descformat := self.attributes.get_value('DESCFORMAT')):
                result = parser.evaluate(descformat, executor=self, number_args={0: desc_eval})
                out.add(fmt.Line(result))
            else:
                out.add(fmt.Line(desc_eval))
        if (contents := self.contents.all()):
            if (conformat := self.attributes.get_value('CONFORMAT')):
                contents_objids = ' '.join([con.objid for con in contents])
                result = parser.evaluate(conformat, executor=self, number_args={0: contents_objids})
                out.add(fmt.Line(result))
            else:
                con = [MudText("Contents:")]
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

    def move_to(self, location: Optional["GameObject"], inventory: str = '',
                coordinates: Optional[Union[Tuple[int, ...], Tuple[float, ...]]] = None):

        current_location = self.location[0] if self.location else None

        if current_location:
            current_location.contents.remove(self)

        if location:
            location.contents.add(inventory, self, coordinates)

        else:
            self.location = None
