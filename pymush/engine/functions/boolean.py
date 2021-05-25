from . base import BaseFunction
from mudstring.patches.text import MudText


class AbstractBoolFunction(BaseFunction):
    
    def do_execute(self):
        return MudText("1") if self.math_execute() else MudText("0")

    def math_execute(self):
        return False


class TFunction(AbstractBoolFunction):
    name = 't'
    min_args = 0
    max_args = 1

    def math_execute(self):
        if self.args:
            value = self.parser.evaluate(self.args[0])
            return self.parser.truthy(value)
        else:
            return self.parser.truthy('')


class NotFunction(AbstractBoolFunction):
    name = 'not'
    min_args = 0
    max_args = 1

    def math_execute(self):
        if self.args:
            value = self.parser.evaluate(self.args[0])
            return not self.parser.truthy(value)
        else:
            return not self.parser.truthy('')


class AndFunction(AbstractBoolFunction):
    name = 'and'
    min_args = 2
    
    def math_execute(self):
        truthy = [self.parser.truthy(self.parser.evaluate(arg)) for arg in self.args]
        return all(truthy)


class CAndFunction(AbstractBoolFunction):
    name = 'cand'
    min_args = 2

    def math_execute(self):
        truthy = False
        for arg in self.args:
            evaled = self.parser.evaluate(arg)
            truthy = self.parser.truthy(evaled)
            if not truthy:
                return False
        return truthy


class OrFunction(AbstractBoolFunction):
    name = 'or'
    min_args = 2

    def math_execute(self):
        truthy = [self.parser.truthy(self.parser.evaluate(arg)) for arg in self.args]
        return any(truthy)


class COrFunction(AbstractBoolFunction):
    name = 'cor'
    min_args = 2

    def math_execute(self):
        for arg in self.args:
            evaled = self.parser.evaluate(arg)
            truthy = self.parser.truthy(evaled)
            if truthy:
                return True
        return False


BOOLEAN_FUNCTIONS = [TFunction, NotFunction, AndFunction, CAndFunction, OrFunction, COrFunction]