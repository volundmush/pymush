from athanor_server.config import Config as BaseConfig


class Config(BaseConfig):

    def __init__(self):
        super().__init__()
        self.process_name: str = "PyMUSH Server"
        self.application = "pymush.app.Application"

    def _config_classes(self):
        super()._config_classes()
        self.classes['game']['connection'] = "pymush.conn.Connection"
        self.classes["game"]["gameobject"] = "pymush.db.gameobject.GameObject"
        self.classes["game"]["user"] = "pymush.db.user.User"
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
