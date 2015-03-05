from ctypes import cdll, create_string_buffer
lib = cdll.LoadLibrary('lparcel.so')
import logging
import atexit
import sys

from const import (
    CONTROL_LEN, HANDSHAKE
)

import signal
signal.signal(signal.SIGINT, signal.SIG_DFL)

log = logging.getLogger('parcel')
log.setLevel(logging.DEBUG)
formatter = logging.Formatter(
    '[%(asctime)s][%(name)10s][%(levelname)7s] %(message)s')
handler = logging.StreamHandler(sys.stderr)
handler.setFormatter(formatter)
log.addHandler(handler)


class Server(object):

    def __init__(self):
        """
        Creates a new udpipeClient instance from shared object library
        """

        self.server = lib.new_server()
        atexit.register(self.close)

    def start(self, host='localhost', port=9000):
        log.info('Starting server at {}:{}'.format(host, port))
        lib.server_start(self.server, str(host), str(port))
        log.info('Server ready at {}:{}'.format(host, port))

    def close(self):
        lib.server_close(self.server)

    def listen(self):
        while True:
            yield ServerThread(lib.server_next_client(self.server))


class ParcelThread(object):

    def __init__(self, instance, read_func, send_func, close_func):
        """
        Creates a new udpipeClient instance from shared object library
        """

        atexit.register(self.close)
        self.instance = instance
        self.read_func = read_func
        self.send_func = send_func
        self.close_func = close_func
        self.buff_len = 64000000
        self.buff = create_string_buffer(self.buff_len)

    def read(self):
        while True:
            log.debug('Blocking read ...')
            rs = self.read_func(self.instance, self.buff, self.buff_len)
            if rs < 0:
                raise StopIteration()
            log.debug('Read {} bytes'.format(rs))
            yield self.buff[:rs]

    def send(self, data):
        self.send_func(self.instance, data, len(data))

    def close(self):
        self.close_func(self.instance)

    def send_control(self, cntl):
        cntl_buff = create_string_buffer(CONTROL_LEN)
        cntl_buff.raw = chr(cntl)
        self.send(cntl_buff)


class ServerThread(ParcelThread):

    def __init__(self, instance):
        super(ServerThread, self).__init__(
            instance=instance,
            read_func=lib.sthread_read,
            send_func=lib.sthread_send,
            close_func=lib.sthread_close,
        )

    def clientport(self):
        return lib.sthread_get_clientport(self.instance)

    def clienthost(self):
        return lib.sthread_get_clienthost(self.instance)


class Client(ParcelThread):

    def __init__(self):
        super(Client, self).__init__(
            instance=lib.new_client(),
            read_func=lib.client_read,
            send_func=lib.client_send,
            close_func=lib.client_close,
        )

    def start(self, host='localhost', port=9000):
        log.info('Connecting to server at {}:{}'.format(host, port))
        lib.client_start(self.instance, str(host), str(port))
        log.debug('Sending handshake')
        self.send_control(HANDSHAKE)
        log.debug('Waiting on handshake back')
