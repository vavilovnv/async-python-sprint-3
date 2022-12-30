import asyncio
import socket
import threading
import time
from signal import SIG_DFL, SIGPIPE, signal
from unittest import TestCase

from server import Server
from utils import (AUTH, AUTH_OR_LOGIN, BYTES, EXIT, GENERAL_CHAT, HOST,
                   INPUT_LOGIN, INPUT_PASSWORD, LOGIN, LOGIN_SET,
                   LOGIN_SUCCESSFUL, PORT, SEND_MESSAGE, SEND_PRIVATE_MESSAGE)

signal(SIGPIPE, SIG_DFL)


class LoopRunner(threading.Thread):
    """Вспомогательный класс для организации тестовой среды. Помогает
    запустить и остановить сервер после тестирования."""

    def __init__(self, loop):
        threading.Thread.__init__(self, name='runner')
        self.loop = loop

    def run(self):
        asyncio.set_event_loop(self.loop)
        try:
            self.loop.run_forever()
        finally:
            if self.loop.is_running():
                self.loop.close()

    def run_coroutine(self, coroutine):
        res = asyncio.run_coroutine_threadsafe(coroutine, self.loop)
        return res.result()

    def _stop(self):
        self.loop.stop()

    def run_in_thread(self, callback, *args):
        return self.loop.call_soon_threadsafe(callback, *args)

    def stop(self):
        time.sleep(0.3)  # костыль для завершения pending tasks
        return self.run_in_thread(self._stop())


