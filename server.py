import asyncio
from asyncio.streams import StreamReader, StreamWriter
from datetime import datetime
from models import Chat, Message, User
from utils import BYTES, HOST, PORT, get_logger

logger = get_logger()


class Server:
    def __init__(self, host: str = HOST, port: int = PORT, short_history_depth: int = 20):
        self.host: str = host
        self.port: str = port
        self.connections: dict[str, tuple[StreamReader, StreamWriter]] = {}
        self.users: dict[str, User] = {}
        self.history: list[Message] = []
        self.short_history_depth: int = short_history_depth
        self.chats: dict[str, Chat] = {}

    async def write_to_client(self, address: str, message: str, line_break: bool = True) -> None:
        writer = self.connections[address][1]
        message += '\n' if line_break else ''
        writer.write(message.encode())
        await writer.drain()

    async def read_from_client(self, address: str) -> str:
        answer, reader = '', self.connections[address][0]
        try:
            data = await reader.read(BYTES)
            if not data:
                logger.error("Can't read message from client %s", address)
                return answer
            return data.decode().strip()
        except Exception as error:
            logger.error(error)
            return answer

    async def get_auth_data(self, address: str, new_user: bool = False) -> tuple:
        login, password = '', ''
        while True:
            await self.write_to_client(address, 'Input your login: ', line_break=False)
            login = await self.read_from_client(address)
            if login:
                if new_user and login in self.users:
                    await self.write_to_client(address, 'The login is taken. Input another login.')
                    continue
                await self.write_to_client(address, 'Input your password: ', line_break=False)
                password = await self.read_from_client(address)
                break
        return login, password

    async def create_user(self, address: str) -> str:
        while True:
            login, password = await self.get_auth_data(address, new_user=True)
            await self.write_to_client(address, 'Login and password was set.')
            user_obj = User(login, password)
            user_obj.addresses.append(address)
            self.users[login] = user_obj
            break
        return login

    async def login_user(self, address: str) -> str:
        login, password, is_authorized = '', '', False
        while not is_authorized:
            login, password = await self.get_auth_data(address)
            if login not in self.users:
                await self.write_to_client(address, 'User not found.')
                return ''
            if password != self.users[login].password:
                await self.write_to_client(address, 'Wrong password.')
                return ''
            is_authorized = True
            if address not in self.users[login].addresses:
                self.users[login].addresses.append(address)
            await self.write_to_client(address, 'Login successful.')
        return login

    async def user_authorization(self, address: str) -> str:
        while True:
            await self.write_to_client(address, 'Please, register (/auth) or log in (/login).')
            answer = await self.read_from_client(address)
            if answer == '/auth':
                login = await self.create_user(address)
                break
            elif answer == '/login':
                login = await self.login_user(address)
                if login:
                    break
                continue
            await self.write_to_client(address, 'Command unknown, please repeat.')
        return login

    async def send_short_history(self, address) -> None:
        await self.write_to_client(address, 'You are in general chat.')
        public_messages = [msg for msg in self.history if not msg.is_private]
        for msg in public_messages[-self.short_history_depth:]:
            await self.write_to_client(address, msg.text)

    async def close_client_connection(self, address, login):
        writer = self.connections[address][1]
        logger.info('User %s at %s disconnected.', login, address)
        del self.connections[address]
        user = self.users[login]
        user.addresses.remove(address)
        user.logout_time = datetime.now()
        try:
            writer.close()
            await writer.wait_closed()
        except Exception as error:
            logger.error('Ошибка при закрытии writer клиента %s %s.', address, error)

    async def send_private(self, message, cur_login, address):
        message = message.replace('/send_private', '').strip()
        login, text = message.split(maxsplit=1)
        message_obj = Message(text, cur_login, is_private=True, recipient=login)
        self.history.append(message_obj)
        text = message_obj.text
        if login in self.users and login == cur_login and address in self.users[login].addresses:
            text.replace(f' {login} ', ' me ')
            await self.write_to_client(address, text)
        elif login in self.users and login != cur_login:
            for adr in self.users[login].addresses:
                await self.write_to_client(adr, text)
        else:
            await self.write_to_client(address, 'Wrong user login.')

    async def send(self, message, login, address):
        text = message.replace('/send', '').strip()
        message_obj = Message(text, login)
        self.history.append(message_obj)
        text = message_obj.text
        for adr in self.connections:
            if adr == address:
                text.replace(f' {login} ', ' me ')
            await self.write_to_client(adr, text)

    async def show_unread(self, login, address) -> None:
        user = self.users[login]
        if not user.logout_time:
            return
        unread = [msg for msg in self.history if msg.pub_date > user.logout_time]
        for message in unread:
            if message.is_private and message.login != login:
                continue
            await self.write_to_client(address, message.text)

    async def create_chat(self, message, login, address):
        name = message.replace('/create_chat', '').strip()
        if not name:
            await self.write_to_client(address, 'Chat name can not be empty.')
        elif name in self.chats:
            await self.write_to_client(address, f'Chat {name} already exists.')
        else:
            user = self.users[login]
            chat_obj = Chat(name, admin=user)
            chat_obj.admin = user
            chat_obj.users.append(user)
            self.chats[name] = chat_obj
            await self.write_to_client(address, f'Chat {name} created.')

    async def show_status(self, login, address):
        await self.write_to_client(address, f'Your address is {address}.')
        private_messages = [msg for msg in self.history if msg.is_private and msg.login == login]
        await self.write_to_client(address, f'You have {len(private_messages)} private messages.')
        amount_chats = [chat for chat in self.chats.values() if self.users[login] in chat.users]
        await self.write_to_client(address, f'You are member of {len(amount_chats)} private chats.')
        admin_of_chats = [chat for chat in self.chats.values() if self.users[login] == chat.admin]
        await self.write_to_client(address, f'You are admin of {len(admin_of_chats)} private chats.')

    async def chatting_with_user(self, address: str, login: str) -> None:
        while message := await self.read_from_client(address):
            if message == '/exit':
                await self.write_to_client(address, 'You are disconnected from chat. Have a nice day.\n')
                await self.close_client_connection(address, login)
                break
            elif message == '/show_unread':
                await self.show_unread(login, address)
            elif message == '/status':
                await self.show_status(login, address)
            elif message.startswith('/send_private'):
                await self.send_private(message, login, address)
            elif message.startswith('/send'):
                await self.send(message, login, address)
            elif message.startswith('/create_chat'):
                await self.create_chat(message, login, address)
            else:
                await self.write_to_client(address, 'Wrong command.')

    async def new_connection(self, reader: StreamReader, writer: StreamWriter) -> None:
        ip, port = writer.get_extra_info('peername')
        address = f'{ip}:{port}'
        logger.info('New client connected from %s:%s', ip, port)
        self.connections[address] = reader, writer
        login = await self.user_authorization(address)
        logger.info('User %s authorized.', login)
        await self.send_short_history(address)
        await self.chatting_with_user(address, login)

    async def run_server(self) -> None:
        server_instance = await asyncio.start_server(self.new_connection, self.host, self.port)
        logger.info('Server running at %s:%s', self.host, self.port)
        async with server_instance:
            await server_instance.serve_forever()


if __name__ == '__main__':
    server = Server()
    try:
        asyncio.run(server.run_server())
    except KeyboardInterrupt:
        logger.info('Server stopped')
