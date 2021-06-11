from rich.text import Text

from pymush.utils.text import truthy

from .base import BaseFunction


class _AbstractBoolFunction(BaseFunction):
    help_category = "boolean"

    def do_execute(self):
        return Text("1") if self.math_execute() else Text("0")

    def math_execute(self):
        return False


class TFunction(_AbstractBoolFunction):
    name = "t"
    exact_args = 1

    def math_execute(self):
        return truthy(self.parser.evaluate(self.args[0]))


class NotFunction(TFunction):
    name = "not"

    def math_execute(self):
        return not super().math_execute()


class AndFunction(_AbstractBoolFunction):
    name = "and"
    min_args = 2

    def math_execute(self):
        return all([truthy(self.parser.evaluate(arg)) for arg in self.args])


class CAndFunction(_AbstractBoolFunction):
    name = "cand"
    min_args = 2

    def math_execute(self):
        t = False
        for arg in self.args:
            t = truthy(self.parser.evaluate(arg))
            if not t:
                return False
        return t


class OrFunction(_AbstractBoolFunction):
    name = "or"
    min_args = 2

    def math_execute(self):
        return any([truthy(self.parser.evaluate(arg)) for arg in self.args])


class COrFunction(_AbstractBoolFunction):
    name = "cor"
    min_args = 2

    def math_execute(self):
        for arg in self.args:
            if truthy(self.parser.evaluate(arg)):
                return True
        return False
