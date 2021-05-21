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
        self.option_class_modules = list()

    def setup(self):
        super().setup()
        self._config_matchers()
        self._config_styles()
        self._config_option_classes()

    def _config_classes(self):
        super()._config_classes()
        self.classes['game']['connection'] = "pymush.conn.Connection"
        self.classes["game"]["gameobject"] = "pymush.db.gameobject.GameObject"
        self.classes['services']['game'] = "pymush.game.GameService"
        self.classes['gameobject']['ALLIANCE'] = 'pymush.db.gameobject.Alliance'
        self.classes['gameobject']['BOARD'] = 'pymush.db.gameobject.Board'
        self.classes['gameobject']['CHANNEL'] = 'pymush.db.gameobject.Channel'
        self.classes['gameobject']['DIMENSION'] = 'pymush.db.gameobject.Dimension'
        self.classes['gameobject']['DISTRICT'] = 'pymush.db.gameobject.District'
        self.classes['gameobject']['EXIT'] = 'pymush.db.gameobject.Exit'
        self.classes['gameobject']['FACTION'] = 'pymush.db.gameobject.Faction'
        self.classes['gameobject']['GATEWAY'] = 'pymush.db.gameobject.Gateway'
        self.classes['gameobject']['HEAVENLYBODY'] = 'pymush.db.gameobject.HeavenlyBody'
        self.classes['gameobject']['ITEM'] = 'pymush.db.gameobject.Item'
        self.classes['gameobject']['MOBILE'] = 'pymush.db.gameobject.Mobile'
        self.classes['gameobject']['PLAYER'] = 'pymush.db.gameobject.Player'
        self.classes['gameobject']['ROOM'] = 'pymush.db.gameobject.Room'
        self.classes['gameobject']['SECTOR'] = 'pymush.db.gameobject.Sector'
        self.classes['gameobject']['THING'] = 'pymush.db.gameobject.Thing'
        self.classes['gameobject']['USER'] = 'pymush.db.gameobject.User'
        self.classes['gameobject']['VEHICLE'] = 'pymush.db.gameobject.Vehicle'
        self.classes['gameobject']['WILDERNESS'] = 'pymush.db.gameobject.Wilderness'
        self.classes['gameobject']['ZONE'] = 'pymush.db.gameobject.Zone'

    def _config_regex(self):
        self.regex['basic_name'] = re.compile(r"(?s)^(\w|\.|-| |'|_)+$")
        self.regex['email_name'] = re.compile(r"(?s)^(\w|\.|-| |'|@|_)+$")

    def _config_matchers(self):
        self.command_matchers['login'] = {
            'login': 'pymush.engine.commands.login.LoginCommandMatcher'
        }
        self.command_matchers['selectscreen'] = {
            'selectscreen': 'pymush.engine.commands.selectscreen.SelectCommandMatcher'
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

    def _config_option_classes(self):
        self.option_class_modules = [
            'pymush.utils.optionclasses'
        ]
