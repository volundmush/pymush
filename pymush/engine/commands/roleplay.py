import weakref

from mudrich.text import Text
from typing import Iterable
from pymush.engine.cmdqueue import BreakQueueException, QueueEntryType
from pymush.utils.text import case_match, truthy

from .base import MushCommand, CommandException, PythonCommandMatcher


class _RoleplayCommand(MushCommand):
    help_category = 'Roleplay'

    def distribute(self, targets: Iterable["GameObject"], to_send: Text):
        if not to_send:
            self.executor.msg("Nothing to send.")
            return
        if not targets:
            return

        for target in targets:
            can_send, err = target.can_receive_text(self.executor, self.interpreter, to_send, mode=self.name)
            if not can_send:
                continue
            target.receive_text(self.executor, self.interpreter, to_send)


class SayCommand(MushCommand):
    name = 'say'

    def execute(self):
        end_quote = Text('"')
        to_send = await self.parser.evaluate(self.args)
        you_see = Text('You say, "') + to_send + end_quote
        self.executor.receive_text(self.executor, self.interpreter, you_see, mode=self.name)

        for neighbor in self.executor.neighbors(include_exits=True):
            neighbor_sees = Text(f'{neighbor.get_dub_or_keyphrase_for(self.executor)} says, "') + to_send + end_quote
            can_send, err = neighbor.can_receive_text(self.executor, self.interpreter, neighbor_sees, mode=self.name)
            if not can_send:
                continue
            neighbor.receive_text(self.executor, self.interpreter, neighbor_sees, mode=self.name)


class PoseCommand(MushCommand):
    name = 'pose'

    def execute(self):
        to_send = await self.parser.evaluate(self.args)
        you_see = Text('You ') + to_send
        self.executor.receive_text(self.executor, self.interpreter, you_see, mode=self.name)

        for neighbor in self.executor.neighbors(include_exits=True):
            neighbor_sees = Text(f'{neighbor.get_dub_or_keyphrase_for(self.executor)} ') + to_send
            can_send, err = neighbor.can_receive_text(self.executor, self.interpreter, neighbor_sees, mode=self.name)
            if not can_send:
                continue
            neighbor.receive_text(self.executor, self.interpreter, neighbor_sees, mode=self.name)


class SemiPoseCommand(MushCommand):
    name = 'semipose'

    def execute(self):
        to_send = await self.parser.evaluate(self.args)
        you_see = Text('You') + to_send
        self.executor.receive_text(self.executor, self.interpreter, you_see, mode=self.name)

        for neighbor in self.executor.neighbors(include_exits=True):
            neighbor_sees = Text(f'{neighbor.get_dub_or_keyphrase_for(self.executor)}') + to_send
            can_send, err = neighbor.can_receive_text(self.executor, self.interpreter, neighbor_sees, mode=self.name)
            if not can_send:
                continue
            neighbor.receive_text(self.executor, self.interpreter, neighbor_sees, mode=self.name)


class RoleplayCommandMatcher(PythonCommandMatcher):
    priority = 10

    def at_cmdmatcher_creation(self):
        self.add(SayCommand)
        self.add(PoseCommand)
        self.add(SemiPoseCommand)
