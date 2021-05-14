import re
import sys
import time
import traceback
from collections import defaultdict
from pymush.utils.misc import partial_match
from . base import Command, MushCommand, CommandException, PythonCommandMatcher
from rich.text import Text

from pymush.db.importer import Importer
from pymush.db.flatfile import check_password
from pymush.utils import formatter as fmt
from pymush.utils.text import tabular_table


class HelpCommand(Command):
    """
    This is the help command.
    """
    name = "help"
    re_match = re.compile(r"^(?P<cmd>help)(?: +(?P<args>.+)?)?", flags=re.IGNORECASE)

    def execute(self):
        obj_chain = self.enactor.get_full_chain()

        categories = defaultdict(set)
        for k, v in obj_chain.items():
            for m in v.get_cmd_matchers():
                m.populate_help(self.enactor, categories)

        gdict = self.match_obj.groupdict()
        args = gdict.get('args', None)

        if not args:
            self.display_help(categories)
        else:
            self.display_help_file(categories, args)

    def display_help(self, data):
        cat_sort = sorted(data.keys())
        out = fmt.FormatList(self.enactor)
        out.add(fmt.Header("Help: Available Commands"))
        for cat_key in cat_sort:
            cat = data[cat_key]
            out.add(fmt.Subheader(cat_key))
            cmds = sorted([cmd for cmd in cat], key=lambda x: x.name)
            out.add(fmt.TabularTable([AnsiString.send_menu(cmd.name, commands=[(f'help {cmd.name}', f"help {cmd.name}")]) for cmd in cmds]))
        out.add(fmt.Footer("help <command> for further help"))
        self.enactor.send(out)

    def display_help_file(self, data, name):
        total = set()
        for k, v in data.items():
            total.update(v)

        if not (found := partial_match(name, total, key=lambda x: x.name)):
            raise CommandException(f"No help for: {name}")
        found.help(self.enactor)
