import asyncio
from aioconsole import ainput

from utils import BYTES, HOST, PORT


class Client:
    def __init__(self, server_host: str = HOST, server_port: int = PORT):
        self.host = server_host
        self.port = server_port
        self.reader = None
        self.writer = None

    async def receive(self) -> None:
        server_message = ''
        while server_message != '/exit':
            data = await self.reader.read(BYTES)
            if data:
                print(data.decode())
            await asyncio.sleep(0.1)
        self.writer.close()

    async def send(self) -> None:
        client_message = ''
        while client_message != '/exit':
            client_message = await ainput('> ')
            self.writer.write(client_message.encode())
            await self.writer.drain()
            await asyncio.sleep(0.1)

    async def run_client(self) -> None:
        try:
            self.reader, self.writer = await asyncio.open_connection(self.host, self.port)
            await asyncio.gather(self.send(), self.receive())
        except Exception as error:
            print(error)
        print('Disconnected.')


if __name__ == '__main__':
    client = Client()
    asyncio.run(client.run_client())