class TestServer(TestCase):
    """Тестирование обработки запросов сервером."""

    def setUp(self):
        self.loop = asyncio.new_event_loop()
        self.runner = LoopRunner(self.loop)
        self.runner.start()

    def tearDown(self) -> None:
        self.runner.stop()
        self.runner.join()

    @staticmethod
    def connect_to_server(sock):
        sock.connect((HOST, PORT))
        return sock.recv(BYTES)

    @staticmethod
    def send_recv_message(sock, message):
        sock.send(message)
        return sock.recv(BYTES)

    def test_server_methods(self):
        """Тестирование подключения к серверу и обработки запросов."""

        # запускаем сервер с параметром -
        # каждый пользователь может оставлять только два сообщения в час
        server = Server(event_loop=self.loop, sent_message_per_user=2)
        self.runner.run_coroutine(server.run_server())
        sock1 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock2 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock3 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock4 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        # проверяем первое подключение к серверу
        data = self.connect_to_server(sock1)
        self.assertEqual(len(server.connections), 1)

        # проверяем приглашение на авторизацию и создаем нового пользователя
        self.assertEqual(data.decode(), f'{AUTH_OR_LOGIN}\n')
        data = self.send_recv_message(sock1, AUTH.encode())
        self.assertEqual(data.decode(), INPUT_LOGIN)
        data = self.send_recv_message(sock1, 'new_user'.encode())
        self.assertEqual(data.decode(), INPUT_PASSWORD)
        data = self.send_recv_message(sock1, 'password'.encode())

        # проверяем вход в чат и количество созданных юзеров
        self.assertEqual(data.decode(), f'{LOGIN_SET}\n')
        data = sock1.recv(BYTES)
        self.assertEqual(data.decode(), f'{GENERAL_CHAT}\n')
        self.assertEqual(len(server.users), 1)

        # проверяем второе подключение к серверу
        self.connect_to_server(sock2)
        self.assertEqual(len(server.connections), 2)

        # проверяем приглашение на авторизацию и логинимся под созданным
        # ранее пользователем
        self.send_recv_message(sock2, LOGIN.encode())
        self.send_recv_message(sock2, 'new_user'.encode())
        data = self.send_recv_message(sock2, 'password'.encode())

        # проверяем вход в чат и то, что количество пользователей осталось
        # прежним
        self.assertEqual(data.decode(), f'{LOGIN_SUCCESSFUL}\n')
        data = sock2.recv(BYTES)
        self.assertEqual(data.decode(), f'{GENERAL_CHAT}\n')
        self.assertEqual(len(server.users), 1)

        # проверяем третье подключение к серверу
        data = self.connect_to_server(sock3)
        self.assertEqual(len(server.connections), 3)

        # проверяем приглашение на авторизацию и создаем второго пользователя
        self.assertEqual(data.decode(), f'{AUTH_OR_LOGIN}\n')
        data = self.send_recv_message(sock3, AUTH.encode())
        self.assertEqual(data.decode(), INPUT_LOGIN)
        data = self.send_recv_message(sock3, 'another_user'.encode())
        self.assertEqual(data.decode(), INPUT_PASSWORD)
        data = self.send_recv_message(sock3, 'another_password'.encode())

        # проверяем вход в чат и количество созданных пользователей
        self.assertEqual(data.decode(), f'{LOGIN_SET}\n')
        data = sock3.recv(BYTES)
        self.assertEqual(data.decode(), f'{GENERAL_CHAT}\n')
        self.assertEqual(len(server.users), 2)

        # проверяем четвертое подключение к серверу
        data = self.connect_to_server(sock4)
        self.assertEqual(len(server.connections), 4)

        # проверяем приглашение на авторизацию и создаем третьего пользователя
        self.assertEqual(data.decode(), f'{AUTH_OR_LOGIN}\n')
        data = self.send_recv_message(sock4, AUTH.encode())
        self.assertEqual(data.decode(), INPUT_LOGIN)
        data = self.send_recv_message(sock4, 'user3'.encode())
        self.assertEqual(data.decode(), INPUT_PASSWORD)
        data = self.send_recv_message(sock4, 'password3'.encode())

        # проверяем вход в чат и количество созданных пользователей
        self.assertEqual(data.decode(), f'{LOGIN_SET}\n')
        data = sock4.recv(BYTES)
        self.assertEqual(data.decode(), f'{GENERAL_CHAT}\n')
        self.assertEqual(len(server.users), 3)

        # отправляем сообщение от второго подключения в общий чат и проверяем
        # его получение самим подключением
        message = f'{SEND_MESSAGE} hi!'
        data = self.send_recv_message(sock2, message.encode())
        self.assertIn('says: hi!', data.decode())

        # проверяем получение сообщения первым подключением
        data = sock1.recv(BYTES)
        self.assertIn('says: hi!', data.decode())

        # проверяем получение сообщения третьим подключением
        data = sock3.recv(BYTES)
        self.assertIn('says: hi!', data.decode())

        # убеждаемся что в истории сохранено одно сообщение
        self.assertEqual(len(server.history), 1)

        # отправляем второе сообщение от первого клиента и убеждаемся, что оно
        # получено этим подключением
        message = f'{SEND_MESSAGE} hi again!'
        data = self.send_recv_message(sock1, message.encode())
        self.assertIn('says: hi again!', data.decode())

        # а также получено другим подключением
        data = sock2.recv(BYTES)
        self.assertIn('says: hi again!', data.decode())

        # проверяем что в истории сохранено два сообщения
        self.assertEqual(len(server.history), 2)

        # отправляем третье сообщение, которое сервер должен отвергнуть
        message = f'{SEND_MESSAGE} hi once more!'
        data = self.send_recv_message(sock2, message.encode())
        self.assertEqual(
            data.decode(),
            ('Sorry, but you have reached your limit of 2 per hour. '
             'The message not be sent.\n'))

        # проверяем что в истории по прежнему два сообщения
        self.assertEqual(len(server.history), 2)

        # отключаем клиентов
        sock1.send(EXIT.encode())
        sock2.send(EXIT.encode())
        sock3.send(EXIT.encode())
        sock4.send(EXIT.encode())
        time.sleep(0.5)
        sock1.close()
        sock2.close()
        sock3.close()
        sock4.close()
