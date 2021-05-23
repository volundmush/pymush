from .functions.base import NotFound as NotFoundFunction
from mudstring.patches.text import MudText
import re
from typing import Union, Optional, List, Set, Tuple, Dict
from enum import IntEnum


class MushLex(IntEnum):
    SPAN = 0
    RECURSE = 1
    SUB = 2


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

    def eval_sub(self, text: MudText):
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
            return MudText('\n')
        elif text.startswith('%T') or text.startswith('%t'):
            return MudText('\t')
        elif text.startswith('%l') or text.startswith('%L'):
            if (loc := self.enactor.relations.get('location')):
                return loc.objid, text[2:]
            else:
                return '', text[2:]
        elif (m := self.parser.re_number_args.fullmatch(text)):
            mdict = m.groupdict()
            num = int(mdict['number'])
            if self.number_args:
                return self.number_args.get(num, ''), text[len(mdict['number'])+1:]
        else:
            return '%', text[1:]


class Parser:
    re_func = re.compile(r"^(?P<bangs>!|!!|!\$|!!\$|!\^|!!\^)?(?P<func>\w+)(?P<open>\()")
    re_number_args = re.compile(r"^%(?P<number>\d+)")
    re_q_old = re.compile(r"(?i)^%q(?P<q>[A-Z0-9])")
    re_q_named = re.compile(r"(?i)^%q<(?P<q>\w+)>")

    def __init__(self, entry, enactor, executor, caller):
        self.entry = entry
        self.frame = StackFrame(self)
        self.frame.enactor = enactor
        self.frame.executor = executor
        self.frame.caller = caller
        self.stack = [self.frame]
        self.func_count = 0

    def evaluate(self, text: Union[None, str, MudText], localize: bool = False, spoof: Optional["GameObject"] = None,
                  called_recursively: bool = False, executor: Optional["GameObject"] = None,
                  caller: Optional["GameObject"] = None, number_args=None):

        if text is None:
            text = MudText("")
        if isinstance(text, str):
            text = MudText(text)

        spans = self.lex(text)

        if not spans:
            return MudText("")

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

        func_called = False

        for span in spans:
            if span[0] == MushLex.SPAN:
                output += span[1]
            elif span[0] == MushLex.SUB:
                output += frame.eval_sub(span[1])
            elif span[0] == MushLex.RECURSE:
                output += self.evaluate(span[1], called_recursively=True)

            if not func_called:
                results = self.function_scan(output)
                if results:
                    func_bangs, func_name, func_args, func_end = results
                    func_called, func_output = self.function_call(func_bangs, func_name, func_args,
                                                                  called_recursively=called_recursively)
                    if func_called:
                        output = func_output + output[func_end:]

        # if we reach down here, then we are doing well and can pop a frame off.
        self.stack.pop(-1)
        if self.stack:
            self.frame = self.stack[-1]

        return output

    def function_call(self, func_bangs: str, func_name: str, func_args: MudText, called_recursively=False):
        called = False
        output = None
        if (func := self.find_function(func_name)):
            # hooray we have a function!
            ready_fun = func(self, func_name, func_args)
            output = ready_fun.execute()
            called = True
        else:
            if called_recursively:
                notfound_fun = NotFoundFunction(self, func_name, func_args)
                output = notfound_fun.execute()
                called = True
        return called, output

    def function_scan(self, text: MudText):
        match = self.re_func.match(text.plain)
        if match:
            mdict = match.groupdict()
            func_name = mdict.get('func')
            func_bangs = mdict.get('bangs', None)
            func_start = match.end()
            paren_depth = 1
            escaped = False

            for i, c in enumerate(text.plain[func_start:]):
                if escaped:
                    escaped = False
                    continue
                else:
                    if c == '\\':
                        escaped = True
                    elif c == '(':
                        paren_depth += 1
                    elif c == ')':
                        if paren_depth:
                            paren_depth -= 1
                            if paren_depth == 0:
                                func_args = text[func_start:func_start+i]
                                return func_bangs, func_name, func_args, func_start+i+1

    def valid_sub(self, text: MudText):
        plain = text.plain
        if plain[0:2] in ('%R', '%r', '%T', '%t'):
            return 2

        return 0

    def find_function(self, funcname: str):
        return self.entry.queue.service.functions.get(funcname.lower(), None)

    def lex(self, text: MudText):
        spans = list()

        square_depth = 0
        paren_depth = 0
        escaped = False
        recurse_at = None
        segment_start = 0
        last_span_end = None

        i = -1
        plain = text.plain
        while True:
            i += 1
            if i >= len(plain):
                break
            c = plain[i]

            if escaped:
                escaped = False
            else:
                if c == '\\':
                    escaped = True
                elif c == '%':
                    results = self.valid_sub(text[i:])
                    if results:
                        if i > segment_start:
                            spans.append((MushLex.SPAN, text[segment_start:i-1]))

                        spans.append((MushLex.SUB, text[i:i+results]))
                        i += results
                        last_span_end = i
                        segment_start = i
                        i -= 1

                elif c == '(':
                    paren_depth += 1
                elif c == ')':
                    if paren_depth:
                        paren_depth -= 1
                elif c == '[':
                    if not paren_depth:
                        if square_depth == 0:
                            # we are entering a recurse section. Append any prepending segment as a span
                            recurse_at = i
                            if i > segment_start:
                                spans.append((MushLex.SPAN, text[segment_start:i]))
                                last_span_end = i - 1
                        square_depth += 1
                elif c == ']':
                    if not paren_depth:
                        if square_depth > 0:
                            # we are inside a recursion and found a recurse terminator...
                            square_depth -= 1
                            if square_depth == 0:
                                # we have found the end of the termination.
                                spans.append((MushLex.RECURSE, text[recurse_at + 1:i]))
                                segment_start = i + 1
                                last_span_end = i + 1


        # there may be leftover text that wasn't added to a span. add it to a span manually.
        if last_span_end is None:
            # somehow, there are no spans. in that case, just append everything as one span that does not recurse.
            spans.append((MushLex.SPAN, text))
        elif last_span_end < (len(text) - 1):
            # there is leftover text. append it as a no-recurse span.
            spans.append((MushLex.SPAN, text[last_span_end:]))
        return spans