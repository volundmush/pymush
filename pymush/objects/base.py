import sys
import weakref

from collections import defaultdict, OrderedDict
from typing import Union, Set, Optional, List, Dict, Tuple, Iterable

from athanor.utils import lazy_property, partial_match

from mudrich.text import Text
from mudrich.encodings.pennmush import ansi_fun, send_menu

from pymush.utils import formatter as fmt
from pymush.utils.styling import StyleHandler
from pymush.db.base import GameObjectKey
from pymush.db import exceptions as ex
from pymush.task import BreakTaskException


class GameObject:
    """
    The GameObject is the basic building block of the game database. This class is just a stub wrapper
    around the database though. It's not meant to store very much.
    """

    __slots__ = ['game', 'key', 'session', 'cpu_quota', '_pid', 'style_holder']

    def __init__(self, game, key: GameObjectKey):
        # has ref back to the game service for API calls.
        self.game = game
        self.key = key

        # Some objects can have sessions attached.
        self.session: Optional["GameSession"] = None
        self.cpu_quota: float = 0.0

        # Used to store default colors and display formats for various things.
        self.style_holder: Optional[StyleHandler] = None

        # queue-relevant data
        self._pid: int = 0

    @property
    def db(self):
        return self.game.db

    def start(self):
        pass

    def db_check(func):
        async def wrapper(*args, **kwargs):
            self = args[0]
            e = self.db.ex_database_unavailable
            try:
                return await func(*args, **kwargs)
            except e as dbu:
                raise BreakTaskException("database unavailable")
            except ex.ObjectDoesNotExist as err:
                raise BreakTaskException("object does not exist")
        return wrapper

    @property
    def objid(self):
        return self.key.objid

    @property
    def uuid(self):
        return self.key.uuid

    async def _get_data(self):
        result = await self.db.get_object(self.key)
        if result.error:
            raise ex.ObjectDoesNotExist()
        return result.data

    @db_check
    async def get_name(self) -> Text:
        data = await self._get_data()
        return data['name_text']

    @db_check
    async def get_created(self) -> Text:
        data = await self._get_data()
        return data['created']

    @db_check
    async def get_modified(self) -> Text:
        data = await self._get_data()
        return data['modified']

    @db_check
    async def get_user(self) -> Text:
        data = await self._get_data()
        return data['user']

    @db_check
    async def get_admin_level(self) -> Text:
        data = await self._get_data()
        return data['admin_level']

    @db_check
    async def get_quota_cost(self) -> Text:
        data = await self._get_data()
        return data['quota_cost']

    @db_check
    async def get_userdata(self) -> Text:
        data = await self._get_data()
        return data['userdata']

    def __repr__(self):
        return f"<{self.__class__.__name__} : {self.objid}>"

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
            total_candidates = [
                x for x in total_candidates if await self.can_perceive(entry, x)
            ]

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
            contents := [
                x
                for x in self.contents
                if x.active() and await viewer.can_perceive(entry, x)
            ]
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
            contents := [
                x
                for x in self.namespaces["EXIT"]
                if x.active() and await viewer.can_perceive(entry, x)
            ]
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

    async def move_to(
        self,
        entry: "TaskEntry",
        destination: Optional[Union["GameObject", str, Text, int]],
    ):
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
                out.update(self.location.namespaces["EXIT"])
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
                    self._queue.put_nowait((50, entry.pid))
                    elapsed.add(entry)
            self.wait_queue -= elapsed

    async def run_task(self, task):
        try:
            if (entry := self.queue_data.pop(task, None)) :
                self.entry = entry
                await entry.execute()
        except Exception as e:
            self.game.app.console.print_exception()
        finally:
            self.entry = None

    async def handle_msg(
        self, msg: Union["GameMsg", "SessionMsg"], priority: int = 0, **kwargs
    ):
        task = self.game.app.classes["game"]["taskentry"](self, msg, **kwargs)
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

    async def print_debug_eval_enter(
        self, entry: "TaskEntry", text: Text, bonus_depth: int = 0
    ):
        spaces = " " * (entry.recursion_count + bonus_depth)
        to_send = f"{entry.executor.dbref}" + "!" + spaces + text + " :"
        self.msg(text=to_send)

    async def print_debug_eval_result(
        self, entry: "TaskEntry", text: Text, result: Text, bonus_depth: int = 0
    ):
        spaces = " " * (entry.recursion_count + 1 + bonus_depth)
        to_send = f"{entry.executor.dbref}" + "!" + spaces + text + " => " + result
        self.msg(text=to_send)
