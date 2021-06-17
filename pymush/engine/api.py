from typing import Union, List, Tuple, Dict

from mudrich.text import Text
from pymush.db.attributes import AttributeRequestType, AttributeRequest


class BaseApi:
    @property
    def parser(self):
        return self.entry.parser

    @property
    def game(self):
        return self.entry.game

    @property
    def executor(self):
        return self.entry.executor

    @property
    def enactor(self):
        return self.entry.enactor

    @property
    def caller(self):
        return self.entry.caller

    @property
    def session(self):
        return self.entry.session

    @property
    def connection(self):
        return self.entry.connection

    def send(self, *args, **kwargs):
        self.executor.send(*args, **kwargs)

    def msg(self, text=None, **kwargs):
        self.executor.msg(text=text, **kwargs)

    async def split_cmd_args(self, text: Union[str, Text]):
        escaped = False
        curly_depth = 0
        i = 0
        start_segment = i
        plain = text.plain if isinstance(text, Text) else text

        while i < len(plain):
            if escaped:
                escaped = False
            else:
                c = plain[i]
                if c == "{":
                    curly_depth += 1
                elif c == "}" and curly_depth:
                    curly_depth -= 1
                elif c == "\\":
                    escaped = True
                elif c == ",":
                    yield await self.parser.evaluate(
                        text[start_segment:i], no_eval=True
                    )
                    start_segment = i + 1
            i += 1

        if i > start_segment:
            yield await self.parser.evaluate(text[start_segment:i], no_eval=True)

    async def split_by(self, text: Union[str, Text], delim: Union[str, Text] = " "):
        plain = text.plain if isinstance(text, Text) else text
        delim = delim.plain if isinstance(delim, Text) else delim

        i = self.parser.find_notspace(plain, 0)
        start_segment = i

        while i < len(plain):
            c = plain[i]
            if c == delim:
                elem = text[start_segment:i]
                if len(elem):
                    elem = await self.parser.evaluate(elem, no_eval=True)
                    if len(elem):
                        yield elem
                start_segment = i
            else:
                pass
            i += 1

        if i > start_segment:
            elem = text[start_segment:i]
            if len(elem):
                elem = await self.parser.evaluate(elem, no_eval=True)
                if len(elem):
                    yield elem

    def eqsplit_args(self, text: Text):
        escaped = False

        plain = text.plain
        paren_depth = 0
        curly_depth = 0
        square_depth = 0
        i = -1

        while True:
            i += 1
            if i > len(plain) - 1:
                return text, Text("")
            c = plain[i]

            if escaped:
                escaped = False
                continue
            else:
                if c == "\\":
                    escaped = True
                elif c == "(":
                    paren_depth += 1
                elif c == ")" and paren_depth:
                    paren_depth -= 1
                elif c == "[":
                    square_depth += 1
                elif c == "]" and square_depth:
                    square_depth -= 1
                elif c == "{":
                    curly_depth += 1
                elif c == "}" and curly_depth:
                    curly_depth -= 1
                elif c == "=":
                    if not (paren_depth or square_depth or curly_depth):
                        lsargs = text[:i].squish_spaces() if i > 0 else Text("")
                        rsargs = text[i + 1 :].squish_spaces()
                        return lsargs, rsargs

    async def target_obj_attr(self, pattern: Text, default=None):
        if default is None:
            default = self.executor

        plain = pattern.plain
        if "/" in plain:
            obj, attr_name = plain.split("/", 1)
            obj = obj.strip()
            if not obj:
                return None, None, "Must enter an Object to search for!"
            results, err = await self.executor.locate_object(
                self.entry, name=obj, first_only=True
            )
            if results:
                obj = results[0]
            else:
                return None, None, err
            attr_name = attr_name.strip()
        else:
            obj = default
            attr_name = plain.strip()
        if not attr_name:
            return None, None, "Must enter an attribute to search for!"
        return obj, attr_name, None

    async def get_attr(self, obj: "GameObject", attr_name):
        req = AttributeRequest(
            accessor=self.executor,
            req_type=AttributeRequestType.GET,
            name=attr_name,
            entry=self.entry,
        )
        await obj.attributes.api_request(req)
        return req

    async def set_attr(self, obj: "GameObject", attr_name, attr_value):
        req = AttributeRequest(
            accessor=self.executor,
            req_type=AttributeRequestType.SET,
            name=attr_name,
            entry=self.entry,
            value=attr_value,
        )
        await obj.attributes.api_request(req)
        return req
