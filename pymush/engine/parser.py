from .functions.base import NotFound as NotFoundFunction
from rich.text import Text
import re


class StackFrame:
    def __init__(self, entry, parent):
        self.parent = parent
        self.entry = entry
        self.enactor = None
        self.spoof = None
        self.executor = None
        self.caller = None
        self.dolist_val = None
        self.iter_val = None
        self.localized = False
        self.number_args = None
        if parent:
            self.vars = parent.vars
        else:
            self.vars = entry.vars

    def localize(self):
        self.localized = True
        # We are localizing this frame, so break the connection to its parent.
        self.vars = dict(self.vars)


class Parser:
    re_func = re.compile(r"^(?P<bangs>!|!!|!\$|!!\$|!\^|!!\^)?(?P<func>\w+)(?P<open>\()")
    re_number_args = re.compile(r"^%(?P<number>\d+)")
    re_q_old = re.compile(r"(?i)^%q(?P<q>[A-Z0-9])")
    re_q_named = re.compile(r"(?i)^%q<(?P<q>\w+)>")

    def __init__(self, core, enactor, executor, caller):
        self.core = core
        self.enactor = enactor
        self.executor = executor
        self.caller = caller
        self.stack = list()
        self.frame = None
        self.func_count = 0
        self.vars = dict()

    def eval_sub(self, text: str):
        """
        Eventually this will process % and other substitutions.
        """
        if text.startswith('%#'):
            return str(self.enactor), text[2:]
        elif text.startswith('%n'):
            return self.enactor.name, text[2:]
        elif text.startswith('%a'):
            return 'ansi', text[2:]
        elif text.startswith('%R') or text.startswith('%r'):
            return '\n', text[2:]
        elif text.startswith('%T') or text.startswith('%t'):
            return '\t', text[2:]
        elif text.startswith('%l') or text.startswith('%L'):
            if (loc := self.enactor.relations.get('location')):
                return loc.objid, text[2:]
            else:
                return '', text[2:]
        elif (m := self.re_number_args.fullmatch(text)):
            mdict = m.groupdict()
            num = int(mdict['number'])
            if self.frame.number_args:
                return self.frame.number_args.get(num, ''), text[len(mdict['number'])+1:]
        else:
            return '%', text[1:]

    def find_function(self, funcname: str):
        return self.core.functions.get(funcname.lower(), None)

    def evaluate(self, text: str, localize: bool = False, spoof: str = None, called_recursively: bool = False, stop_at=None,
                 recurse=True, substitute=True, functions=True, curly_literals=True, noeval=False, executor=None, number_args=None):
        if text is None:
            text = ''
        if isinstance(text, Text):
            text = text.plain
        if stop_at is None:
            stop_at = list()
        if isinstance(stop_at, str):
            stop_at = [stop_at]
        if not len(text):
            return Text(""), '', None
        if noeval:
            recurse = False
            substitute = False
            functions = False
            curly_literals = True
        # if cpu exceeded, cancel here.
        # if fil exceeded, cancel here.
        # if recursion limit reached, cancel here.
        if not noeval:
            if self.frame:
                new_frame = StackFrame(self, self.frame)
                self.frame = new_frame
                if localize:
                    new_frame.localize()
                self.stack.append(new_frame)
            else:
                self.frame = StackFrame(self, None)
                self.stack.append(self.frame)
            if number_args:
                self.frame.number_args = number_args
            if executor:
                self.frame.executor = executor
        out = Text()
        remaining = text
        escaped = False
        called_func = False
        stopped = None
        curl_escaped = False
        nest_depth = 0

        i = -1

        while i < len(remaining)-1:
            i += 1
            c = remaining[i]
            if escaped:
                out += c
                escaped = False
            else:
                if c == '\\':
                    escaped = True
                elif c == '{' and curly_literals and not curl_escaped:
                    curl_escaped += 1
                elif c == '}' and curly_literals and curl_escaped > 0:
                    curl_escaped -= 1
                elif stop_at and c in stop_at and nest_depth == 0:
                    if curl_escaped:
                        out += c
                    else:
                        remaining = remaining[i+1:]
                        stopped = c
                        break
                elif c == '%' and substitute:
                    subbed, remaining = self.eval_sub(remaining[i:])
                    out += subbed
                    i = -1
                elif c == '[' and recurse:
                    evaled, remaining, stop_char = self.evaluate(remaining[i+1:], called_recursively=True, stop_at=']')
                    i = -1
                    out += evaled
                elif c == '(' and not called_func and functions:
                    out += c
                    if (match := self.re_func.fullmatch(out.clean)):
                        gdict = match.groupdict()
                        if gdict:
                            if (func := self.find_function(gdict["func"])):
                                # hooray we have a function!
                                ready_fun = func(self, gdict['func'], remaining[i+1:])
                                ready_fun.execute()
                                called_func = True
                                # the function's output will replace everything that lead up to its calling.
                                out = ready_fun.output
                                remaining = ready_fun.remaining
                                i = -1
                            else:
                                if called_recursively:
                                    notfound_fun = NotFoundFunction(self, gdict['func'], remaining[i+1:])
                                    notfound_fun.execute()
                                    out = notfound_fun.output
                                    remaining = notfound_fun.remaining
                                    i = -1
                                called_func = True
                elif c == '(' and not functions:
                    nest_depth += 1
                    out += c
                elif c == ')' and nest_depth > 0:
                    nest_depth -= 1
                    out += c
                else:
                    out += c

        # if we reach down here, then we are doing well and can pop a frame off.
        if not noeval:
            self.stack.pop(-1)
            if self.stack:
                self.frame = self.stack[-1]

        # If stopped was never set, then we ended because we reached EOL.
        if stopped is None and remaining:
            remaining = ''

        return out, remaining, stopped
