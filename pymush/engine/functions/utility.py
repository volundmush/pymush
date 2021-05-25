from . base import BaseFunction
from mudstring.patches.text import MudText


class SetRFunction(BaseFunction):
    name = 'setr'
    exact_args = 2

    def do_execute(self):
        reg_name = self.parser.evaluate(self.args[0])
        value = self.parser.evaluate(self.args[1])

        reg_name = reg_name.plain.strip()
        if reg_name.isdigit():
            reg_name = int(reg_name)

        if value.plain:
            self.parser.frame.vars[reg_name] = value
        else:
            self.parser.frame.vars.pop(reg_name, None)
        return value


class SetQFunction(SetRFunction):
    name = 'setq'

    def do_execute(self):
        super().do_execute()
        return MudText("")


class ListQFunction(BaseFunction):
    name = 'listq'
    min_args = 0
    max_args = 1

    def do_execute(self):
        vars = " ".join([str(key) for key in self.parser.frame.vars.keys()])
        return MudText(vars)


VAR_FUNCTIONS = [SetRFunction, SetQFunction, ListQFunction]