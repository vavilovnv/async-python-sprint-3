import logging
import sys

BYTES = 1024 * 5
HOST = '127.0.0.1'
PORT = 8000

EXIT = '/exit'
SHOW_UNREAD_MESSAGES = '/show_unread'
USER_STATUS = '/status'
SEND_PRIVATE_MESSAGE = '/send_private'
SEND_MESSAGE = '/send'
CREATE_CHAT = '/create_chat'
SEND_TO_CHAT = '/send_chat'
INVITE_TO_CHAT = '/invite_chat'
JOIN_TO_CHAT = '/join_chat'

COMMANDS = {
    EXIT: '- disconnect from server',
    SHOW_UNREAD_MESSAGES: '- show all unread message in general chat',
    USER_STATUS: '- show user status',
    SEND_PRIVATE_MESSAGE: '<user_login> <message> - send the private message to a user',
    SEND_MESSAGE: '<message> - send the message to a user',
    CREATE_CHAT: '<chat name> - create a private chat',
    SEND_TO_CHAT: '<chat name> <message> - send the message to a private chat',
    INVITE_TO_CHAT: '<user login> <chat name> - invite a user to a private chat',
    JOIN_TO_CHAT: '<chat name> <invite-key or empty> - join to the private chat, or send request for the invite-key',
}

def get_logger() -> logging.Logger:
    """Настройки логгера для проекта."""

    logging.basicConfig(
        level=logging.INFO,
        stream=sys.stdout,
        format='%(name)s - %(asctime)s - %(levelname)s - %(message)s',
    )
    return logging.getLogger('chat-service')


