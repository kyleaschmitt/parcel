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

    def __init__(self, instance, socket, close_func):
        """
        Creates a new udpipeClient instance from shared object library
        """

        log.debug(
            'New ParcelThread object with instance {}, with socket {}'.format(
                instance, socket))
        atexit.register(self.close)
        self.instance = instance
        self.socket = socket
        self.close_func = close_func
        self.buff_len = 64000000
        self.buff = create_string_buffer(self.buff_len)
        self.handshake()

    def read(self):
        while True:
            log.debug('Blocking read ...')
            rs = lib.read_data(self.socket, self.buff, self.buff_len)
            if rs < 0:
                raise StopIteration()
            log.debug('Read {} bytes'.format(rs))
            yield self.buff[:rs]

    def send(self, data):
        lib.send_data(self.socket, data, len(data))

    def close(self):
        self.close_func(self.instance)

    def send_control(self, cntl):
        cntl_buff = create_string_buffer(CONTROL_LEN)
        cntl_buff.raw = chr(cntl)
        self.send(cntl_buff)

    def recv_control(self):
        cntl_buff = create_string_buffer(CONTROL_LEN)
        self.send(cntl_buff)

    def handshake(self):
        log.debug('Sending handshake')
        self.send_control(HANDSHAKE)
        log.debug('Waiting on handshake back')


class ServerThread(ParcelThread):

    def __init__(self, instance):
        super(ServerThread, self).__init__(
            instance=instance,
            socket=lib.sthread_get_socket(instance),
            close_func=lib.sthread_close,
        )

    def clientport(self):
        return lib.sthread_get_clientport(self.instance)

    def clienthost(self):
        return lib.sthread_get_clienthost(self.instance)


class Client(ParcelThread):

    def __init__(self, host='localhost', port=9000):
        client = lib.new_client()
        log.info('Connecting to server at {}:{}'.format(host, port))
        lib.client_start(client, str(host), str(port))
        super(Client, self).__init__(
            instance=client,
            socket=lib.client_get_socket(client),
            close_func=lib.client_close,
        )
