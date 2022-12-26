from datetime import datetime
from typing import Optional


class Message:

    def __init__(self, text: str, login: str, is_private: bool = False, recipient: str = ''):
        self.is_private = is_private
        self.login = login
        self.pub_date = datetime.now()
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


class Chat:

    def __init__(self, name: str, admin: User):
        self.name = name
        self.admin = admin
        self.users = []
