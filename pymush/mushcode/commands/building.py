import weakref

from mudrich.text import Text
from typing import Iterable

from pymush.utils.text import case_match, truthy

from .base import MushCommand, MushCommandException, MushCommandMatcher


class _BuildCommand(MushCommand):
    help_category = 'Build'


class SetCommand(_BuildCommand):
    name = "@set"
    aliases = ["@se"]

    async def execute(self):
        lsargs, rsargs = self.eqsplit_args(self.args)

        obj, err = self.executor.locate_object(
            name=await self.parser.evaluate(lsargs), first_only=True
        )
        if err:
            self.executor.msg(err)
            return
        obj = obj[0]
        to_set = await self.parser.evaluate(rsargs)

        idx = to_set.find(":")
        if idx == -1:
            self.executor.msg("Malformed @set syntax")
        attr_name = to_set[:idx]
        value = to_set[idx + 1 :]
        result = self.set_attr(obj, attr_name, value)
        if result.error:
            self.executor.msg(result.error)
        else:
            self.executor.msg("Set.")
