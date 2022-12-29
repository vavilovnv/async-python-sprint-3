import asyncio
import socket
import threading
import time
from signal import signal, SIGPIPE, SIG_DFL
from unittest import TestCase
from server import Server
from utils import AUTH_OR_LOGIN, INPUT_LOGIN, GENERAL_CHAT, LOGIN_SET, INPUT_PASSWORD, BYTES, HOST, PORT, SEND_MESSAGE,\
    EXIT, LOGIN_SUCCESSFUL, AUTH, LOGIN


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

    def test_server_methods(self):
        """Тестирование подключения к серверу и обработки запросов."""

        # запускаем сервер с параметром -
        # каждый пользователь может оставлять только два сообщения в час
        server = Server(event_loop=self.loop, sent_message_per_user=2)
        self.runner.run_coroutine(server.run_server())
        sock1 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock2 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        # проверяем первое подключение к серверу
        sock1.connect((HOST, PORT))
        data = sock1.recv(BYTES)
        self.assertEqual(len(server.connections), 1)

        # проверяем приглашение на авторизацию и создаем нового пользователя
        self.assertEqual(data.decode(), f'{AUTH_OR_LOGIN}\n')
        sock1.send(AUTH.encode())
        data = sock1.recv(BYTES)
        self.assertEqual(data.decode(), INPUT_LOGIN)
        sock1.send('new_user'.encode())
        data = sock1.recv(BYTES)
        self.assertEqual(data.decode(), INPUT_PASSWORD)
        sock1.send('password'.encode())
        data = sock1.recv(BYTES)

        # проверяем вход в чат и количество созданных юзеров
        self.assertEqual(data.decode(), f'{LOGIN_SET}\n')
        data = sock1.recv(BYTES)
        self.assertEqual(data.decode(), f'{GENERAL_CHAT}\n')
        self.assertEqual(len(server.users), 1)

        # проверяем второе подключение к серверу
        sock2.connect((HOST, PORT))
        sock2.recv(BYTES)
        self.assertEqual(len(server.connections), 2)

        # проверяем приглашение на авторизацию и логинимся под созданным
        # ранее пользователем
        sock2.send(LOGIN.encode())
        sock2.recv(BYTES)
        sock2.send('new_user'.encode())
        sock2.recv(BYTES)
        sock2.send('password'.encode())

        # проверяем вход в чат и то, что количество пользователей осталось
        # прежним
        data = sock2.recv(BYTES)
        self.assertEqual(data.decode(), f'{LOGIN_SUCCESSFUL}\n')
        data = sock2.recv(BYTES)
        self.assertEqual(data.decode(), f'{GENERAL_CHAT}\n')
        self.assertEqual(len(server.users), 1)

        # отправляем сообщение от второго подключения в общий чат
        message = f'{SEND_MESSAGE} hi!'
        sock2.send(message.encode())

        # проверяем его получение первым подключением
        data = sock1.recv(BYTES)
        self.assertIn('says: hi!', data.decode())

        # проверяем его получение вторым подключением
        data = sock2.recv(BYTES)
        self.assertIn('says: hi!', data.decode())

        # убеждаемся что в истории сохранено одно сообщение
        self.assertEqual(len(server.history), 1)

        # отправляем второе сообщение от первого клиента и убеждаемся, что его
        # получили оба клиента
        message = f'{SEND_MESSAGE} hi again!'
        sock1.send(message.encode())
        data = sock1.recv(BYTES)
        self.assertIn('says: hi again!', data.decode())
        data = sock2.recv(BYTES)
        self.assertIn('says: hi again!', data.decode())

        # проверяем что в истории сохранено два сообщения
        self.assertEqual(len(server.history), 2)

        # отправляем третье сообщение, которое сервер должен отвергнуть
        message = f'{SEND_MESSAGE} hi once more!'
        sock2.send(message.encode())
        data = sock2.recv(BYTES)
        self.assertEqual(
            data.decode(),
            ('Sorry, but you have reached your limit of 2 per hour. '
             'The message not be sent.\n'))

        # проверяем что в истории по прежнему два сообщения
        self.assertEqual(len(server.history), 2)
        # time.sleep(5)
        # отключаем клиентов
        sock1.send(EXIT.encode())
        sock2.send(EXIT.encode())
        sock1.close()
        sock2.close()
