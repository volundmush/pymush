from mudstring.patches.text import MudText
from mudstring.encodings.pennmush import ansi_fun, ansi_fun_style, ansify

from . base import BaseFunction


class _AbstractStringFunction(BaseFunction):
    help_category = 'string'


class AnsiFunction(_AbstractStringFunction):
    name = "ansi"
    exact_args = 2

    def do_execute(self):
        codes = self.parser.evaluate(self.args[0])
        text = self.parser.evaluate(self.args[1])

        try:
            style = ansi_fun_style(codes.plain)
        except ValueError as err:
            return MudText(f"#-1 INVALID ANSI DEFINITION: {err}")
        return ansify(style, text)


class ScrambleFunction(_AbstractStringFunction):
    name = "scramble"
    exact_args = 1

    def do_execute(self):
        if self.args:
            return self.parser.evaluate(self.args[0]).scramble()
        else:
            return MudText("")


class ReverseFunction(_AbstractStringFunction):
    name = "reverse"
    exact_args = 1

    def do_execute(self):
        if self.args:
            return self.parser.evaluate(self.args[0]).reverse()
        else:
            return MudText("")

