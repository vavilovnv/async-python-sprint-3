import asyncio
from asyncio.streams import StreamReader, StreamWriter
from datetime import datetime

from models import Chat, Message, User
from utils import (AUTH_OR_LOGIN, BYTES, CREATE_CHAT, EXIT, GENERAL_CHAT, HOST,
                   INPUT_LOGIN, INPUT_PASSWORD, INVITE_TO_CHAT, JOIN_TO_CHAT,
                   LOGIN_SET, LOGIN_SUCCESSFUL, PORT, SEND_MESSAGE,
                   SEND_PRIVATE_MESSAGE, SEND_TO_CHAT, SHOW_UNREAD_MESSAGES,
                   USER_STATUS, get_logger, get_split_values)

logger = get_logger()


class Server:
    def __init__(self,
                 event_loop: asyncio.AbstractEventLoop,
                 host: str = HOST,
                 port: int = PORT,
                 short_history_depth: int = 20,
                 sent_message_per_user: int = 20):

        self.event_loop: asyncio.AbstractEventLoop = event_loop
        self.host: str = host
        self.port: int = port
        self.short_history_depth: int = short_history_depth
        self.sent_message_per_user: int = sent_message_per_user
        self.connections: dict[str, tuple[StreamReader, StreamWriter]] = {}
        self.users: dict[str, User] = {}
        self.history: list[Message] = []
        self.chats: dict[str, Chat] = {}

    async def write_to_client(self,
                              address: str,
                              message: str,
                              line_break: bool = True) -> None:
        """Отправка сообщения клиенту."""

        connection = self.connections.get(address)
        if not connection:
            return
        writer = connection[1]
        message += '\n' if line_break else ''
        writer.write(message.encode())
        try:
            await writer.drain()
        except Exception as error:
            logger.error(error)
            del self.connections[address]
            try:
                writer.close()
                await writer.wait_closed()
            except Exception as error:
                logger.error(
                    'Error when closing the client connection.',
                    exc_info=error)
        else:
            await asyncio.sleep(0.1)

    async def read_from_client(self, address: str) -> str:
        """Чтение сообщения от клиента."""

        connection = self.connections.get(address)
        if not connection:
            return ''
        answer, reader = '', connection[0]
        try:
            data = await reader.read(BYTES)
            if not data:
                logger.error("Can't read message from client %s", address)
                return answer
            return data.decode().strip()
        except Exception as error:
            logger.error(error)
            return answer

    async def get_auth_data(self,
                            address: str,
                            new_user: bool = False) -> tuple:
        """Получение логина и пароля пользователя."""

        login, password = '', ''
        while True:
            await self.write_to_client(address, INPUT_LOGIN, line_break=False)
            login = await self.read_from_client(address)
            if login:
                if new_user and login in self.users:
                    await self.write_to_client(
                        address,
                        'The login is taken. Input another login.')
                    continue
                await self.write_to_client(
                    address,
                    INPUT_PASSWORD,
                    line_break=False)
                password = await self.read_from_client(address)
                break
        return login, password

    async def create_user(self, address: str) -> str:
        """Обработка запроса на создание нового пользователя."""

        while True:
            login, password = await self.get_auth_data(address, new_user=True)
            await self.write_to_client(address, LOGIN_SET)
            user_obj = User(login, password)
            user_obj.addresses.append(address)
            self.users[login] = user_obj
            logger.info('Create user %s', login)
            break
        return login

    async def login_user(self, address: str) -> str:
        """Обработка запроса на авторизацию ранее зарегистрированного
        пользователя."""

        login, password, is_authorized = '', '', False
        while not is_authorized:
            login, password = await self.get_auth_data(address)
            if login not in self.users:
                await self.write_to_client(address, 'User not found.')
                return ''
            user = self.users[login]
            if password != user.password:
                await self.write_to_client(address, 'Wrong password.')
                return ''
            is_authorized = True
            if address not in user.addresses:
                user.addresses.append(address)
            logger.info('Logging user %s', login)
            await self.write_to_client(address, LOGIN_SUCCESSFUL)
        return login

    async def user_authorization(self, address: str) -> str:
        """Обработка запроса на авторизацию пользователя."""

        while True:
            await self.write_to_client(address, AUTH_OR_LOGIN)
            answer = await self.read_from_client(address)
            if answer == '/auth':
                login = await self.create_user(address)
                break
            elif answer == '/login':
                login = await self.login_user(address)
                if login:
                    break
                continue
            elif answer == '':
                login = answer
                break
            await self.write_to_client(
                address,
                'Command unknown, please repeat.')
        return login

    async def send_short_history(self, address: str) -> None:
        """Отправка краткой истории в количестве self.short_history_depth
        сообщений при входе пользователя в общий чат."""

        await self.write_to_client(address, GENERAL_CHAT)
        public_messages = [msg for msg in self.history if not msg.is_private]
        for msg in public_messages[-self.short_history_depth:]:
            await self.write_to_client(address, msg.text)

    async def close_client_connection(self, address: str, login: str) -> None:
        """Завершение клиентского соединения и удаление адреса пользователя из
         активных соединений."""

        connection = self.connections.get(address)
        if connection:
            writer = connection[1]
            await self.write_to_client(
                address,
                'You are disconnected from chat. Have a nice day.')
            logger.info('User %s at %s disconnected.', login, address)
            del connection
            user = self.users[login]
            user.addresses.remove(address)
            user.logout_time = datetime.now()
            try:
                writer.close()
                await writer.wait_closed()
            except Exception as error:
                logger.error(
                    'Error when closing writer %s %s.',
                    address,
                    error)

    async def send_private(self,
                           message,
                           cur_login: str,
                           address: str) -> None:
        """Обработка запроса на отправку приватного сообщения другому
        пользователю."""

        message = message.replace(SEND_PRIVATE_MESSAGE, '').strip()
        login, text = message.split(maxsplit=1)
        message_obj = Message(
            text,
            cur_login,
            is_private=True,
            recipient=login)
        self.history.append(message_obj)
        text = message_obj.text
        user = self.users[login]
        if (login in self.users
                and login == cur_login
                and address in user.addresses):
            text.replace(f' {login} ', ' me ')
            await self.write_to_client(address, text)
        elif login in self.users and login != cur_login:
            for adr in user.addresses:
                await self.write_to_client(adr, text)
        else:
            await self.write_to_client(address, 'Wrong user login.')

    async def send(self, message: str, login: str, address: str) -> None:
        """Обработка запроса на отправку сообщения в общий чат."""

        text = message.replace(SEND_MESSAGE, '').strip()
        message_obj = Message(text, login)
        text = message_obj.text
        user = self.users[login]
        if user.count_sent_messages == self.sent_message_per_user:
            for adr in user.addresses:
                await self.write_to_client(
                    adr, (f'Sorry, but you have reached your limit '
                          f'of {self.sent_message_per_user} per hour. '
                          f'The message not be sent.'))
            return
        self.history.append(message_obj)
        user.count_sent_messages = datetime.now()
        for adr in self.connections:
            if adr == address:
                text.replace(f' {login} ', ' me ')
            await self.write_to_client(adr, text)

    async def show_unread(self, login: str, address: str) -> None:
        """Обработка запроса на вывод всех непрочитанных сообщений
        с момента последнего выхода из общего чата."""

        user = self.users[login]
        if not user.logout_time:
            return
        unread = [msg for msg in self.history
                  if msg.pub_date > user.logout_time]
        for message in unread:
            if message.is_private and message.login != login:
                continue
            await self.write_to_client(address, message.text)

    async def create_chat(self,
                          message: str,
                          login: str,
                          address: str) -> None:
        """Обработка запроса на создание приватного чата."""

        chat_name = message.replace(CREATE_CHAT, '').strip()
        if not chat_name:
            await self.write_to_client(address, 'Chat name can not be empty.')
        elif chat_name in self.chats:
            await self.write_to_client(
                address,
                f'Chat {chat_name} already exists.')
        else:
            user = self.users[login]
            chat_obj = Chat(chat_name, admin=user)
            chat_obj.admin = user
            chat_obj.users.append(user)
            self.chats[chat_name] = chat_obj
            await self.write_to_client(address, f'Chat {chat_name} created.')

    async def show_status(self, login: str, address: str) -> None:
        """Обработка запроса о статусе пользователя: вывод адрес, количество
         приватных сообщения, администрирование приватных чатов, участие в
         приватных чатах и инвайт-ключи к ним."""

        user = self.users[login]
        await self.write_to_client(address, f'Your address is {address}.')
        private_messages = [msg for msg in self.history
                            if msg.is_private and msg.login == login]
        await self.write_to_client(
            address,
            f'You have {len(private_messages)} private messages.')
        admin_of_chats = [chat for chat in self.chats.values()
                          if user == chat.admin]
        await self.write_to_client(
            address,
            f'You are admin of {len(admin_of_chats)} private chats.')
        amount_chats = [chat for chat in self.chats.values()
                        if user in chat.users]
        await self.write_to_client(
            address,
            f'You are member of {len(amount_chats)} private chats.')
        for k, v in user.private_chats:
            await self.write_to_client(
                address,
                f'The invite key for the chat {k} is {v}.')

    async def send_to_chat(self,
                           message: str,
                           login: str,
                           address: str) -> None:
        """Отправка сообщения в приватный чат."""

        message = message.replace(SEND_TO_CHAT, '').strip()
        chat_name, text = get_split_values(message)
        if chat_name not in self.chats:
            await self.write_to_client(
                address,
                f'Chat {chat_name} not found.')
            return
        if not text:
            await self.write_to_client(
                address,
                'Message text can not be empty.')
            return
        chat = self.chats[chat_name]
        if self.users[login] not in chat.users:
            await self.write_to_client(
                address,
                f'You are not member of chat {chat_name}.')
            return
        message_obj = Message(
            text,
            login,
            is_private=True,
            chat_name=chat_name)
        self.history.append(message_obj)
        addresses = []
        for user in chat.users:
            addresses.extend(user.addresses)
        for adr in addresses:
            if adr == address:
                text.replace(f' {login} ', ' me ')
            await self.write_to_client(adr, message_obj.text)

    async def invite_user_to_chat(self,
                                  message: str,
                                  curr_login: str,
                                  address: str) -> None:
        """Обработка запроса на приглашение пользователя в приватный чат."""

        message = message.replace('/invite_chat', '').strip()
        login, chat_name = get_split_values(message)
        if not login or not chat_name:
            await self.write_to_client(address, 'Wrong commands parameters.')
            return
        if chat_name not in self.chats:
            await self.write_to_client(
                address,
                f'Chat {chat_name} not found.')
            return
        chat = self.chats[chat_name]
        admin = chat.admin
        if self.users[curr_login] != admin:
            await self.write_to_client(
                address,
                f'You are not the admin of chat {chat_name}.')
            return
        if login not in self.users:
            await self.write_to_client(address, f'User {login} not found.')
            return
        user = self.users[login]
        if user in chat.users:
            await self.write_to_client(
                address,
                f'User {login} already added to chat {chat_name}.')
            return
        await self.write_to_client(
            address,
            f'An invitation to user {login} to chat '
            f'{chat_name} has been sent.')
        invite_key = chat.get_private_key(login)
        user.private_chats[chat_name] = invite_key
        for adr in user.addresses:
            await self.write_to_client(
                adr,
                f'You are invited to the chat {chat_name} by an admin '
                f'{curr_login}. Your invite key is {invite_key}')

    async def join_to_chat(self,
                           message: str,
                           login: str,
                           address: str) -> None:
        """Обработка запроса на присоединение пользователя к приватному чату.
        Если у пользователя нет токена, будет отправлен запрос администратору
        чата. Если токен есть и он валиден, пользователь присоединяется к
        чату."""

        message = message.replace(JOIN_TO_CHAT, '').strip()
        chat_name, invite_key = get_split_values(message)
        if not chat_name:
            await self.write_to_client(
                address,
                'Chat name can not be empty.')
            return
        if chat_name not in self.chats:
            await self.write_to_client(
                address,
                f'Chat {chat_name} not found.')
            return
        chat = self.chats[chat_name]
        user = self.users[login]
        admin = chat.admin
        if user in chat.users:
            await self.write_to_client(
                address,
                f'You are already member of chat {chat_name}.')
            return
        if not invite_key:
            await self.write_to_client(
                address,
                ('You need an invite-key to join the chat. '
                 'Send a request to the admin (y/n)?'))
            while True:
                answer = await self.read_from_client(address)
                if answer == 'y':
                    await self.write_to_client(
                        address,
                        'A request has been sent to the admin.')
                    for adr in admin.addresses:
                        await self.write_to_client(
                            adr,
                            f'User {login} wants to join the chat '
                            f'{chat_name}.',
                            line_break=True)
                    return
                elif answer == 'n':
                    return
                else:
                    await self.write_to_client(
                        address,
                        'Send a request to the admin (y/n)?')
        if invite_key != chat.get_private_key(login):
            await self.write_to_client(
                address,
                'The invite-key is invalid.')
            return
        await self.write_to_client(
            address,
            f'You are join to chat {chat_name}.')
        chat.users.append(user)

    async def chatting_with_user(self, address: str, login: str) -> None:
        """Обработка запросов от клиентов."""

        while True:
            message = await self.read_from_client(address)
            if message == EXIT:
                await self.close_client_connection(address, login)
                break
            elif message == SHOW_UNREAD_MESSAGES:
                await self.show_unread(login, address)
            elif message == USER_STATUS:
                await self.show_status(login, address)
            elif message.startswith(SEND_PRIVATE_MESSAGE):
                await self.send_private(message, login, address)
            elif message.startswith(SEND_TO_CHAT):
                await self.send_to_chat(message, login, address)
            elif message.startswith(SEND_MESSAGE):
                await self.send(message, login, address)
            elif message.startswith(CREATE_CHAT):
                await self.create_chat(message, login, address)
            elif message.startswith(INVITE_TO_CHAT):
                await self.invite_user_to_chat(message, login, address)
            elif message.startswith(JOIN_TO_CHAT):
                await self.join_to_chat(message, login, address)
            else:
                await self.write_to_client(address, 'Wrong command.')

    async def new_connection(self,
                             reader: StreamReader,
                             writer: StreamWriter) -> None:
        """Установка нового соединения с клиентом."""

        ip, port = writer.get_extra_info('peername')
        address = f'{ip}:{port}'
        logger.info('New client connected from %s:%s', ip, port)
        self.connections[address] = reader, writer
        login = await self.user_authorization(address)
        if login:
            logger.info('User %s authorized.', login)
            await self.send_short_history(address)
            await self.chatting_with_user(address, login)

    async def run_server(self) -> None:
        await asyncio.start_server(self.new_connection, self.host, self.port)
        logger.info('Server running at %s:%s', self.host, self.port)


if __name__ == '__main__':
    loop = asyncio.new_event_loop()
    server = Server(loop)
    loop.create_task(server.run_server())
    try:
        loop.run_forever()
    except KeyboardInterrupt:
        logger.info('Server stopped')
