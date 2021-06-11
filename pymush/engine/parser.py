import re
from typing import Union, Optional
from enum import IntEnum

from rich.text import Text

from pymush.utils.text import find_notspace, find_matching

from .functions.base import NotFound as NotFoundFunction


class MushLex(IntEnum):
    SPAN = 0
    RECURSE = 1
    SUB = 2


class MushSub(IntEnum):
    SPACE = 0
    NEWLINE = 1
    TAB = 2

    ENACTOR_DBREF = 3
    ENACTOR_NAME = 4
    ENACTOR_ACCENTED_NAME = 5
    ENACTOR_OBJID = 6
    ENACTOR_MONIKER = 7

    PERCENT = 9

    SUBJECTIVE_PRONOUN = 10
    OBJECTIVE_PRONOUN = 11
    POSSESSIVE_PRONOUN = 12
    ABSOLUTE_PRONOUN = 13

    NUMBER_ARG_VALUE = 14
    REGISTER_VALUE = 15

    EXECUTOR_DBREF = 16
    ENACTOR_LOCATION_DBREF = 17
    COMMAND_TEXT_NOEVAL = 18
    COMMAND_TEXT_EVALED = 19
    FUNC_INVOKE_AND_DEPTH = 20
    CUR_DBREF_ATTR = 21
    ARG_COUNT = 22
    ITEXT = 23
    STEXT = 24
    DTEXT = 25
    INUM = 26
    DNUM = 27
    CALLER_DBREF = 28


class StackFrame:
    def __init__(self, enactor, executor, caller):
        self.parser = None
        self.parent = None
        self.entry = None
        self.break_after = False
        self.enactor = enactor
        self.executor = executor
        self.caller = caller
        self.dvars = list()
        self.dnum = list()
        self.iter = list()
        self.ivars = list()
        self.inum = list()
        self.number_args = dict()
        self.stext = None

        self.localized = False
        self.vars = dict()
        self.ukeys = dict()

    def localize(self):
        self.localized = True
        # We are localizing this frame, so break the connection to its parent.
        self.vars = dict(self.vars)
        self.ukeys = dict(self.ukeys)

    def inherit(self, from_frame, copy=False):
        if not copy:
            self.vars = from_frame.vars
            self.ukeys = from_frame.ukeys
        else:
            self.vars = dict(from_frame.keys)
            self.ukeys = dict(from_frame.ukeys)

    def get_var(self, key):
        if isinstance(key, int) and key in self.vars:
            return self.vars[key]
        elif isinstance(key, str):
            key = self.ukeys.get(key.upper(), None)
            if key in self.vars:
                return self.vars[key]

    def set_var(self, key, value):
        if isinstance(key, int):
            self.vars[key] = value
        elif isinstance(key, str):
            self.ukeys[key.upper()] = key
            self.vars[key] = value

    def eval_sub(self, subtype: MushSub, data) -> Text:
        if subtype == MushSub.ENACTOR_DBREF:
            if self.enactor:
                return Text(self.enactor.dbref)
        elif subtype == MushSub.ENACTOR_NAME:
            if self.enactor:
                if data:
                    return Text(self.enactor.name.capitalize())
                else:
                    return Text(self.enactor.name)
        elif subtype == MushSub.ENACTOR_OBJID:
            if self.enactor:
                return Text(self.enactor.objid)

        elif subtype == MushSub.CALLER_DBREF:
            if self.caller:
                return Text(self.caller.dbref)

        elif subtype == MushSub.SPACE:
            return Text(" ")
        elif subtype == MushSub.PERCENT:
            return Text("%")
        elif subtype == MushSub.NEWLINE:
            return Text("\n")
        elif subtype == MushSub.TAB:
            return Text("\t")

        elif subtype == MushSub.ENACTOR_LOCATION_DBREF:
            if self.enactor:
                loc = self.enactor.location[0] if self.enactor.location else None
                if loc:
                    return Text(loc.dbref)

        elif subtype == MushSub.NUMBER_ARG_VALUE:
            print(f"NUMBER ARG REQUEST: {data}")
            try:
                return self.number_args[data]
            except KeyError:
                return Text("")

        elif subtype == MushSub.ARG_COUNT:
            return Text(str(len(self.number_args)))

        elif subtype == MushSub.REGISTER_VALUE:
            resp = self.get_var(data)
            if resp:
                return resp

        elif subtype == MushSub.DNUM:
            try:
                val = str(self.dnum[data])
            except IndexError:
                val = Text("#-1 ARGUMENT OUT OF RANGE")
            return val

        elif subtype == MushSub.DTEXT:
            try:
                val = self.dvars[data]
            except IndexError:
                val = Text("#-1 ARGUMENT OUT OF RANGE")
            return val

        elif subtype == MushSub.INUM:
            try:
                val = str(self.inum[data])
            except IndexError:
                val = Text("#-1 ARGUMENT OUT OF RANGE")
            return val

        elif subtype == MushSub.ITEXT:
            try:
                val = self.ivars[data]
            except IndexError:
                val = Text("#-1 ARGUMENT OUT OF RANGE")
            return val

        elif subtype == MushSub.STEXT:
            if self.stext is not None:
                return self.stext
            else:
                return Text("#-1 ARGUMENT OUT OF RANGE")

        return Text("")


