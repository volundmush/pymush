from pymush.app import BaseConfig


class Config(BaseConfig):

    def __init__(self):
        super().__init__()
        self.name = "portal"
        self.process_name = "PyMUSH Portal"
        self.application = "pymush_portal.app.Application"
        self.listeners = dict()

    def setup(self):
        super().setup()
        self._config_listeners()

    def _config_listeners(self):
        self.listeners["telnet"] = {"interface": "any", "port": 7999, "protocol": 0}

    def _config_classes(self):
        self.classes['services']['net'] = 'pymush_portal.net.NetService'
        self.classes['services']['link'] = "pymush_portal.link.LinkService"


