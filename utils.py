import logging
import sys
from datetime import datetime

BYTES = 1024 * 5
HOST = '127.0.0.1'
PORT = 8000


def get_logger() -> logging.Logger:
    """Настройки логгера для проекта."""

    logging.basicConfig(
        level=logging.INFO,
        stream=sys.stdout,
        format='%(name)s - %(asctime)s - %(levelname)s - %(message)s',
    )
    return logging.getLogger('chat-service')


def format_datatime(datetime: datetime) -> str:
    pattern = '%Y.%m.%d %H:%M:%S'
    return datetime.strftime(pattern)


def format_message(message: str, login: str, is_private: bool = False) -> str:
    date_time = format_datatime(datetime.now())
    private = 'in private' if is_private else ''
    return f'{date_time} {login} {private} says: {message}'
