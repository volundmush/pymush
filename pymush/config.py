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
        self.mushcode_functions = set()

    def setup(self):
        super().setup()
        self._config_matchers()
        self._config_styles()
        self._config_option_classes()
        self._config_game_options()
        self._config_mushcode_functions()

    def _config_classes(self):
        super()._config_classes()
        self.classes['game']['connection'] = "pymush.conn.Connection"
        self.classes["game"]["gameobject"] = "pymush.db.objects.base.GameObject"
        self.classes["game"]["gamesession"] = "pymush.conn.GameSession"
        self.classes['services']['game'] = "pymush.game.GameService"

        self.classes['gameobject']['ALLIANCE'] = 'pymush.db.objects.alliance.Alliance'
        self.classes['gameobject']['BOARD'] = 'pymush.db.objects.board.Board'
        self.classes['gameobject']['CHANNEL'] = 'pymush.db.objects.channel.Channel'
        self.classes['gameobject']['DIMENSION'] = 'pymush.db.objects.dimension.Dimension'
        self.classes['gameobject']['DISTRICT'] = 'pymush.db.objects.district.District'
        self.classes['gameobject']['EXIT'] = 'pymush.db.objects.exit.Exit'
        self.classes['gameobject']['FACTION'] = 'pymush.db.objects.faction.Faction'
        self.classes['gameobject']['GATEWAY'] = 'pymush.db.objects.gateway.Gateway'
        self.classes['gameobject']['HEAVENLYBODY'] = 'pymush.db.objects.heavenlybody.HeavenlyBody'
        self.classes['gameobject']['ITEM'] = 'pymush.db.objects.item.Item'
        self.classes['gameobject']['MOBILE'] = 'pymush.db.objects.mobile.Mobile'
        self.classes['gameobject']['PLAYER'] = 'pymush.db.objects.player.Player'
        self.classes['gameobject']['ROOM'] = 'pymush.db.objects.room.Room'
        self.classes['gameobject']['SECTOR'] = 'pymush.db.objects.sector.Sector'
        self.classes['gameobject']['THING'] = 'pymush.db.objects.thing.Thing'
        self.classes['gameobject']['USER'] = 'pymush.db.objects.user.User'
        self.classes['gameobject']['VEHICLE'] = 'pymush.db.objects.vehicle.Vehicle'
        self.classes['gameobject']['WILDERNESS'] = 'pymush.db.objects.wilderness.Wilderness'
        self.classes['gameobject']['ZONE'] = 'pymush.db.objects.zone.Zone'

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
        self.command_matchers['session'] = {
            'session': 'pymush.engine.commands.session.SessionCommandMatcher'
        }

        self.command_matchers['mobile'] = {
            'mobile': 'pymush.engine.commands.mobile.MobileCommandMatcher',
            'exit': 'pymush.engine.commands.mobile.MobileExitMatcher'
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

    def _config_game_options(self):
        self.dub_system = False

    def _config_mushcode_functions(self):
        from pymush.engine.functions.string import STRING_FUNCTIONS
        self.mushcode_functions.update(STRING_FUNCTIONS)

        from pymush.engine.functions.utility import VAR_FUNCTIONS
        self.mushcode_functions.update(VAR_FUNCTIONS)

        from pymush.engine.functions.boolean import BOOLEAN_FUNCTIONS
        self.mushcode_functions.update(BOOLEAN_FUNCTIONS)
