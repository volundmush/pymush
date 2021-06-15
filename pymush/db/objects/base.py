import sys
import weakref
import asyncio

from collections import defaultdict, OrderedDict
from typing import Union, Set, Optional, List, Dict, Tuple, Iterable

from athanor.utils import lazy_property, partial_match
from athanor.tasks import TaskMaster

from mudrich.text import Text
from mudrich.encodings.pennmush import ansi_fun, send_menu

from pymush.utils import formatter as fmt
from pymush.utils.styling import StyleHandler


class GameObject(TaskMaster):
    type_name = None
    unique_names = False
    cmd_matchers = ("basic",)
    is_root_owner = False
    can_be_zone = False
    can_be_destination = False
    can_have_destination = False
    can_be_puppet = False
    no_location = False
    ignore_sessionless = False

    def __init__(self, game: "GameService", dbid: int, created: int, name: str):
        TaskMaster.__init__(self)
        self.game = game
        self.dbid = dbid
        self.created: int = created
        self.modified: int = created
        self._name = sys.intern(name)
        self.aliases: List[str] = list()
        self._parent: Optional[GameObject] = None
        self._parent_of: weakref.WeakValueDictionary[
            str, GameObject
        ] = weakref.WeakValueDictionary()
        self._zone: Optional[GameObject] = None
        self._zone_of: weakref.WeakValueDictionary[
            str, GameObject
        ] = weakref.WeakValueDictionary()
        self._owner: Optional[GameObject] = None
        self._owner_of: weakref.WeakValueDictionary[
            str, GameObject
        ] = weakref.WeakValueDictionary()
        self._owner_of_type: Dict[str, weakref.WeakValueDictionary] = defaultdict(
            weakref.WeakValueDictionary
        )
        self.namespaces: Dict[str, weakref.WeakSet] = defaultdict(weakref.WeakSet)
        self._namespace: Optional[GameObject] = None
        self.session: Optional["GameSession"] = None
        self.account_sessions: Set["GameSession"] = weakref.WeakSet()
        self.connections: Set["Connection"] = set()
        self.attributes = game.app.classes["game"]["attributehandler"](
            self, self.game.attributes
        )
        self.sys_attributes = dict()
        self._location: Optional[GameObject] = None
        self._location_of: weakref.WeakValueDictionary[
            str, GameObject
        ] = weakref.WeakValueDictionary()
        self._destination: Optional[GameObject] = None
        self.db_quota: int = 0
        self.cpu_quota: float = 0.0
        self._admin_level: Optional[int] = None
        self.style_holder: Optional[StyleHandler] = None

        # queue-relevant data
        self.queue_data: OrderedDict[int, "TaskEntry"] = OrderedDict()
        self.wait_queue: Set["TaskEntry"] = set()
        self._pid: int = 0

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
    def name(self, value: Union[str, Text]):
        plain = value.plain if isinstance(value, Text) else value
        plain = plain.strip()
        if not self.game.app.config.regex["basic_name"].match(plain):
            raise ValueError("Name contains invalid characters!")
        if self.unique_names:
            found, err = self.game.search_objects(
                plain, self.game.type_index[self.type_name], exact=True, aliases=True
            )
            if found and found != self:
                raise ValueError("Name conflict within TYPE detected!")
        if self.namespace:
            found, err = self.game.search_objects(
                plain,
                self.namespace.namespaces[self.type_name],
                exact=True,
                aliases=True,
            )
            if found and found != self:
                raise ValueError(
                    f"Name conflict within namespace {self.objid}-{self.type_name} detected!"
                )
        self._name = sys.intern(plain)

    @property
    def owner(self):
        return self._owner

    @owner.setter
    def owner(self, value: Optional[Union["GameObject", str, Text, int]]):
        if self.is_root_owner:
            raise ValueError(
                f"A {self.type_name} cannot be owned by anything! It is a root owner!"
            )
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
            self._owner = (
                weakref.proxy(found)
                if not isinstance(found, weakref.ProxyType)
                else found
            )
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
    def zone(self, value: Optional[Union["GameObject", str, Text, int]]):
        if self.can_be_zone:
            raise ValueError(
                f"{self.objid} cannot be assigned to a Zone as it is a zone candidate!"
            )
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
                raise ValueError(
                    f"That would create a circular relationship! Cannot be your own grandpa!"
                )
            if old and found != old:
                del old._zone_of[self.objid]
            found._zone_of[self.objid] = self
            self._zone = (
                weakref.proxy(found)
                if not isinstance(found, weakref.ProxyType)
                else found
            )
        else:
            if old:
                del old._zone_of[self.objid]
            self._zone = None

    def gather_zones(
        self, max_zones: Optional[int] = None, max_depth: Optional[int] = None
    ):
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
    def parent(self, value: Optional[Union["GameObject", str, Text, int]]):
        old = self._parent
        if value is not None:
            found = self.game.resolve_object(value)
            if not found:
                raise ValueError(f"Cannot resolve {value} to a GameObject!")
            if found == self:
                raise ValueError(f"{self.objid} cannot be its own parent!")
            if self.objid in found.descendants:
                raise ValueError(
                    f"That would create a circular relationship! Cannot be your own grandpa!"
                )
            if old and found != old:
                del old._parent_of[self.objid]
            found._parent_of[self.objid] = self
            self._parent = (
                weakref.proxy(found)
                if not isinstance(found, weakref.ProxyType)
                else found
            )
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
    def location(self, value: Optional[Union["GameObject", str, Text, int]]):
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
            self._location = (
                weakref.proxy(found)
                if not isinstance(found, weakref.ProxyType)
                else found
            )
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
    def namespace(self, value: Optional[Union["GameObject", str, Text, int]]):
        old = self._namespace
        if value is not None:
            found = self.game.resolve_object(value)
            if not found:
                raise ValueError(f"Cannot resolve {value} to a GameObject!")
            if found == self:
                raise ValueError(f"{self.objid} cannot own itself!")
            if found == old:
                return
            obj, err = self.game.search_objects(
                self.name, found.namespaces[self.type_name], exact=True, aliases=True
            )
            if obj and obj != self:
                raise ValueError(
                    f"Name conflict within namespace {found.objid}-{self.type_name} detected!"
                )

            if old and found != old:
                old.namespaces[self.type_name].remove(self)
            found.namespaces[self.type_name].add(self)
            self._namespace = (
                weakref.proxy(found)
                if not isinstance(found, weakref.ProxyType)
                else found
            )
        else:
            if old:
                old.namespaces[self.type_name].remove(self)
            self._namespace = None

    @property
    def destination(self):
        return self._destination

    @destination.setter
    def destination(self, value: Optional[Union["GameObject", str, Text, int]]):
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
            self._destination = (
                weakref.proxy(found)
                if not isinstance(found, weakref.ProxyType)
                else found
            )
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
            "type_name": self.type_name,
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

    def can_receive_text(self, entry: "TaskEntry", sender: "GameObject", text: Text, **kwargs) -> Tuple[bool, Optional[str]]:
        """
        Called by most @*emit commands and *emit() functions to check if sender can speak with this Object.

        Overload this to implement permissions checks.

        Args:
            entry (TaskEntry): The TaskEntry object of the moment.
            sender (GameObject): The sender of the message.
            text (Text): The Text object that sender wishes self to receive.
            **kwargs: Arbitrary data for overloading.

        Returns:
            yes_or_no: bool, err: str or None
        """
        return True, None

    def receive_text(self, entry: "TaskEntry", sender: "GameObject", text: Text, **kwargs):
        """
        Called by most @*emit commands and *emit() functions to handling receiving a message from sender.

        Overload this to implement LISTEN and similar MUSH features. Firing off events when <self> receives
        specific text patterns.

        Args:
            entry (TaskEntry): The TaskEntry object of the moment.
            sender (GameObject): The sender of the message.
            text (Text): The Text object that sender wishes self to receive.
            **kwargs: Arbitrary data for overloading.
        """
        flist = fmt.FormatList(sender, **kwargs)
        flist.add(fmt.Line(text))
        self.send(flist)

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

    @property
    def alevel(self):
        real_level = self._admin_level
        if real_level is None:
            return self.game.alevel_of(self.type_name)
        return real_level

    @alevel.setter
    def alevel(self, value: Optional[int]):
        self._admin_level = value

    def get_alevel(self, ignore_fake=False):
        if self.session:
            return self.session.get_alevel(ignore_fake=ignore_fake)

        if self.owner:
            return self.root_owner.alevel
        else:
            return self.alevel

    def get_dub(self, target):
        dubs = self.sys_attributes.get("dubs", dict())
        return dubs.get(target.objid, None)

    def set_sub(self, target, value: str):
        dubs = self.sys_attributes.get("dubs", dict())
        if value:
            dubs[target.objid] = value
        else:
            dubs.pop(target.objid, None)
        self.sys_attributes["dubs"] = dubs

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

    async def locate_object(
        self,
        entry: "TaskEntry",
        name: Union[str, Text],
        general=True,
        dbref=True,
        location=True,
        contents=True,
        candidates=None,
        use_names=True,
        use_nicks=True,
        use_aliases=True,
        use_dub=True,
        exact=False,
        first_only=False,
        multi_match=False,
        filter_visible=True,
        include_inactive=False,
    ):
        if isinstance(name, Text):
            name = name.plain
        name = name.strip()
        nlower = name.lower()
        out = list()

        loc = None
        if location is True:
            loc = self.location
        elif location:
            loc = location

        if general:
            dict_check = {"self": self, "me": self, "here": loc}

            if (found := dict_check.get(nlower, None)) :
                out.append(found)
                return out, None

        if dbref and name.startswith("#"):
            found, err = self.game.locate_dbref(name)
            if found:
                out.append(found)
                return out, None
            else:
                return None, err

        quant = None
        if multi_match and "|" in name:
            quant_str, name = name.split("|", 1)
            quant_str = quant_str.strip().lower()
            if quant_str == "all":
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

        total_candidates = list(total_candidates)

        if not include_inactive:
            total_candidates = filter(lambda x: x.active(), total_candidates)

        if filter_visible:
            total_candidates = [x for x in total_candidates if await self.can_perceive(entry, x)]

        keywords = defaultdict(list)
        full_names = defaultdict(list)

        simple_words = ("the", "of", "an", "a", "or", "and")

        for can in total_candidates:
            whole, words = self.generate_identifiers_for(
                can, names=use_names, aliases=use_aliases, nicks=use_nicks
            )
            for word in words:
                ilower = word.lower()
                if ilower in simple_words:
                    continue
                keywords[ilower].append(can)
            for n in whole:
                full_names[n.lower()].append(can)

        nlower = name.lower()
        if exact:
            if (found := full_names.get(nlower, None)) :
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

    async def can_perceive(self, entry: "TaskEntry", target: "GameObject"):
        return True

    async def can_interact_with(self, entry: "TaskEntry", target: "GameObject"):
        return True

    async def render_appearance(
        self, entry: "TaskEntry", viewer: "GameObject", internal=False
    ):
        parser = entry.parser
        out = fmt.FormatList(viewer)

        see_dbrefs = viewer.session.admin if viewer.session else True

        def format_name(obj, cmd=None):
            name = viewer.get_dub_or_keyphrase_for(obj)
            display = ansi_fun("hw", name)
            if cmd:
                display = send_menu(display, [(f"{cmd} {name}", cmd)])
            if see_dbrefs:
                display += f" ({obj.dbref})"
            return display

        if (nameformat := self.attributes.get_value("NAMEFORMAT")) :
            result = await parser.evaluate(
                nameformat, executor=self, number_args={0: self.objid, 1: self.name}
            )
            out.add(fmt.Line(result))
        else:
            out.add(fmt.Line(format_name(self)))

        if internal and (idesc := self.attributes.get_value("IDESCRIBE")):
            idesc_eval = await parser.evaluate(idesc, executor=self)
            if (idescformat := self.attributes.get_value("IDESCFORMAT")) :
                result = await parser.evaluate(
                    idescformat, executor=self, number_args=(idesc_eval,)
                )
                out.add(fmt.Line(result))
            else:
                out.add(fmt.Line(idesc_eval))

        elif (desc := self.attributes.get_value("DESCRIBE")) :
            try:
                desc_eval = await parser.evaluate(desc, executor=self)
            except Exception as err:
                import sys, traceback
                traceback.print_exc(file=sys.stdout)
            if (descformat := self.attributes.get_value("DESCFORMAT")) :
                result = await parser.evaluate(
                    descformat, executor=self, number_args=(desc_eval,)
                )
                out.add(fmt.Line(result))
            else:
                out.add(fmt.Line(desc_eval))

        if (
            contents := [x for x in self.contents if x.active() and await viewer.can_perceive(entry, x)]
        ) :
            contents = sorted(
                contents, key=lambda x: viewer.get_dub_or_keyphrase_for(x)
            )
            if contents:
                if (conformat := self.attributes.get_value("CONFORMAT")) :
                    contents_objids = " ".join([con.objid for con in contents])
                    result = await parser.evaluate(
                        conformat, executor=self, number_args=(contents_objids,)
                    )
                    out.add(fmt.Line(result))
                else:
                    if viewer in contents:
                        contents.remove(viewer)
                    if contents:
                        con = [Text("Contents:")]
                        for obj in contents:
                            con.append(f" * " + format_name(obj, "look"))
                        out.add(fmt.Line(Text("\n").join(con)))

        if (
            contents := [x for x in self.namespaces['EXIT'] if x.active() and await viewer.can_perceive(entry, x)]
        ) :
            contents = sorted(
                contents, key=lambda x: viewer.get_dub_or_keyphrase_for(x)
            )
            if contents:
                if (conformat := self.attributes.get_value("EXITFORMAT")) :
                    contents_objids = " ".join([con.objid for con in contents])
                    result = await parser.evaluate(
                        conformat, executor=self, number_args=(contents_objids,)
                    )
                    out.add(fmt.Line(result))
                else:
                    con = [Text("Exits:")]
                    for obj in contents:
                        con.append(f" * " + format_name(obj, "goto"))
                    out.add(fmt.Line(Text("\n").join(con)))

        viewer.send(out)

    async def find_cmd(self, entry: "TaskEntry", cmd_text: Text):
        for matcher_name in self.cmd_matchers:
            matchers = self.game.command_matchers.get(matcher_name, None)
            if matchers:
                for matcher in matchers:
                    if matcher and await matcher.access(entry):
                        cmd = await matcher.match(entry, cmd_text)
                        if cmd:
                            return cmd

    async def gather_help(self, entry: "TaskEntry", data):
        for matcher_name in self.cmd_matchers:
            matchers = self.game.command_matchers.get(matcher_name, None)
            if matchers:
                for matcher in matchers:
                    if matcher and await matcher.access(entry):
                        await matcher.populate_help(entry, data)

    async def move_to(self, entry: "TaskEntry", destination: Optional[Union["GameObject", str, Text, int]]):
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

    def setup(self):
        pass

    def active(self):
        return True

    def neighbors(self, include_exits=False) -> Iterable["GameObject"]:
        out = weakref.WeakSet()
        if self.location:
            out.update(self.location.contents)
            if include_exits:
                out.update(self.location.namespaces['EXIT'])
        out.remove(self)
        return out

    async def announce_login(self, from_linkdead: bool = False):
        if from_linkdead:
            self.msg(Text("You return from link-dead!"))
            to_send = Text(" is no longer link-dead!")
            for neighbor in self.neighbors():
                neighbor.msg(neighbor.get_dub_or_keyphrase_for(self) + to_send)
        else:
            self.msg(Text("You have entered the game."))
            to_send = Text(" has entered the game!")
            for neighbor in self.neighbors():
                neighbor.msg(neighbor.get_dub_or_keyphrase_for(self) + to_send)

    async def announce_linkdead(self):
        to_send = Text(" has gone link-dead!")
        for neighbor in self.neighbors():
            neighbor.msg(neighbor.get_dub_or_keyphrase_for(self) + to_send)

    async def announce_logout(self, from_linkdead: bool = False):
        if from_linkdead:
            to_send = Text(" has been idled-out due to link-deadedness!")
            for neighbor in self.neighbors():
                neighbor.msg(neighbor.get_dub_or_keyphrase_for(self) + to_send)
        else:
            self.msg(Text("You have left the game."))
            to_send = Text(" has left the game!")
            for neighbor in self.neighbors():
                neighbor.msg(neighbor.get_dub_or_keyphrase_for(self) + to_send)

    def update(self, now: float, delta: float):
        self.queue_elapsed(now, delta)

    def queue_elapsed(self, now: float, delta: float):
        if self.wait_queue:
            elapsed = set()
            for entry in self.wait_queue:
                if (now - entry.created) > entry.wait:
                    self.queue.put_nowait((50, entry.pid))
                    elapsed.add(entry)
            self.wait_queue -= elapsed

    async def run_task(self, task):
        try:
            if (entry := self.queue_data.pop(task, None)):
                self.entry = entry
                await entry.execute()
        except Exception as e:
            self.game.app.console.print_exception()
        finally:
            self.entry = None

    async def handle_msg(self, msg: Union["GameMsg", "SessionMsg"], priority: int = 0, **kwargs):
        task = self.game.app.classes['game']['taskentry'](self, msg, **kwargs)
        await self.schedule_task(task, priority=priority)

    async def schedule_task(self, task, priority: int = 0):
        self._pid += 1
        task.pid = self._pid
        self.queue_data[self._pid] = task
        await self._queue.put((priority, self._pid))

    async def controls(self, entry: "TaskEntry", target: "GameObject"):
        return target == self

    async def see_debug(self, entry: "TaskEntry"):
        return True

    async def print_debug_cmd(self, entry: "TaskEntry", action: Text):
        to_send = f"{entry.executor.dbref}" + "-" * entry.inline_depth + "] " + action
        self.msg(text=to_send)

    async def print_debug_eval_enter(self, entry: "TaskEntry", text: Text, bonus_depth : int = 0):
        spaces = " " * (entry.recursion_count+bonus_depth)
        to_send = f"{entry.executor.dbref}" + "!" + spaces + text + " :"
        self.msg(text=to_send)

    async def print_debug_eval_result(self, entry: "TaskEntry", text: Text, result: Text, bonus_depth : int = 0):
        spaces = " " * (entry.recursion_count+1+bonus_depth)
        to_send = f"{entry.executor.dbref}" + "!" + spaces + text + " => " + result
        self.msg(text=to_send)