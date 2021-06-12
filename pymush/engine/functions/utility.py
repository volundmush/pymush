from mudrich.text import Text

from pymush.utils.text import case_match
from pymush.db.attributes import AttributeRequest, AttributeRequestType
from .base import BaseFunction


class SetRFunction(BaseFunction):
    name = "setr"
    exact_args = 2

    async def do_execute(self):
        reg_name = await self.parser.evaluate(self.args[0])
        value = await self.parser.evaluate(self.args[1])

        reg_name = reg_name.plain.strip()
        if reg_name.isdigit():
            reg_name = int(reg_name)

        self.parser.frame.set_var(reg_name, value)
        return value


class SetQFunction(SetRFunction):
    name = "setq"

    async def do_execute(self):
        await super().do_execute()
        return Text("")


class ListQFunction(BaseFunction):
    name = "listq"
    exact_args = 1

    async def do_execute(self):
        vars = " ".join([str(key) for key in self.parser.frame.vars.keys()])
        return Text(vars)


class IfFunction(BaseFunction):
    name = "if"
    min_args = 1
    max_args = 3

    async def do_execute(self):
        if self.parser.truthy(await self.parser.evaluate(self.args[0])):
            return await self.parser.evaluate(self.args[1])
        else:
            if len(self.args) == 3:
                return await self.parser.evaluate(self.args[2])
            else:
                return Text("")


class IterFunction(BaseFunction):
    name = "iter"
    min_args = 2
    max_args = 4

    def __init__(self, parser, called_as: str, args_data: Text):
        super().__init__(parser, called_as, args_data)
        self.ibreak = False

    async def do_execute(self):
        out = list()
        delim = " "
        out_delim = Text(" ")
        if self.args_count >= 3:
            delim = await self.parser.evaluate(self.args[2])
        if self.args_count == 4:
            out_delim = await self.parser.evaluate(self.args[3])

        elements = self.split_by(await self.parser.evaluate(self.args[0]), delim)

        for i, elem in enumerate(elements):
            out.append(await self.parser.evaluate(self.args[1], iter=self, inum=i, ivar=elem))
            if self.ibreak:
                break

        return out_delim.join(out)


class IBreakFunction(BaseFunction):
    name = "ibreak"
    exact_args = 1

    async def do_execute(self):
        if not self.parser.frame.iter:
            return Text("#-1 ARGUMENT OUT OF RANGE")
        arg = await self.parser.evaluate(self.args[0])
        if arg:
            num = self.parser.to_number(arg)
            if num is not None:
                num = max(int(num), 0)
        else:
            num = 0

        try:
            func = self.parser.frame.iter[num]
            func.ibreak = True
            return Text("")
        except IndexError:
            return Text("#-1 ARGUMENT OUT OF RANGE")


class SwitchFunction(BaseFunction):
    name = "switch"
    min_args = 3

    async def do_execute(self):
        matcher = await self.parser.evaluate(self.args[0])
        if len(self.args[1:]) % 2 == 0:
            default = Text("")
            args = self.args[1:]
        else:
            default = await self.parser.evaluate(self.args[-1], stext=matcher)
            args = self.args[1:-1]

        for case, outcome in zip(args[0::2], args[1::2]):
            if case_match(matcher, await self.parser.evaluate(case, stext=matcher)):
                return await self.parser.evaluate(outcome, stext=matcher)
        return default


class UFunction(BaseFunction):
    name = "u"
    min_args = 1

    async def do_execute(self):
        obj, attr_name, err = self.target_obj_attr(await self.parser.evaluate(self.args[0]))
        if err:
            return Text("#-1 UNABLE TO LOCATE OBJECT")

        req = self.get_attr(obj, attr_name)
        if req.error:
            return req.error
        code = req.value
        number_args = [await self.parser.evaluate(arg) for arg in self.args[1:]]

        return await self.parser.evaluate(
            code, number_args=number_args, executor=obj, caller=self.executor
        )
