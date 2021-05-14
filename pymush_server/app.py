import mudstring
mudstring.install()


from pymush.app import Application as BaseApplication
from .config import Config


class Application(BaseApplication):

    def __init__(self, config: Config):
        super().__init__(config)
        self.link = None
        self.game = None

    def process_protocol_in_events(self):
        for proto in self.net.mudconnections.values():
            if not proto.in_events:
                continue

            if proto.session:
                proto.session.in_events.append(proto.in_events.pop(0))
            elif proto.user:
                pass
            else:
                pass