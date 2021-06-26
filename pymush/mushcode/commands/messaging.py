import weakref

from mudrich.text import Text
from typing import Iterable

from pymush.utils.text import case_match, truthy

from .base import MushCommand, MushCommandException, MushCommandMatcher


class _MessageCommand(MushCommand):
    help_category = 'Messaging'


class SetCommand(_MessageCommand):
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


class _EmitCommand(_MessageCommand):
    def send_to_targets(self, targets: Iterable["GameObject"], to_send: Text):
        if not to_send:
            self.executor.msg("Nothing to send.")
            return
        if not targets:
            self.executor.msg("Nobody to hear it.")

        for target in targets:
            can_send, err = target.can_receive_text(
                self.executor, self.interpreter, to_send
            )
            if not can_send:
                self.executor.msg(err)
                continue
            target.receive_text(self.executor, self.interpreter, to_send)


class PemitCommand(_EmitCommand):
    name = "@pemit"
    aliases = ["@pe", "@pem", "@pemi"]

    async def execute(self):
        lsargs, rsargs = self.eqsplit_args(self.args)

        obj, err = self.executor.locate_object(
            name=await self.parser.evaluate(lsargs), first_only=True
        )
        if err:
            self.executor.msg(err)
            return
        obj = obj[0]
        self.send_to_targets([obj], await self.parser.evaluate(rsargs))


class RemitCommand(_EmitCommand):
    name = "@remit"
    aliases = ["@re", "@rem", "@remi"]

    async def execute(self):
        lsargs, rsargs = self.eqsplit_args(self.args)

        obj, err = self.executor.locate_object(
            name=await self.parser.evaluate(lsargs), first_only=True
        )
        if err:
            self.executor.msg(err)
            return
        obj = obj[0]

        targets = weakref.WeakSet()
        targets.update(obj.contents)
        targets.update(obj.namespaces["EXIT"])

        self.send_to_targets(targets, await self.parser.evaluate(rsargs))


class OemitCommand(_EmitCommand):
    name = "@oemit"
    aliases = ["@oe", "@oem", "@oemi"]

    async def execute(self):
        lsargs, rsargs = self.eqsplit_args(self.args)

        obj, err = self.executor.locate_object(
            name=await self.parser.evaluate(lsargs), first_only=True
        )
        if err:
            self.executor.msg(err)
            return
        obj = obj[0]

        loc = obj.location
        if not loc:
            self.executor.msg("Nothing would hear it.")
            return

        self.send_to_targets(
            obj.neighbors(include_exits=True), await self.parser.evaluate(rsargs)
        )


class EmitCommand(_EmitCommand):
    name = "@emit"
    aliases = ["@em", "@emi"]

    async def execute(self):
        obj = self.executor
        targets = obj.neighbors(include_exits=True)
        targets.add(obj)

        self.send_to_targets(targets, await self.parser.evaluate(self.args))
