import asyncio
from asyncio.streams import StreamReader, StreamWriter
from datetime import datetime
from utils import BYTES, HOST, PORT, get_logger

logger = get_logger()


class Server:
    def __init__(self, host: str = HOST, port: int = PORT):
        self.host, self.port = host, port
        self.clients = {}
        self.users_auth_data = {}
        self.history = []

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
            answer = data.decode().strip()
        except Exception as error:
            logger.error(error)
            return answer
        return answer

    def add_new_client(self, address: str, reader_writer: tuple):
        self.clients[address] = reader_writer

    async def get_auth_data(self, address: str, new_user: bool = False) -> tuple:
        while True:
            await self.write_to_client(address, 'Input your login: ')
            login = await self.read_from_client(address)
            if login:
                if new_user and login in self.users_auth_data:
                    await self.write_to_client(address, 'The login is taken. Input another login.\n')
                    continue
                await self.write_to_client(address, 'Input your password: ')
                password = await self.read_from_client(address)
                break
        return login, password

    async def authorize_new_user(self, address: str) -> str:
        while True:
            login, password = await self.get_auth_data(address, new_user=True)
            await self.write_to_client(address, 'Login and password was set.\n')
            self.users_auth_data[login] = password
            break
        return login

    async def login_user(self, address: str) -> str:
        is_authorized = False
        while not is_authorized:
            login, password = await self.get_auth_data(address)
            if login not in self.users_auth_data:
                await self.write_to_client(address, 'User not found.\n')
                return ''
            if password != self.users_auth_data[login]:
                await self.write_to_client(address, 'Wrong password.\n')
                return ''
            is_authorized = True
            await self.write_to_client(address, 'Login successful.\n')
        return login

    async def user_authorization(self, address: str) -> str:
        await self.write_to_client(address, 'Please, register (/auth) or log in (/login).\n')
        while True:
            answer = await self.read_from_client(address)
            if answer == '/auth':
                login = await self.authorize_new_user(address)
                break
            elif answer == '/login':
                login = await self.login_user(address)
                if login:
                    break
                continue
            await self.write_to_client(address, 'Command unknown, please repeat.\n')
        return login

    async def send_to_all(self, message, login, address):
        for adr in self.clients:
            time_now = datetime.now()
            if adr == address:
                msg = f'{time_now} me says: {message}\n'
            else:
                msg = f'{time_now} {login} says: {message}\n'
            await self.write_to_client(adr, msg)

    async def new_connection(self, reader: StreamReader, writer: StreamWriter) -> None:
        ip, port = writer.get_extra_info('peername')
        address = f'{ip}:{port}'
        logger.info('New client connected from %s:%s', ip, port)
        self.add_new_client(address, (reader, writer))
        login = await self.user_authorization(address)
        await self.write_to_client(address, 'You are in general chat.\n')
        while True:
            message = await self.read_from_client(address)
            if message == '/exit':
                await self.write_to_client(address, 'You are disconnected from chat. Have a nice day.\n')
                writer.close()
                logger.info('User %s at %s disconnected.', login, address)
                break
            else:
                self.history.append(message)
                await self.send_to_all(message, login, address)

    async def run_server(self) -> None:
        server_instance = await asyncio.start_server(self.new_connection, self.host, self.port)
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
