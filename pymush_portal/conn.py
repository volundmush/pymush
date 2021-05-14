import random
import string
import time
from typing import List
from pymush.shared import ConnectionDetails, ConnectionInMessageType, ConnectionOutMessage, ConnectionInMessage, ConnectionOutMessageType, MudProtocol


class MudConnection:

    def __init__(self, listener):
        self.listener = listener
        self.conn_id: str = self.generate_name()
        self.details = ConnectionDetails()
        self.details.client_id = self.conn_id
        self.details.protocol = listener.protocol
        self.created = time.time()
        self.running: bool = False
        self.started: bool = False
        self.tls = bool(listener.ssl_context)
        self.out_events: List[ConnectionOutMessage] = list()
        self.in_events: List[ConnectionInMessage] = list()

    def generate_name(self) -> str:
        prefix = f"{self.listener.name}_"

        attempt = f"{prefix}{''.join(random.choices(string.ascii_letters + string.digits, k=20))}"
        while attempt in self.listener.service.mudconnections:
            attempt = f"{prefix}{''.join(random.choices(string.ascii_letters + string.digits, k=20))}"
        return attempt

    def process_out_events(self):
        pass

    def process_in_events(self):
        pass

