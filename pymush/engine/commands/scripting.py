import re
import sys
import time
import traceback
from athanor.utils import partial_match
from . base import Command, MushCommand, CommandException, PythonCommandMatcher
from pymush.engine.cmdqueue import BreakQueueException, QueueEntryType
from mudstring.encodings.pennmush import send_menu, ansi_fun
from pymush.utils import formatter as fmt


class DoListCommand(MushCommand):
    name = '@dolist'
    aliases = ['@dol', '@doli', '@dolis']
    available_switches = ['delimit', 'clearregs', 'inline', 'inplace', 'localize', 'nobreak', 'notify']

    def execute(self):
        lsargs, rsargs = self.eqsplit_args(self.args)
        if 'inplace' in self.switches:
            self.switches.update({"inline", "nobreak", "localize"})

        lsargs = self.parser.evaluate(lsargs)

        if 'delimit' in self.switches:
            delim, _ = lsargs.plain.split(' ', 1)
            if not len(delim) == 1:
                raise CommandException("Delimiter must be one character.")
            elements = lsargs[2:]
        else:
            delim = ' '
            elements = lsargs

        if not len(elements):
            return

        elements = self.split_by(elements, delim)
        nobreak = 'nobreak' in self.switches

        if 'inline' in self.switches:
            for i, elem in enumerate(elements):
                self.entry.execute_action_list(rsargs, nobreak=nobreak, dnum=i, dvar=elem)
        else:
            for i, elem in enumerate(elements):
                self.entry.spawn_action_list(rsargs, dnum=i, dvar=elem)


class AssertCommand(MushCommand):
    name = '@assert'
    aliases = ['@as', '@ass', '@asse', '@asser']
    available_switches = ['queued']

    def execute(self):
        lsargs, rsargs = self.eqsplit_args(self.args)
        if not self.parser.truthy(self.parser.evaluate(lsargs)):
            if rsargs:
                if 'queued' in self.switches:
                    self.entry.spawn_action_list(rsargs)
                else:
                    self.entry.execute_action_list(rsargs)
            raise BreakQueueException(self)


class BreakCommand(MushCommand):
    name = '@break'
    aliases = ['@br', '@bre', '@brea']
    available_switches = ['queued']

    def execute(self):
        lsargs, rsargs = self.eqsplit_args(self.args)
        if self.parser.truthy(self.parser.evaluate(lsargs)):
            if rsargs:
                if 'queued' in self.switches:
                    self.entry.spawn_action_list(rsargs)
                else:
                    self.entry.execute_action_list(rsargs)
            raise BreakQueueException(self)


class TriggerCommand(MushCommand):
    name = '@trigger'
    aliases = ['@tr', '@tri', '@trig', '@trigg', '@trigge']


class IncludeCommand(MushCommand):
    name = '@include'
    aliases = ['@inc', '@incl', '@inclu', '@includ']


class ScriptCommandMatcher(PythonCommandMatcher):
    priority = 10

    def access(self, entry: "QueueEntry"):
        return entry.type == QueueEntryType.SCRIPT

    def at_cmdmatcher_creation(self):
        for cmd in [DoListCommand, AssertCommand, BreakCommand, TriggerCommand, IncludeCommand]:
            self.add(cmd)
