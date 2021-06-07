from typing import Union, Iterable, List

from mudstring.patches.text import MudText, OLD_TEXT

from pymush.utils.text import to_number
from pymush.utils import formatter as fmt
from pymush.engine.api import BaseApi


class BaseFunction(BaseApi):
    name = None
    aliases = set()
    min_args = None
    max_args = None
    exact_args = None
    even_args = False
    odd_args = False
    eval_args = True
    help_category = None

    def __init__(self, parser, called_as: str, args_data: MudText):
        self.parser = parser
        self.called_as = called_as
        self.args_data = args_data
        self.args = list()
        self.args_eval = list()
        self.args_count = 1
        self.error = False

    @classmethod
    def help(cls, interpreter):
        """
        This is called by the command-help system if help is called on this command.
        """
        enactor = interpreter.frame.enactor
        if cls.__doc__:
            out = fmt.FormatList(enactor)
            out.add(fmt.Header(f"Help: {cls.name}"))
            out.add(fmt.Line(cls.__doc__))
            out.add(fmt.Footer())
            enactor.send(out)
        else:
            enactor.msg(text="Help is not implemented for this command.")

    def _err_too_many_args(self, num):
        if self.min_args is not None and self.min_args != self.max_args:
            return MudText(
                f"#-1 FUNCTION ({self.name.upper()}) EXPECTS BETWEEN {self.min_args} AND {self.max_args} ARGUMENTS BUT GOT {num}")
        else:
            return MudText(
                f"#-1 FUNCTION ({self.name.upper()}) EXPECTS AT MOST {self.max_args} ARGUMENTS BUT GOT {num}")

    def _err_too_few_args(self, num):
        if self.max_args is not None and self.min_args != self.max_args:
            return MudText(
                f"#-1 FUNCTION ({self.name.upper()}) EXPECTS BETWEEN {self.min_args} AND {self.max_args} ARGUMENTS BUT GOT {num}")
        else:
            return MudText(
                f"#-1 FUNCTION ({self.name.upper()}) EXPECTS AT LEAST {self.min_args} ARGUMENTS BUT GOT {num}")

    def _err_uneven_args(self, num):
        return MudText(
            f"#-1 FUNCTION ({self.name.upper()}) EXPECTS EVEN NUMBER OF ARGUMENTS BUT GOT {num}")

    def _err_even_args(self, num):
        return MudText(
            f"#-1 FUNCTION ({self.name.upper()}) EXPECTS ODD NUMBER OF ARGUMENTS BUT GOT {num}")

    def _err_num_args(self, num):
        return MudText(
            f"#-1 FUNCTION ({self.name.upper()}) EXPECTS {self.exact_args} ARGUMENTS BUT GOT {num}")

    def split_args(self):
        escaped = False
        text = self.args_data
        plain = text.plain
        paren_depth = 0
        i = 0
        segment_start = i

        while i < len(plain):
            if escaped:
                escaped = False
                continue
            else:
                c = plain[i]
                if c == '\\':
                    escaped = True
                elif c == '(':
                    paren_depth += 1
                elif c == ')' and paren_depth:
                    paren_depth -= 1
                elif c == ',' and not paren_depth:
                    self.args_count += 1
                    self.args.append(text[segment_start:i])
                    segment_start = i+1
            i += 1

        if i > segment_start:
            self.args.append(text[segment_start:i])

        total = len(self.args)
        diff = self.args_count - total

        if diff:
            for _ in range(diff):
                self.args.append(MudText(""))

    def execute(self):
        self.split_args()
        c = self.args_count
        if self.exact_args is not None and c != self.exact_args:
            return self._err_num_args(c)
        if self.max_args is not None and c > self.max_args:
            return self._err_too_many_args(c)
        if self.min_args is not None and c < self.min_args:
            return self._err_too_few_args(c)
        if self.even_args and c % 2 == 1:
            return self._err_uneven_args(c)
        if self.odd_args and c % 2 == 0:
            return self._err_even_args(c)
        return self.do_execute()

    def do_execute(self):
        return MudText(f"#-1 FUNCTION {self.name.upper()} IS NOT IMPLEMENTED")

    def join_by(self, lines: Iterable[OLD_TEXT], delim: OLD_TEXT):
        out = MudText("")
        finish = len(lines)-1
        for i, elem in enumerate(lines):
            out.append(elem)
            if i != finish:
                out.append(delim)
        return out

    def list_to_numbers(self, numbers: Iterable[MudText]) -> List[Union[float, int]]:
        out_vals = list()
        for arg in numbers:
            num = to_number(self.parser.evaluate(arg))
            if num is None:
                raise ValueError("#-1 ARGUMENTS MUST BE NUMBERS")
            out_vals.append(num)
        return out_vals


class NotFound(BaseFunction):
    def execute(self):
        return MudText(f"#-1 FUNCTION ({self.called_as.upper()}) NOT FOUND")