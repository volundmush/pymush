import weakref

from mudrich.text import Text
from typing import Iterable

from pymush.utils.text import case_match, truthy

from .base import MushCommand, CommandException, PythonCommandMatcher


class _ScriptCommand(MushCommand):
    help_category = "Building"


class DoListCommand(_ScriptCommand):
    name = "@dolist"
    aliases = ["@dol", "@doli", "@dolis"]
    available_switches = [
        "delimit",
        "clearregs",
        "inplace",
        "localize",
        "nobreak",
        "notify",
    ]

    async def execute(self):
        lsargs, rsargs = self.eqsplit_args(self.args)
        if "inplace" in self.switches:
            self.switches.update({"inline", "nobreak", "localize"})

        lsargs = await self.parser.evaluate(lsargs)

        if "delimit" in self.switches:
            delim, _ = lsargs.plain.split(" ", 1)
            if not len(delim) == 1:
                raise CommandException("Delimiter must be one character.")
            elements = lsargs[2:]
        else:
            delim = " "
            elements = lsargs

        if not len(elements):
            return

        elements = self.split_by(elements, delim)
        nobreak = "nobreak" in self.switches

        for i, elem in enumerate(elements):
            self.entry.inline(
                rsargs, nobreak=nobreak, dnum=i, dvar=elem
            )


class AssertCommand(_ScriptCommand):
    name = "@assert"
    aliases = ["@as", "@ass", "@asse", "@asser"]

    async def execute(self):
        lsargs, rsargs = self.eqsplit_args(self.args)
        if not self.parser.truthy(await self.parser.evaluate(lsargs)):
            if rsargs:
                self.entry.inline(rsargs)
            self.entry.parser.frame.break_after = True


class BreakCommand(_ScriptCommand):
    name = "@break"
    aliases = ["@br", "@bre", "@brea"]

    async def execute(self):
        lsargs, rsargs = self.eqsplit_args(self.args)
        if self.parser.truthy(await self.parser.evaluate(lsargs)):
            if rsargs:
                self.entry.inline(rsargs)
            self.entry.parser.frame.break_after = True



class TriggerCommand(_ScriptCommand):
    name = "@trigger"
    aliases = ["@tr", "@tri", "@trig", "@trigg", "@trigge"]


class IncludeCommand(_ScriptCommand):
    name = "@include"
    aliases = ["@inc", "@incl", "@inclu", "@includ"]
    available_switches = ["nobreak"]

    async def execute(self):
        lsargs, rsargs = self.eqsplit_args(self.args)
        obj, attr_name, err = self.target_obj_attr(
            await self.parser.evaluate(lsargs), default=self.executor
        )
        if err:
            self.executor.msg(Text(err))

        actions = await self.get_attr(obj, attr_name=attr_name)

        if not truthy(actions):
            self.executor.msg(
                f"{self.name} cannot use that attribute. Is it accessible, and an action list?"
            )

        number_args = [await self.parser.evaluate(arg) for arg in self.split_cmd_args(rsargs)]
        await self.entry.inline(actions, nobreak='nobreak' in self.switches, number_args=number_args)


class SwitchCommand(_ScriptCommand):
    name = "@switch"
    aliases = ["@swi", "@swit", "@switc"]
    available_switches = ["all"]

    async def execute(self):
        lsargs, rsargs = self.eqsplit_args(self.args)
        matcher = await self.parser.evaluate(lsargs)
        s_rsargs = self.split_cmd_args(rsargs)

        actions = list()
        default = None
        if len(s_rsargs) % 2 == 0:
            args = s_rsargs[1:]
        else:
            default = s_rsargs[-1]
            args = s_rsargs[1:-1]

        stop_first = "all" not in self.switches

        for case, outcome in zip(args[0::2], args[1::2]):
            if case_match(matcher, await self.parser.evaluate(case, stext=matcher)):
                actions.append(outcome)
                if stop_first:
                    break

        if not actions:
            if default:
                actions.append(default)

        if actions:
            await self.entry.inline(actions)


class SetCommand(_ScriptCommand):
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


class _EmitCommand(_ScriptCommand):

    def send_to_targets(self, targets: Iterable["GameObject"], to_send: Text):
        if not to_send:
            self.executor.msg("Nothing to send.")
            return
        if not targets:
            self.executor.msg("Nobody to hear it.")

        for target in targets:
            can_send, err = target.can_receive_text(self.executor, self.interpreter, to_send)
            if not can_send:
                self.executor.msg(err)
                continue
            target.receive_text(self.executor, self.interpreter, to_send)


class PemitCommand(_EmitCommand):
    name = '@pemit'
    aliases = ['@pe', '@pem', '@pemi']

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
    name = '@remit'
    aliases = ['@re', '@rem', '@remi']

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
        targets.update(obj.namespaces['EXIT'])

        self.send_to_targets(targets, await self.parser.evaluate(rsargs))


class OemitCommand(_EmitCommand):
    name = '@oemit'
    aliases = ['@oe', '@oem', '@oemi']

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

        self.send_to_targets(obj.neighbors(include_exits=True), await self.parser.evaluate(rsargs))


class EmitCommand(_EmitCommand):
    name = '@emit'
    aliases = ['@em', '@emi']

    async def execute(self):
        obj = self.executor
        targets = obj.neighbors(include_exits=True)
        targets.add(obj)

        self.send_to_targets(targets, await self.parser.evaluate(self.args))


class ScriptCommandMatcher(PythonCommandMatcher):
    priority = 10

    async def access(self, entry: "TaskEntry"):
        return not entry.session or entry.get_alevel() > 0

    def at_cmdmatcher_creation(self):
        cmds = [
            DoListCommand,
            AssertCommand,
            BreakCommand,
            TriggerCommand,
            IncludeCommand,
            SwitchCommand,
            SetCommand,
            PemitCommand,
            RemitCommand,
            OemitCommand,
            EmitCommand
        ]
        for cmd in cmds:
            self.add(cmd)
