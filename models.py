from datetime import datetime
from typing import Optional
from uuid import uuid4


class Message:

    def __init__(self,
                 text: str,
                 login: str,
                 is_private: bool = False,
                 recipient: str = '',
                 chat_name: str = ''):
        self.is_private = is_private
        self.login = login
        self.pub_date = datetime.now()
        self.recipient = recipient
        self.chat_name = chat_name
        self.text = self.format_message(text)

    def format_message(self, text: str) -> str:
        pub_date = self.pub_date.strftime('%Y.%m.%d %H:%M:%S')
        private = 'in private' if self.is_private else ''
        return f'{pub_date} {self.login} {private} says: {text}'


class User:

    def __init__(self, login: str, password: str):
        self.login: str = login
        self.password: str = password
        self.addresses: list[str] = []
        self.logout_time: Optional[datetime] = None
        self.__count_sent_message: int = 0
        self.__pub_date: Optional[datetime] = None
        self.private_chats: dict[str, str] = {}

    @property
    def count_sent_messages(self):
        return self.__count_sent_message

    @count_sent_messages.setter
    def count_sent_messages(self, dt_now):
        if (not self.__pub_date
                or self.__pub_date.date() != dt_now.date()
                or (self.__pub_date.date() == dt_now.date()
                    and self.__pub_date.hour != dt_now.hour)):
            self.__count_sent_message = 1
        else:
            self.__count_sent_message += 1
        self.__pub_date = dt_now


class Chat:

    def __init__(self, name: str, admin: User):
        self.name = name
        self.admin = admin
        self.users = []
        self.__private_keys = {}

    def get_private_key(self, login):
        if login not in self.__private_keys:
            self.__private_keys[login] = uuid4().hex
        return self.__private_keys[login]
