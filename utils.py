import logging
import sys

BYTES = 1024
HOST = '127.0.0.1'
PORT = 8000

LOGIN = '/login'
AUTH = '/auth'
EXIT = '/exit'
SHOW_UNREAD_MESSAGES = '/unread'
USER_STATUS = '/status'
SEND_PRIVATE_MESSAGE = '/private'
SEND_MESSAGE = '/send'
CREATE_CHAT = '/create'
SEND_TO_CHAT = '/send_chat'
INVITE_TO_CHAT = '/invite'
JOIN_TO_CHAT = '/join'

COMMANDS_DESCRIPTION = {
    EXIT: '- disconnect from server',
    SHOW_UNREAD_MESSAGES: '- show all unread message in general chat',
    USER_STATUS: '- show user status',
    SEND_MESSAGE: '<message> - send the message to a user',
    SEND_PRIVATE_MESSAGE: '<user_login> <message> - send the private message to a user',
    CREATE_CHAT: '<chat name> - create a private chat',
    SEND_TO_CHAT: '<chat name> <message> - send the message to a private chat',
    INVITE_TO_CHAT: '<user login> <chat name> - invite a user to a private chat',
    JOIN_TO_CHAT: '<chat name> <invite-key or empty> - join to the private chat, or send request for the invite-key',
}

AUTH_OR_LOGIN = 'Please, register (/auth) or log in (/login).'
INPUT_LOGIN = 'Input your login: '
INPUT_PASSWORD = 'Input your password: '
GENERAL_CHAT = 'You are in general chat.'
LOGIN_SET = 'Login and password was set.'
LOGIN_SUCCESSFUL = 'Login successful.'


def get_logger() -> logging.Logger:
    """Настройки логгера для проекта."""

    logging.basicConfig(
        level=logging.INFO,
        stream=sys.stdout,
        format='%(name)s - %(asctime)s - %(levelname)s - %(message)s',
    )
    return logging.getLogger('chat-service')


def get_split_values(text: str) -> tuple:
    if ' ' in text:
        value1, value2 = text.split(maxsplit=1)
    else:
        value1 = text
        value2 = ''
    return value1, value2
