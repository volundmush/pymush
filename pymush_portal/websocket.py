import asyncio
from . conn import MudConnection
from websockets.exceptions import ConnectionClosedError, ConnectionClosed, ConnectionClosedOK


class WebSocketConnection(MudConnection):

    def __init__(self, listener, ws, path):
        super().__init__(listener)
        self.connection = ws
        self.path = path
        self.outbox = asyncio.Queue()
        self.task = None

    async def run(self):
        self.running = True
        self.task = asyncio.create_task(asyncio.gather(self.read(), self.write()))
        await self.task
        self.running = False

    async def read(self):
        try:
            async for message in self.connection:
                await self.process(message)
        except ConnectionClosedError:
            self.task.cancel()
        except ConnectionClosedOK:
            self.task.cancel()
        except ConnectionClosed:
            self.task.cancel()

    async def write(self):
        while self.running:
            msg = await self.outbox.get()
            await self.connection.send(msg)
