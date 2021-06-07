from athanor_server.config import Config as BaseConfig
from collections import defaultdict
import re


class Config(BaseConfig):

    def __init__(self):
        super().__init__()
        self.process_name: str = "PyMUSH Server"
        self.application = "pymush.app.Application"
        self.command_matchers = defaultdict(dict)
        self.styles = defaultdict(dict)
        self.gather_modules = defaultdict(list)
        self.game_options = dict()

    def setup(self):
        super().setup()
        self._config_matchers()
        self._config_styles()
        self._config_gather_modules()
        self._config_game_options()

    def _config_classes(self):
        super()._config_classes()
        self.classes['game']['connection'] = "pymush.conn.Connection"
        self.classes["game"]["gamesession"] = "pymush.conn.GameSession"
        self.classes["game"]["attributemanager"] = "pymush.db.attributes.AttributeManager"
        self.classes["game"]["attributehandler"] = "pymush.db.attributes.AttributeHandler"
        self.classes["game"]["scripthandler"] = "pymush.db.scripts.ScriptHandler"
        self.classes['game']['contentshandler'] = "pymush.db.objects.base.ContentsHandler"
        self.classes['services']['game'] = "pymush.game.GameService"

        self.classes['gameobject']['EXIT'] = 'pymush.db.objects.exit.Exit'
        self.classes['gameobject']['PLAYER'] = 'pymush.db.objects.player.Player'
        self.classes['gameobject']['ROOM'] = 'pymush.db.objects.room.Room'
        self.classes['gameobject']['THING'] = 'pymush.db.objects.thing.Thing'
        self.classes['gameobject']['USER'] = 'pymush.db.objects.user.User'

    def _config_regex(self):
        self.regex['basic_name'] = re.compile(r"(?s)^(\w|\.|-| |'|_)+$")
        self.regex['email_name'] = re.compile(r"(?s)^(\w|\.|-| |'|@|_)+$")

    def _config_matchers(self):
        m = self.command_matchers
        m['login'] = {
            'login': 'pymush.engine.commands.login.LoginCommandMatcher'
        }

        m['ooc'] = {
            'ooc': 'pymush.engine.commands.ooc.SelectCommandMatcher'
        }

        m['ic'] = {
            'ic': 'pymush.engine.commands.ic.SessionCommandMatcher'
        }

        m['thing'] = {
            'thing': 'pymush.engine.commands.thing.ThingCommandMatcher',
            'exit': 'pymush.engine.commands.thing.ThingExitMatcher',
            'script': 'pymush.engine.commands.scripting.ScriptCommandMatcher'
        }

    def _config_styles(self):
        self.styles['system'] = {
            "border_color": ("Headers, footers, table borders, etc.", "Color", "m"),
            "header_star_color": ("* inside Header lines.", "Color", "hm"),
            "header_text_color": ("Text inside Header lines.", "Color", "hw"),
            "header_fill": ("Fill for Header lines.", "Text", "="),
            "subheader_fill": ("Fill for SubHeader lines.", "Text", "="),
            "subheader_text_color": ("Text inside SubHeader lines.", "Color", "hw"),
            "separator_star_color": ("* inside Separator lines.", "Color", "n"),
            "separator_text_color": ("Text inside Separator lines.", "Color", "w"),
            "separator_fill": ("Fill for Separator Lines.", "Text", "-"),
            "footer_star_color": ("* inside Footer lines.", "Color", "n"),
            "footer_text_color": ("Text inside Footer Lines.", "Color", "n"),
            "footer_fill": ("Fill for Footer Lines.", "Text", "="),
            "column_names_color": ("Table column header text.", "Color", "g"),
            "help_category_color": ("Help category names.", "Color", "n"),
            "help_entry_color": ("Help entry names.", "Color", "n"),
            "timezone": ("Timezone for dates. @tz for a list.", "Timezone", "UTC"),
        }

    def _config_gather_modules(self):
        self.gather_modules['optionclasses'].append('pymush.utils.optionclasses')

        self.gather_modules['functions'].extend([
            'pymush.engine.functions.string',
            'pymush.engine.functions.utility',
            'pymush.engine.functions.boolean',
            'pymush.engine.functions.math'
        ])

    def _config_game_options(self):
        o = self.game_options
        o['dub_system'] = False
        o['default_start'] = 1
        o['type_start'] = dict()
        o['default_alevel'] = 0
        o['type_alevel'] = dict()
        o['function_invocation_limit'] = 10000
        o['function_recursion_limit'] = 3000
        o['max_cpu_time'] = 4.0
