import asyncio
from asyncio import StreamReader, StreamWriter
from typing import Optional
from signal import signal, SIGPIPE, SIG_DFL
from aioconsole import ainput
from utils import BYTES, COMMANDS_DESCRIPTION, HOST, PORT, EXIT


signal(SIGPIPE, SIG_DFL)


class Client:
    def __init__(self, server_host: str = HOST, server_port: int = PORT):
        self.host = server_host
        self.port = server_port
        self.reader: Optional[StreamReader] = None
        self.writer: Optional[StreamWriter] = None

    async def receive(self) -> None:
        server_message = ''
        while server_message != EXIT:
            try:
                data = await self.reader.read(BYTES)
            except Exception as error:
                print(error)
            else:
                if data:
                    print(data.decode())
                await asyncio.sleep(0.1)
        try:
            self.writer.close()
            await self.writer.wait_closed()
        except Exception as error:
            print(error)

    async def send(self) -> None:
        client_message = ''
        while client_message != EXIT:
            client_message = await ainput('> ')
            self.writer.write(client_message.encode())
            await self.writer.drain()
            await asyncio.sleep(0.1)
        print('Client disconnected.')
        self.writer.close()

    async def run_client(self) -> None:
        print('Commands description:')
        print(*[f'{k} {v}' for k, v in COMMANDS_DESCRIPTION.items()], sep='\n')
        print()
        try:
            self.reader, self.writer = await asyncio.open_connection(self.host, self.port)
            await asyncio.gather(self.send(), self.receive())
        except Exception as error:
            print(error)
        print('Client disconnected.')


if __name__ == '__main__':
    client = Client()
    try:
        asyncio.run(client.run_client())
    except KeyboardInterrupt:
        print('Disconnected.')
