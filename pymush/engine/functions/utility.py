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

        self.parser.frame.set_var(reg_name, value)
        return value


class SetQFunction(SetRFunction):
    name = 'setq'

    def do_execute(self):
        super().do_execute()
        return MudText("")


class ListQFunction(BaseFunction):
    name = 'listq'
    exact_args = 1

    def do_execute(self):
        vars = " ".join([str(key) for key in self.parser.frame.vars.keys()])
        return MudText(vars)


class IfFunction(BaseFunction):
    name = 'if'
    min_args = 1
    max_args = 3

    def do_execute(self):
        if self.parser.truthy(self.parser.evaluate(self.args[0])):
            return self.parser.evaluate(self.args[1])
        else:
            if len(self.args) == 3:
                return self.parser.evaluate(self.args[2])
            else:
                return MudText("")


class IterFunction(BaseFunction):
    name = 'iter'
    min_args = 2
    max_args = 4

    def __init__(self, parser, called_as: str, args_data: MudText):
        super().__init__(parser, called_as, args_data)
        self.ibreak = False

    def do_execute(self):
        out = list()
        delim = ' '
        out_delim = MudText(' ')
        if self.args_count >= 3:
            delim = self.parser.evaluate(self.args[2])
        if self.args_count == 4:
            out_delim = self.parser.evaluate(self.args[3])

        elements = self.split_by(self.parser.evaluate(self.args[0]), delim)

        for i, elem in enumerate(elements):
            out.append(self.parser.evaluate(self.args[1], iter=self, inum=i, ivar=elem))
            if self.ibreak:
                break

        return out_delim.join(out)


class IBreakFunction(BaseFunction):
    name = 'ibreak'
    exact_args = 1

    def do_execute(self):
        if not self.parser.frame.iter:
            return MudText("#-1 ARGUMENT OUT OF RANGE")
        arg = self.parser.evaluate(self.args[0])
        if arg:
            num = self.parser.to_number(arg)
            if num is not None:
                num = max(int(num), 0)
        else:
            num = 0

        try:
            func = self.parser.frame.iter[num]
            func.ibreak = True
            return MudText('')
        except IndexError:
            return MudText("#-1 ARGUMENT OUT OF RANGE")

