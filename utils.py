import logging
import sys

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
