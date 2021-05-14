import time
from datetime import timedelta
from .net import MudNetManager
from .protocol import MudProtocol
from .engine.cmdqueue import CmdQueue
from collections import OrderedDict
from .db.gameobject import GameSession, GameObject
from .db.attributes import AttributeManager


class Application:

    def __init__(self, config):
        self.config = config
        self.net = MudNetManager(self)
        self.running: bool = False
        self.queue = CmdQueue(self)
        self.objects: OrderedDict[int, GameObject] = OrderedDict()
        self.attributes = AttributeManager(self)
        self.sysattributes = AttributeManager(self)
        self.sessions: OrderedDict[int, GameSession] = OrderedDict()

    def setup(self):
        self.setup_net()

    def setup_net(self):
        for key, data in self.config.get("ssl_contexts", dict()).items():
            self.net.register_ssl(key, data)

        for key, interface in self.config.get("interfaces", dict()).items():
            self.net.register_interface(key, interface)

        for key, data in self.config.get("listeners", dict()).items():
            self.net.register_listener(key, data["interface"], data["port"], MudProtocol(data["protocol"]),
                                       data.get('ssl', None))

    def run(self):

        interval = 0.01
        delta = interval

        self.running = True

        while self.running:
            now = time.clock_gettime(time.CLOCK_PROCESS_CPUTIME_ID)

            self.net.poll()
            if self.net.ready_listeners:
                self.net.accept_connections()

            if self.net.ready_readers:
                self.net.read_bytes()

            if self.net.ready_writers:
                self.net.write_bytes()

            after = time.clock_gettime(time.CLOCK_PROCESS_CPUTIME_ID)
            delta = after - now

            if interval > delta:
                time.sleep(interval - delta)
            else:
                time.sleep(0)
