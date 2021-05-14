import ssl
import logging
import socket
import time

from collections import defaultdict
from pymush.utils import import_from_module
from logging.handlers import TimedRotatingFileHandler
from typing import List, Set, Union, Optional, Dict


class BaseConfig:

    def __init__(self):
        self.name = 'pymush'
        self.process_name = "PyMUSH Application"
        self.application = 'pymush.app.Application'
        self.classes = defaultdict(dict)
        self.interval = 0.01
        self.interfaces = dict()
        self.tls = dict()
        self.tls_contexts = dict()
        self.log_handlers = dict()
        self.logs = dict()
        self.regex = dict()
        self.link = dict()

    def setup(self):
        self._config_classes()
        self._config_interfaces()
        self._config_tls()
        self._init_tls_contexts()
        self._config_log_handlers()
        self._config_logs()
        self._config_regex()
        self._config_link()

    def _config_link(self):
        self.link = {
            "interface": "localhost",
            "port": 7998
        }

    def _config_classes(self):
        """
        Meant to add all necessary classes to the classes dictionary.
        """
        pass

    def _config_interfaces(self):
        """
        This lets you assign a name to an interface. 'internal' is for things hosted on an
        loopback is for hosting on the host itself with no access from other computers.
        internal is for your internal network. Same as loopback unless configured otherwise.
        external is for any internet-facing adapters.
        """
        self.interfaces['loopback'] = "localhost"
        self.interfaces['internal'] = "localhost"
        self.interfaces['external'] = socket.gethostname()
        self.interfaces["public"] = socket.gethostname()
        self.interfaces["any"] = ""
        self.interfaces["localhost"] = "localhost"

    def _config_tls(self):
        """
        can have multiple contexts for different TLS/SSL cert combos.
        These must be file paths to the certifications/keys in question.
        """
        pass

    def _init_tls_contexts(self):
        for k, v in self.tls.items():
            new_context = ssl.SSLContext(ssl.PROTOCOL_TLS)
            new_context.load_cert_chain(v['pem'], v['key'])
            self.tls_contexts[k] = new_context

    def _config_servers(self):
        pass

    def _config_clients(self):
        pass

    def _config_log_handlers(self):
        for name in ('application', 'server', 'client'):
            handler = TimedRotatingFileHandler(filename=f'logs/{name}.log', when='D')
            self.log_handlers[name] = handler

    def _config_logs(self):
        for name in ('application', 'server', 'client'):
            log = logging.getLogger(name)
            log.addHandler(self.log_handlers[name])
            self.logs[name] = log

    def _config_regex(self):
        """
        Compiling a regex is expensive, so do it once, here, and save it to self.regex for safekeeping.
        """


class LauncherConfig:

    def __init__(self):
        self.applications = ["portal", "server"]


class Application:

    def __init__(self, config: BaseConfig):
        self.config: BaseConfig = config
        self.classes = defaultdict(dict)
        self.services: Dict[str, Service] = dict()
        self.services_update: List[Service] = list()
        self.running: bool = True

    def setup(self):
        found_classes = list()
        # Import all classes from the given config object.
        for category, d in self.config.classes.items():
            for name, path in d.items():
                found = import_from_module(path)
                found.app = self
                self.classes[category][name] = found
                if hasattr(found, 'class_init'):
                    found_classes.append(found)

        for name, v in sorted(self.classes['services'].items(), key=lambda x: getattr(x[1], 'init_order', 0)):
            self.services[name] = v()

        self.services_update = sorted(self.services.values(), key=lambda x: getattr(x, 'update_order', 0))

        for service in sorted(self.services.values(), key=lambda s: getattr(s, 'load_order', 0)):
            service.setup()

        for cls in found_classes:
            cls.class_init()

    def before_loop(self, delta: float):
        pass

    def after_loop(self, delta: float):
        pass

    def start(self):
        interval = self.config.interval
        delta = interval

        self.running = True

        while self.running:
            now = time.time()
            self.before_loop(delta)
            for s in self.services_update:
                s.update(delta)

            after = time.time()
            delta = after - now

            if interval > delta:
                time.sleep(interval - delta)
            else:
                time.sleep(0)


class Service:
    name = None
    init_order = 0
    setup_order = 0
    update_order = 0

    def setup(self):
        pass

    def start(self):
        pass

    def update(self, delta: float):
        pass