class Parser:
    re_func = re.compile(r"^(?P<bangs>!|!!|!\$|!!\$|!\^|!!\^)?(?P<func>\w+)")
    re_number_args = re.compile(r"^%(?P<number>\d+)")
    re_q_reg = re.compile(r"^%q(?P<varname>\d+|[A-Z])", flags=re.IGNORECASE)
    re_q_named = re.compile(r"^%q<(?P<varname>[\w| ]+)>", flags=re.IGNORECASE)
    re_stext = re.compile(r"^%\$(?P<num>\d+)", flags=re.IGNORECASE)
    re_dtext = re.compile(r"^%d(?P<num>\d+)", flags=re.IGNORECASE)
    re_itext = re.compile(r"^%i(?P<num>\d+)", flags=re.IGNORECASE)
    re_dnum = re.compile(r"^%d_(?P<num>\d+)", flags=re.IGNORECASE)
    re_inum = re.compile(r"^%i_(?P<num>\d+)", flags=re.IGNORECASE)
    re_numeric = re.compile(r"^(?P<neg>-)?(?P<value>\d+(?P<dec>\.\d+)?)$")

    def __init__(self, entry, enactor, executor, caller, frame=None):
        self.entry = entry
        self.frame = StackFrame(enactor, executor, caller) if frame is None else frame
        self.frame.parser = self
        self.frame.entry = entry
        self.stack = [self.frame]

    def make_child(self, **kwargs):
        frame = self.make_child_frame(**kwargs)
        out = self.__class__(self.entry, None, None, None, frame=frame)
        return out

    def make_child_frame(
        self,
        localize=False,
        enactor=None,
        executor=None,
        caller=None,
        number_args=None,
        dnum=None,
        dvar=None,
        iter=None,
        inum=None,
        ivar=None,
        stext=None,
    ):
        cur_frame = self.frame
        new_frame = StackFrame(
            enactor if enactor else self.frame.enactor,
            executor if executor else self.frame.executor,
            caller if caller else self.frame.caller,
        )

        if localize:
            new_frame.localized = True
        new_frame.inherit(cur_frame, copy=localize)

        if number_args:
            new_frame.number_args = number_args
        if dnum is not None:
            new_frame.dnum.insert(0, dnum)
            new_frame.dvars.insert(0, dvar)
        if iter is not None:
            new_frame.iter.insert(0, iter)
            new_frame.inum.insert(0, inum)
            new_frame.ivars.insert(0, ivar)
        if stext is not None:
            new_frame.stext = stext
        return new_frame

    def enter_frame(self, **kwargs):
        cur_frame = self.frame
        new_frame = self.make_child_frame(**kwargs)

        new_frame.parent = cur_frame
        new_frame.entry = self.entry
        new_frame.parser = self
        self.stack.append(new_frame)
        self.frame = new_frame

    def exit_frame(self):
        if self.stack:
            self.stack.pop(-1)
            if self.stack:
                self.frame = self.stack[-1]

    def evaluate(
        self,
        text: Union[None, str, Text],
        localize: bool = False,
        called_recursively: bool = False,
        executor: Optional["GameObject"] = None,
        caller: Optional["GameObject"] = None,
        number_args=None,
        no_eval=False,
        iter=None,
        inum=None,
        ivar=None,
        stext=None,
    ):

        if not text:
            return Text("")
        if isinstance(text, str):
            text = Text(text)

        if not no_eval:
            self.entry.recursion_count += 1
            if self.entry.recursion_count >= self.entry.queue.function_recursion_limit:
                return Text("#-1 FUNCTION RECURSION LIMIT EXCEEDED")

            self.enter_frame(
                localize=localize,
                executor=executor,
                caller=caller,
                number_args=number_args,
                iter=iter,
                inum=inum,
                ivar=ivar,
                stext=stext,
            )

        output = Text("")

        plain = text.plain
        escaped = False

        first_paren = False
        no_hoover = False
        i = find_notspace(plain, 0)
        segment_start = i
        if i is not None:
            while i < len(plain):
                if escaped:
                    escaped = False
                    segment_start = i
                    i += 1
                else:
                    c = plain[i]
                    if c == "\\" and not no_eval:
                        escaped = True
                        if i > segment_start:
                            output += text[segment_start:i]
                        i += 1
                    elif c == " ":
                        notspace = find_notspace(plain, i)
                        if notspace is not None:
                            if i > segment_start:
                                output += text[segment_start:i]
                            if output.plain:
                                output += " "
                            i = notspace
                            segment_start = i
                        else:
                            if i > segment_start:
                                output += text[segment_start:i]
                            no_hoover = True
                            break
                    elif c == "[" and not no_eval:
                        # This is potentially a recursion. Seek a matching ]
                        closing = find_matching(plain, i, "[", "]")
                        if closing is not None:
                            if i > segment_start:
                                output += text[segment_start:i]
                            output += self.evaluate(
                                text[i + 1 : closing], called_recursively=True
                            )
                            segment_start = closing + 1
                            i = closing + 1
                        else:
                            i += 1
                    elif c == "(" and not no_eval and not first_paren:
                        # this is potentially a function call. Seek a matching )
                        first_paren = True
                        closing = find_matching(plain, i, "(", ")")
                        if closing is not None:
                            if i > segment_start:
                                output += text[segment_start:i]
                            f_match = self.re_func.fullmatch(output.plain)
                            if f_match:
                                fdict = f_match.groupdict()
                                func_name = fdict["func"]
                                bangs = fdict["bangs"]
                                if (
                                    func := self.find_function(
                                        func_name,
                                        default=NotFoundFunction
                                        if called_recursively
                                        else None,
                                    )
                                ) :
                                    # hooray we have a function!
                                    self.entry.function_invocation_count += 1
                                    if (
                                        self.entry.function_invocation_count
                                        >= self.entry.queue.function_invocation_limit
                                    ):
                                        output = Text(
                                            "#-1 FUNCTION INVOCATION LIMIT EXCEEDED"
                                        )
                                        break
                                    else:
                                        ready_fun = func(
                                            self, func_name, text[i + 1 : closing]
                                        )
                                        output = ready_fun.execute()
                                segment_start = closing + 1
                                i = closing + 1
                        else:
                            i += 1
                    elif c == "%" and not no_eval:
                        # this is potentially a substitution.
                        results = self.valid_sub(plain, i)
                        if results:
                            if i > segment_start:
                                output += text[segment_start:i]
                            length, sub = results
                            output += self.frame.eval_sub(sub[0], sub[1])
                            i += length
                            segment_start = i
                        else:
                            if i > segment_start:
                                output += text[segment_start:i]
                            i += 1
                            segment_start = i
                    else:
                        i += 1

            # hoover up any remaining info to be evaluated...
            if not no_hoover:
                if i > segment_start:
                    remaining = text[segment_start:i]
                    output += remaining

        # if we reach down here, then we are doing well and can pop a frame off.
        if not no_eval:
            self.exit_frame()
            self.entry.recursion_count -= 1

        return output

    def valid_sub(self, text: str, start: int):
        simple = text[start : start + 2]
        sub = None
        if simple in ("%R", "%r"):
            sub = (MushSub.NEWLINE, None)
        elif simple in ("%T", "%t"):
            sub = (MushSub.TAB, None)
        elif simple in ("%B", "%b"):
            sub = (MushSub.SPACE, None)
        elif simple == "%#":
            sub = (MushSub.ENACTOR_DBREF, None)
        elif simple == "%%":
            sub = (MushSub.PERCENT, None)
        elif simple == "%:":
            sub = (MushSub.ENACTOR_OBJID, None)
        elif simple == "%@":
            sub = (MushSub.CALLER_DBREF, None)
        elif simple == "%?":
            sub = (MushSub.FUNC_INVOKE_AND_DEPTH, None)
        elif simple == "%+":
            sub = (MushSub.ARG_COUNT, None)
        elif simple == "%!":
            sub = (MushSub.EXECUTOR_DBREF, None)
        elif simple in ("%l", "%L"):
            sub = (MushSub.ENACTOR_LOCATION_DBREF, simple[1].isupper())
        elif simple in ("%n", "%N"):
            sub = (MushSub.ENACTOR_NAME, simple[1].isupper())
        elif simple in ("%s", "%S"):
            sub = (MushSub.SUBJECTIVE_PRONOUN, simple[1].isupper())
        elif simple in ("%p", "%P"):
            sub = (MushSub.POSSESSIVE_PRONOUN, simple[1].isupper())
        elif simple in ("%o", "%O"):
            sub = (MushSub.OBJECTIVE_PRONOUN, simple[1].isupper())
        elif simple in ("%a", "%A"):
            sub = (MushSub.ABSOLUTE_PRONOUN, simple[1].isupper())

        if sub:
            return 2, sub

        t_start = text[start:]

        if (match := self.re_number_args.fullmatch(t_start)) :
            gdict = match.groupdict()
            number = gdict["number"]
            length = len(number)
            number = int(number)
            return 1 + length, (MushSub.NUMBER_ARG_VALUE, number)

        if t_start.lower().startswith("%q"):
            # this is a q-register of some kind.
            gdict = None
            extra = 2
            if (match := self.re_q_reg.match(t_start)) :
                gdict = match.groupdict()
            elif (match := self.re_q_named.match(t_start)) :
                gdict = match.groupdict()
                extra += 2
            if gdict:
                varname = gdict["varname"]
                varlength = len(varname)
                if varname.isdigit():
                    varname = int(varname)
                return extra + varlength, (MushSub.REGISTER_VALUE, varname)

        for code, reg, length in (
            (MushSub.ITEXT, self.re_itext, 2),
            (MushSub.DTEXT, self.re_dtext, 2),
            (MushSub.STEXT, self.re_stext, 2),
            (MushSub.INUM, self.re_inum, 3),
            (MushSub.DNUM, self.re_dnum, 3),
        ):
            if (match := reg.match(t_start)) :
                mdict = match.groupdict()
                number = mdict["num"]
                extra = len(number)
                number = int(number)
                return length + extra, (code, number)

        return None

    def find_function(self, funcname: str, default=None):
        found = self.entry.queue.game.functions.get(funcname.lower(), None)
        return found if found else default
