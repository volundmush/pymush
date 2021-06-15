from mudrich.text import Text

from pymush.utils.text import truthy

from .base import BaseFunction


class _AbstractBoolFunction(BaseFunction):
    help_category = "boolean"

    async def do_execute(self):
        return Text("1") if await self.math_execute() else Text("0")

    async def math_execute(self):
        return False


class TFunction(_AbstractBoolFunction):
    name = "t"
    exact_args = 1

    async def math_execute(self):
        return truthy(await self.evaluate(self.args[0]))


class NotFunction(TFunction):
    name = "not"

    async def math_execute(self):
        return not super().math_execute()


class AndFunction(_AbstractBoolFunction):
    name = "and"
    min_args = 2

    async def math_execute(self):
        return all([truthy(await self.evaluate(arg)) for arg in self.args])


class CAndFunction(_AbstractBoolFunction):
    name = "cand"
    min_args = 2

    async def math_execute(self):
        t = False
        for arg in self.args:
            t = truthy(await self.evaluate(arg))
            if not t:
                return False
        return t


class OrFunction(_AbstractBoolFunction):
    name = "or"
    min_args = 2

    async def math_execute(self):
        return any([truthy(await self.evaluate(arg)) for arg in self.args])


class COrFunction(_AbstractBoolFunction):
    name = "cor"
    min_args = 2

    async def math_execute(self):
        for arg in self.args:
            if truthy(await self.evaluate(arg)):
                return True
        return False
