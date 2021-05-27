from .functions.base import NotFound as NotFoundFunction
from mudstring.patches.text import MudText, OLD_TEXT
import re
from typing import Union, Optional, List, Set, Tuple, Dict
from enum import IntEnum


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
    def __init__(self, parser, parent=None):
        self.parser = parser
        self.parent = parent
        self.enactor = None
        self.spoof = None
        self.executor = None
        self.caller = None
        self.dolist_val = None
        self.iter_val = None
        self.localized = False
        self.number_args = parent.number_args if parent else dict()
        self.vars = parent.vars if parent else dict()
        self.ukeys = parent.ukeys if parent else dict()

    def make_child(self):
        frame = StackFrame(self.parser, parent=self)
        frame.enactor = self.enactor
        frame.spoof = self.spoof
        frame.executor = self.executor
        frame.caller = self.caller
        frame.dolist_val = self.dolist_val
        frame.iter_val = self.iter_val
        return frame

    def localize(self):
        self.localized = True
        # We are localizing this frame, so break the connection to its parent.
        self.vars = dict(self.vars)
        self.ukeys = dict(self.ukeys)


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

    def eval_sub(self, subtype: MushSub, data) -> MudText:
        if subtype == MushSub.ENACTOR_DBREF:
            if self.enactor:
                return MudText(self.enactor.dbref)
        elif subtype == MushSub.ENACTOR_NAME:
            if self.enactor:
                if data:
                    return MudText(self.enactor.name.capitalize())
                else:
                    return MudText(self.enactor.name)
        elif subtype == MushSub.ENACTOR_OBJID:
            if self.enactor:
                return MudText(self.enactor.objid)

        elif subtype == MushSub.CALLER_DBREF:
            if self.caller:
                return MudText(self.caller.dbref)

        elif subtype == MushSub.SPACE:
            return MudText(' ')
        elif subtype == MushSub.PERCENT:
            return MudText("%")
        elif subtype == MushSub.NEWLINE:
            return MudText('\n')
        elif subtype == MushSub.TAB:
            return MudText('\t')

        elif subtype == MushSub.ENACTOR_LOCATION_DBREF:
            if self.enactor:
                loc = self.enactor.location[0] if self.enactor.location else None
                if loc:
                    return MudText(loc.dbref)

        elif subtype == MushSub.NUMBER_ARG_VALUE:
            if data in self.number_args:
                return self.number_args[data]

        elif subtype == MushSub.ARG_COUNT:
            return MudText(str(len(self.number_args)))

        elif subtype == MushSub.REGISTER_VALUE:
            resp = self.get_var(data)
            if resp:
                return resp

        return MudText('')


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

    def __init__(self, entry, enactor, executor, caller):
        self.entry = entry
        self.frame = StackFrame(self)
        self.frame.enactor = enactor
        self.frame.executor = executor
        self.frame.caller = caller
        self.stack = [self.frame]
        self.func_count = 0

    def truthy(self, test_str: Union[str, OLD_TEXT]) -> bool:
        if isinstance(test_str, OLD_TEXT):
            test_str = test_str.plain
        test_str = test_str.strip()
        if not test_str:
            return False
        if test_str.startswith("#-"):
            return False
        number = self.to_number(test_str)
        if number is not None:
            return bool(number)
        return True

    def to_number(self, test_str: Union[str, OLD_TEXT]) -> Optional[Union[int, float]]:
        if isinstance(test_str, OLD_TEXT):
            test_str = test_str.plain
        test_str = test_str.strip()

        if not len(test_str):
            return 0

        try:
            value = None
            match = self.re_numeric.fullmatch(test_str)
            if match:
                mdict = match.groupdict()
                sign = -1 if mdict['neg'] else 1
                if mdict['dec'] is not None:
                    value = float(mdict['value']) * sign
                else:
                    value = int(mdict['value']) * sign
            if value is not None:
                return value
            else:
                return None
        except Exception as e:
            # TODO: Add proper exception value handling
            return None

    def find_matching(self, text: str, start: int, opening: str, closing: str):
        escaped = False
        depth = 0
        i = start
        while i < len(text):
            if escaped:
                pass
            else:
                c = text[i]
                if c == '\\':
                    escaped = True
                elif c == opening:
                    depth += 1
                elif c == closing and depth:
                    depth -= 1
                    if not depth:
                        return i
            i += 1
        return None

    def find_notspace(self, text: str, start: int):
        escaped = False
        i = start
        while i < len(text):
            if escaped:
                pass
            else:
                c = text[i]
                if c == '\\':
                    escaped = True
                elif c == ' ':
                    pass
                else:
                    return i
            i += 1
        return None

    def evaluate(self, text: Union[None, str, OLD_TEXT], localize: bool = False, spoof: Optional["GameObject"] = None,
                  called_recursively: bool = False, executor: Optional["GameObject"] = None,
                  caller: Optional["GameObject"] = None, number_args=None):

        if not text:
            return MudText("")
        if isinstance(text, str):
            text = MudText(text)

        frame = self.frame.make_child()
        self.frame = frame
        if localize:
            frame.localize()
        self.stack.append(frame)

        if number_args:
            self.frame.number_args = number_args
        if executor:
            self.frame.executor = executor
        if spoof:
            self.frame.spoof = spoof
        if caller:
            self.frame.caller = caller

        output = MudText("")

        plain = text.plain
        escaped = False


        first_paren = False
        no_hoover = False
        i = self.find_notspace(plain, 0)
        segment_start = i
        if i is not None:
            while i < len(plain):
                if escaped:
                    i += 1
                else:
                    c = plain[i]
                    if c == '\\':
                        escaped = True
                        i += 1
                    elif c == ' ':
                        notspace = self.find_notspace(plain, i)
                        if notspace is not None:
                            if i > segment_start:
                                output += text[segment_start:i]
                            if output.plain:
                                output += ' '
                            i = notspace
                            segment_start = i
                        else:
                            if i > segment_start:
                                output += text[segment_start:i]
                            no_hoover = True
                            break
                    elif c == '[':
                        # This is potentially a recursion. Seek a matching ]
                        closing = self.find_matching(plain, i, '[', ']')
                        if closing is not None:
                            if i > segment_start:
                                output += text[segment_start:i]
                            output += self.evaluate(text[i+1:closing], called_recursively=True)
                            segment_start = closing+1
                            i = closing+1
                        else:
                            i += 1
                    elif c == '(' and not first_paren:
                        # this is potentially a function call. Seek a matching )
                        first_paren = True
                        closing = self.find_matching(plain, i, '(', ')')
                        if closing is not None:
                            if i > segment_start:
                                output += text[segment_start:i]
                            f_match = self.re_func.fullmatch(output.plain)
                            if f_match:
                                fdict = f_match.groupdict()
                                func_name = fdict['func']
                                bangs = fdict['bangs']
                                if (func := self.find_function(func_name)):
                                    # hooray we have a function!
                                    ready_fun = func(self, func_name, text[i+1:closing])
                                    output = ready_fun.execute()
                                else:
                                    if called_recursively:
                                        notfound_fun = NotFoundFunction(self, func_name, text[i+1:closing])
                                        output = notfound_fun.execute()
                                segment_start = closing+1
                                i = closing+1
                        else:
                            i += 1
                    elif c == '%':
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
                    output += text[segment_start:i]

        # if we reach down here, then we are doing well and can pop a frame off.
        self.stack.pop(-1)
        if self.stack:
            self.frame = self.stack[-1]
        return output

    def valid_sub(self, text: str, start: int):
        simple = text[start:start+2]
        sub = None
        if simple in ('%R', '%r'):
            sub = (MushSub.NEWLINE, None)
        elif simple in ('%T', '%t'):
            sub = (MushSub.TAB, None)
        elif simple in ('%B', '%b'):
            sub = (MushSub.SPACE, None)
        elif simple == '%#':
            sub = (MushSub.ENACTOR_DBREF, None)
        elif simple == '%%':
            sub = (MushSub.PERCENT, None)
        elif simple == '%:':
            sub = (MushSub.ENACTOR_OBJID, None)
        elif simple == '%@':
            sub = (MushSub.CALLER_DBREF, None)
        elif simple == '%?':
            sub = (MushSub.FUNC_INVOKE_AND_DEPTH, None)
        elif simple == '%+':
            sub = (MushSub.ARG_COUNT, None)
        elif simple == '%!':
            sub = (MushSub.EXECUTOR_DBREF, None)
        elif simple in ('%l', '%L'):
            sub = (MushSub.ENACTOR_LOCATION_DBREF, simple[1].isupper())
        elif simple in ('%n', '%N'):
            sub = (MushSub.ENACTOR_NAME, simple[1].isupper())
        elif simple in ('%s', '%S'):
            sub = (MushSub.SUBJECTIVE_PRONOUN, simple[1].isupper())
        elif simple in ('%p', '%P'):
            sub = (MushSub.POSSESSIVE_PRONOUN, simple[1].isupper())
        elif simple in ('%o', '%O'):
            sub = (MushSub.OBJECTIVE_PRONOUN, simple[1].isupper())
        elif simple in ('%a', '%A'):
            sub = (MushSub.ABSOLUTE_PRONOUN, simple[1].isupper())

        if sub:
            return 2, sub

        t_start = text[start:]

        if (match := self.re_number_args.fullmatch(t_start)):
            gdict = match.groupdict()
            number = gdict['number']
            length = len(number)
            number = int(number)
            return 1+length, (MushSub.NUMBER_ARG_VALUE, number)

        if t_start.lower().startswith('%q'):
            # this is a q-register of some kind.
            gdict = None
            extra = 2
            if (match := self.re_q_reg.match(t_start)):
                gdict = match.groupdict()
            elif (match := self.re_q_named.match(t_start)):
                gdict = match.groupdict()
                extra += 2
            if gdict:
                varname = gdict['varname']
                varlength = len(varname)
                if varname.isdigit():
                    varname = int(varname)
                return extra + varlength, (MushSub.REGISTER_VALUE, varname)

        for code, reg, length in ((MushSub.ITEXT, self.re_itext, 2), (MushSub.DTEXT, self.re_dtext, 2),
                                  (MushSub.STEXT, self.re_stext, 2), (MushSub.INUM, self.re_inum, 3),
                                  (MushSub.DNUM, self.re_dnum, 3)):
            if (match := reg.match(t_start)):
                mdict = match.groupdict()
                number = mdict['num']
                extra = len(number)
                number = int(number)
                return length + extra, (code, number)

        return None

    def find_function(self, funcname: str):
        return self.entry.queue.service.functions.get(funcname.lower(), None)