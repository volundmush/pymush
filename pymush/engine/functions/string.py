from . base import BaseFunction
from rich.text import Text


class AnsiFunction(BaseFunction):
    name = "ansi"
    min_args = 2
    max_args = 2

    def do_execute(self):
        codes = self.args_eval[0].clean
        text = self.args_eval[1]
        self.output = AnsiString.from_args(codes, text)
        if self.output.clean.startswith("#-1 INVALID ANSI DEFINITION"):
            self.error = True
            return False
        else:
            self.error = False
            return True


class ScrambleFunction(BaseFunction):
    name = "scramble"
    min_args = 0
    max_args = 1

    def do_execute(self):
        if self.args_count:
            self.output = self.args_eval[0].scramble()
            return True
        else:
            self.output = AnsiString()
            return True


STRING_FUNCTIONS = [AnsiFunction, ScrambleFunction]