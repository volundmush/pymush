from pymush.app import BaseConfig


class Config(BaseConfig):

    def __init__(self):
        super().__init__()
        self.name = "server"
        self.process_name: str = "PyMUSH Server"
        self.application = "pymush_server.app.Application"

    def _config_classes(self):
        self.classes['services']['link'] = "pymush_server.link.LinkService"
        self.classes['service']['game'] = 'pymush_server.game.GameService'