from ctypes import cdll, create_string_buffer
lib = cdll.LoadLibrary('lparcel.so')
import logging
import atexit
import sys
from functools import wraps
import threading

from const import (
    CONTROL_LEN, HANDSHAKE, STATE_IDLE
)

import signal
signal.signal(signal.SIGINT, signal.SIG_DFL)

log = logging.getLogger('parcel')
log.setLevel(logging.DEBUG)
log.propagate = False
formatter = logging.Formatter(
    '[%(asctime)s][%(name)10s][%(levelname)7s] %(message)s')
handler = logging.StreamHandler(sys.stderr)
handler.setFormatter(formatter)
log.addHandler(handler)


def state_method(valid_prev_states):
    def wrapper(func, *args, **kwargs):
        @wraps(func)
        def f(self, *args, **kwargs):
            assert self.state in valid_prev_states, \
                '{} not a valid previous state'.format(self.state)
            self.state = func.__name__
            log.debug('Entering state: {}'.format(self.state))
            func(self, *args, **kwargs)
            log.debug('exiting state: {}'.format(self.state))
        return f
    return wrapper


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
        self.listen()

    def close(self):
        lib.server_close(self.server)

    def server_thread(self, thread):
        logging.info('New client: {}'.format(thread))

    def listen(self):
        threads = []
        while True:
            sthread = ServerThread(lib.server_next_client(self.server))
            t = threading.Thread(target=self.server_thread, args=(sthread,))
            t.daemon = True
            threads.append(t)
            t.start()


class ParcelThread(object):

    def __init__(self, instance, socket, close_func):
        """
        Creates a new udpipeClient instance from shared object library
        """

        atexit.register(self.close)
        self.instance = instance
        self.socket = socket
        self.close_func = close_func
        self.buff_len = 64000000
        self.buff = create_string_buffer(self.buff_len)
        self.state = STATE_IDLE
        log.info('New instance {}'.format(self))
        self.handshake()

    def __repr__(self):
        return '<{}, instance: {}, socket: {}>'.format(
            type(self).__name__, self.instance, self.socket)

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
        cntl_buff.raw = cntl
        self.send(cntl_buff)

    def recv_control(self):
        cntl_buff = create_string_buffer(CONTROL_LEN)
        lib.read_size(self.socket, cntl_buff, CONTROL_LEN)
        logging.debug('CONTROL: {}'.format(cntl_buff.value))
        return cntl_buff.value

    @state_method(STATE_IDLE)
    def handshake(self):
        self.send_control(HANDSHAKE)
        r = self.recv_control()
        assert r == HANDSHAKE


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

    @state_method('handshake')
    def recv_cmd(self):
        self.send_control(HANDSHAKE)
        r = self.recv_control()
        assert r == HANDSHAKE


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
