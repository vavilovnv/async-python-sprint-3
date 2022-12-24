import asyncio
from asyncio.streams import StreamReader, StreamWriter
from utils import BYTES, HOST, PORT, get_logger

logger = get_logger()


class Server:
    def __init__(self, host: str = HOST, port: int = PORT):
        self.host, self.port = host, port
        self.clients = {}

    async def write_to_client(self, address: str, message: str):
        writer = self.clients[address][1]
        writer.write(message.encode())
        await writer.drain()

    async def read_from_client(self, address: str) -> str:
        answer = ''
        reader = self.clients[address][0]
        try:
            data = await reader.read(BYTES)
            if not data:
                logger.error("Can't read message from client %s", address)
                return answer
            answer = data.decode()
        except Exception as error:
            logger.error(error)
            return answer
        return answer

    def registration_new_client(self, address: str, reader_writer: tuple):
        self.clients[address] = reader_writer

    async def welcome_new_client(self, address: str) -> str:
        await self.write_to_client(address, 'You are welcome!\n')
        while True:
            answer = await self.read_from_client(address)
            if answer == '/auth':
                login = ''
                break
            elif answer == '/signin':
                login = ''
                break
            await self.write_to_client(address, 'Command unknown, please repeat.')
        return login

    async def new_connections(self, reader: StreamReader, writer: StreamWriter) -> None:
        ip, port = writer.get_extra_info('peername')
        address = f'{ip}:{port}'
        logger.info('New client connected from %s:%s', ip, port)
        self.registration_new_client(address, (reader, writer))
        await self.welcome_new_client(address)

    async def run_server(self) -> None:
        server_instance = await asyncio.start_server(self.new_connections, self.host, self.port)
        logger.info('Server running at %s:%s', self.host, self.port)
        async with server_instance:
            await server_instance.serve_forever()

    def listen(self):
        pass


if __name__ == '__main__':
    server = Server()
    try:
        asyncio.run(server.run_server())
    except KeyboardInterrupt:
        logger.info('Server stopped')
