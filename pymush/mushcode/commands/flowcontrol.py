from mudrich.text import Text

from pymush.utils.text import case_match, truthy

from .base import MushCommand, MushCommandException, MushCommandMatcher


class _FlowCommand(MushCommand):
    help_category = "Flow Control"


class DoListCommand(_FlowCommand):
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
                raise MushCommandException("Delimiter must be one character.")
            elements = lsargs[2:]
        else:
            delim = " "
            elements = lsargs

        if not len(elements):
            return

        elements = self.split_by(elements, delim)
        nobreak = "nobreak" in self.switches

        for i, elem in enumerate(elements):
            self.entry.inline(rsargs, nobreak=nobreak, dnum=i, dvar=elem)


class AssertCommand(_FlowCommand):
    name = "@assert"
    aliases = ["@as", "@ass", "@asse", "@asser"]

    async def execute(self):
        lsargs, rsargs = self.eqsplit_args(self.args)
        if not self.parser.truthy(await self.parser.evaluate(lsargs)):
            if rsargs:
                self.entry.inline(rsargs)
            self.entry.parser.frame.break_after = True


class BreakCommand(_FlowCommand):
    name = "@break"
    aliases = ["@br", "@bre", "@brea"]

    async def execute(self):
        lsargs, rsargs = self.eqsplit_args(self.args)
        if self.parser.truthy(await self.parser.evaluate(lsargs)):
            if rsargs:
                self.entry.inline(rsargs)
            self.entry.parser.frame.break_after = True


class TriggerCommand(_FlowCommand):
    name = "@trigger"
    aliases = ["@tr", "@tri", "@trig", "@trigg", "@trigge"]


class IncludeCommand(_FlowCommand):
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

        number_args = [
            await self.parser.evaluate(arg) for arg in self.split_cmd_args(rsargs)
        ]
        await self.entry.inline(
            actions, nobreak="nobreak" in self.switches, number_args=number_args
        )


class SwitchCommand(_FlowCommand):
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