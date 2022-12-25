import asyncio
from asyncio.streams import StreamReader, StreamWriter
from datetime import datetime
from utils import BYTES, HOST, PORT, get_logger, format_message

logger = get_logger()


class Server:
    def __init__(self, host: str = HOST, port: int = PORT, short_history_depth: int = 20):
        self.host, self.port = host, port
        self.clients = {}
        self.users_auth_data = {}
        self.history = []
        self.short_history_depth = short_history_depth

    async def write_to_client(self, address: str, message: str, line_break: bool = True) -> None:
        writer = self.clients[address][1]
        message += '\n' if line_break else ''
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
        login, password = '', ''
        while True:
            await self.write_to_client(address, 'Input your login: ', line_break=False)
            login = await self.read_from_client(address)
            if login:
                if new_user and login in self.users_auth_data:
                    await self.write_to_client(address, 'The login is taken. Input another login.')
                    continue
                await self.write_to_client(address, 'Input your password: ', line_break=False)
                password = await self.read_from_client(address)
                break
        return login, password

    async def authorize_new_user(self, address: str) -> str:
        while True:
            login, password = await self.get_auth_data(address, new_user=True)
            await self.write_to_client(address, 'Login and password was set.')
            self.users_auth_data[login] = password, [address]
            break
        return login

    async def login_user(self, address: str) -> str:
        login, is_authorized = '', False
        while not is_authorized:
            login, password = await self.get_auth_data(address)
            if login not in self.users_auth_data:
                await self.write_to_client(address, 'User not found.')
                return ''
            if password != self.users_auth_data[login]:
                await self.write_to_client(address, 'Wrong password.')
                return ''
            is_authorized = True
            if address not in self.users_auth_data[login][1]:
                self.users_auth_data[login][1].append(address)
            await self.write_to_client(address, 'Login successful.')
        return login

    async def user_authorization(self, address: str) -> str:
        while True:
            await self.write_to_client(address, 'Please, register (/auth) or log in (/login).')
            answer = await self.read_from_client(address)
            if answer == '/auth':
                login = await self.authorize_new_user(address)
                break
            elif answer == '/login':
                login = await self.login_user(address)
                if login:
                    break
                continue
            await self.write_to_client(address, 'Command unknown, please repeat.')
        return login

    async def send_to_all(self, message, login, address):
        for adr in self.clients:
            if adr == address:
                login = 'me'
            await self.write_to_client(adr, format_message(message, login))

    async def send_private(self, message, cur_login, address):
        message = message.replace('/private', '').strip()
        login, message = message.split(maxsplit=1)
        if login in self.users_auth_data and login == cur_login:
            await self.write_to_client(address, format_message(message, 'me', is_private=True))
        elif login in self.users_auth_data and login != cur_login:
            for adr in self.users_auth_data[login][1]:
                await self.write_to_client(adr, format_message(message, login, is_private=True))
        else:
            await self.write_to_client(address, 'Wrong user login.')

    async def send_short_history(self, address) -> None:
        await self.write_to_client(address, 'You are in general chat.')
        for msg in self.history[:self.short_history_depth]:
            await self.write_to_client(address, msg[1])

    async def close_client_connection(self, address, login):
        writer = self.clients[address][1]
        logger.info('User %s at %s disconnected.', login, address)
        del self.clients[address]
        try:
            writer.close()
            await writer.wait_closed()
        except Exception as error:
            logger.error('Ошибка при закрытии writer клиента %s %s.', address, error)

    async def chat_with_client(self, address: str, login: str) -> None:
        while message := await self.read_from_client(address):
            if message == '/exit':
                await self.write_to_client(address, 'You are disconnected from chat. Have a nice day.\n')
                await self.close_client_connection(address, login)
                break
            elif message.startswith('/send private'):
                await self.send_private(message, login, address)
            elif message.startswith('/send'):
                message = message.replace('/send', '').strip()
                self.history.append(format_message(message, login))
                await self.send_to_all(message, login, address)
            else:
                await self.write_to_client(address, 'Wrong command.')

    async def new_connection(self, reader: StreamReader, writer: StreamWriter) -> None:
        ip, port = writer.get_extra_info('peername')
        address = f'{ip}:{port}'
        logger.info('New client connected from %s:%s', ip, port)
        self.add_new_client(address, (reader, writer))
        login = await self.user_authorization(address)
        logger.info('User %s authorized.', login)
        await self.send_short_history(address)
        await self.chat_with_client(address, login)

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
