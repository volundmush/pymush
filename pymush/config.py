from athanor_server.config import Config as BaseConfig


class Config(BaseConfig):

    def __init__(self):
        super().__init__()
        self.process_name: str = "PyMUSH Server"
        self.application = "athanor_server.app.Application"

    def _config_classes(self):
        super()._config_classes()
        self.classes['game']['connection'] = "pymush.conn.Connection"
        self.classes["game"]["gameobject"] = "pymush.db.gameobject.GameObject"
