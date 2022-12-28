import asyncio
import socket
import threading
import time
from unittest import TestCase
from server import Server
from utils import BYTES, HOST, PORT, SEND_MESSAGE


class LoopRunner(threading.Thread):
    """Вспомогательный класс для организации тестовой среды."""
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
        time.sleep(0.1)
        self.loop.stop()

    def run_in_thread(self, callback, *args):
        return self.loop.call_soon_threadsafe(callback, *args)

    def stop(self):
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
        server = Server(self.loop)
        self.runner.run_coroutine(server.run_server())

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((HOST, PORT))

        data = sock.recv(BYTES)
        self.assertEqual(data.decode(), 'Please, register (/auth) or log in (/login).\n')

        sock.send('/auth'.encode())
        data = sock.recv(BYTES)
        self.assertEqual(data.decode(), 'Input your login: ')

        sock.send('user'.encode())
        data = sock.recv(BYTES)
        self.assertEqual(data.decode(), 'Input your password: ')

        sock.send('password'.encode())
        data = sock.recv(BYTES)
        self.assertEqual(data.decode(), 'Login and password was set.\n')
        sock.close()

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((HOST, PORT))

        sock.recv(BYTES)
        sock.send('/login'.encode())

        sock.recv(BYTES)
        sock.send('user'.encode())

        sock.recv(BYTES)
        sock.send('password'.encode())

        data = sock.recv(BYTES)
        self.assertEqual(data.decode(), 'Login successful.\n')

        message = f'{SEND_MESSAGE} hi!'
        sock.send(message.encode())

        self.assertEqual(len(server.history), 1)
        self.assertEqual(len(server.users), 1)

        sock.close()
