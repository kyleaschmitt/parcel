from ctypes import cdll, create_string_buffer
import json
import logging
import atexit
import sys
import os
import signal
import urlparse
from functools import wraps
from threading import Thread
import requests

from const import (
    # Lengths
    LEN_CONTROL, LEN_PAYLOAD_SIZE, RES_CHUNK_SIZE,
    # Control messages
    CNTL_EXIT, CNTL_DOWNLOAD, CNTL_HANDSHAKE,
    # States
    STATE_IDLE,
)

# Load library
INSTALL_PATH = '/usr/local/lib/'
lib = cdll.LoadLibrary(os.path.join(INSTALL_PATH, 'lparcel.so'))

# Signal handling for external calls
signal.signal(signal.SIGINT, signal.SIG_DFL)

# Logging
log = logging.getLogger('parcel')
log.setLevel(logging.DEBUG)
log.propagate = False
formatter = logging.Formatter(
    '[%(asctime)s][%(name)10s][%(levelname)7s] %(message)s')
handler = logging.StreamHandler(sys.stderr)
handler.setFormatter(formatter)
log.addHandler(handler)


def vec(val):
    return val if hasattr(val, '__iter__') else [val]


def state_method(*states):
    """Enter a new state

    :param states:
        A list of str or single str specifying the states that are
        valid preceeding this one

    """

    def wrapper(func, *args, **kwargs):
        @wraps(func)
        def f(self, *args, **kwargs):
            assert self.state in vec(states), \
                'Moving from state <{}> to <{}> is invalid'.format(
                    self.state, func.__name__)
            self.state = func.__name__
            log.debug('{}: Entering state: {}'.format(self, self.state))
            func(self, *args, **kwargs)
            log.debug('{}: Exiting state: {}'.format(self, self.state))
        return f
    return wrapper


class Server(object):

    def __init__(self):
        """
        Creates a new udpipeClient instance from shared object library
        """

        self.server = lib.new_server()
        atexit.register(self.close)

    def start(self, host='localhost', port=9000, sthread_args={}):
        """

        """

        log.info('Starting server at {}:{}'.format(host, port))
        lib.server_start(self.server, str(host), str(port))
        log.info('Server ready at {}:{}'.format(host, port))
        self.sthread_args = sthread_args

        # Check server thread args
        assert 'data_server_url' in sthread_args

        self.listen()

    def close(self):
        lib.server_close(self.server)

    def server_thread(self, instance):
        try:
            logging.info('New ServerThread: {}'.format(instance))
            ServerThread(instance, **self.sthread_args)
        except Exception, e:
            log.error('ServerThread exception: {}'.format(str(e)))

    def listen(self):
        while True:
            instance = lib.server_next_client(self.server)
            t = Thread(target=self.server_thread, args=(instance,))
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
        return '<{}({}, {})>'.format(
            type(self).__name__, self.instance, self.socket)

    def read_size(self, size):
        buff = create_string_buffer(size)
        rs = lib.read_size(self.socket, buff, size)
        if (rs == -1):
            raise Exception('Unable to read from socket.')
        return buff.value

    def send_payload_size(self, size):
        buff = create_string_buffer(LEN_PAYLOAD_SIZE)
        buff.value = str(size)
        self.send(buff, LEN_PAYLOAD_SIZE)

    def read_payload_size(self):
        payload_size = int(self.read_size(LEN_PAYLOAD_SIZE))
        return payload_size

    def next_payload(self):
        payload_size = self.read_payload_size()
        return self.read_size(payload_size)

    def send_payload(self, payload, size=None):
        if size is None:
            size = len(payload)
        self.send_payload_size(size)
        self.send(payload, size)

    def read(self):
        while True:
            log.debug('Blocking read ...')
            rs = lib.read_data(self.socket, self.buff, self.buff_len)
            if rs < 0:
                raise StopIteration()
            log.debug('Read {} bytes'.format(rs))
            yield self.buff[:rs]

    def send(self, data, size=None):
        if size is None:
            size = len(data)
        lib.send_data(self.socket, data, size)

    def close(self):
        del self.buff
        self.send_control(CNTL_EXIT)
        self.close_func(self.instance)

    def send_control(self, cntl):
        cntl_buff = create_string_buffer(LEN_CONTROL)
        cntl_buff.raw = cntl
        self.send(cntl_buff)

    def recv_control(self, expected=None):
        cntl = self.read_size(LEN_CONTROL)
        log.debug('CONTROL: {}'.format(ord(cntl)))
        if expected is not None and cntl not in vec(expected):
            raise RuntimeError('Unexpected control msg: {} != {}'.format(
                ord(cntl), ord(expected)))
        return cntl

    @state_method(STATE_IDLE)
    def handshake(self, *args, **kwargs):
        raise NotImplementedError()

    @state_method('handshake')
    def authenticate(self, *args, **kwargs):
        raise NotImplementedError()


class ServerThread(ParcelThread):

    def __init__(self, instance, data_server_url):
        super(ServerThread, self).__init__(
            instance=instance,
            socket=lib.sthread_get_socket(instance),
            close_func=lib.sthread_close,
        )

        self.data_server_url = data_server_url
        self.authenticate()
        self.token = None
        self.live = True
        while self.live:
            self.event_loop()

    @state_method(STATE_IDLE)
    def handshake(self):
        self.send_control(CNTL_HANDSHAKE)
        self.recv_control(CNTL_HANDSHAKE)
        client_option_str = self.next_payload()
        try:
            client_options = json.loads(client_option_str)
        except:
            log.error('Unable to process client options: {}'.format(
                client_options))
        log.debug('Client options: {}'.format(client_options))

    def clientport(self):
        return lib.sthread_get_clientport(self.instance)

    def clienthost(self):
        return lib.sthread_get_clienthost(self.instance)

    @state_method('handshake')
    def recv_cmd(self):
        self.send_control(CNTL_HANDSHAKE)
        r = self.recv_control()
        assert r == CNTL_HANDSHAKE

    @state_method('handshake')
    def authenticate(self):
        self.token = self.next_payload()
        log.info('Connected with token: "{}"'.format(self.token))

    @state_method('authenticate', 'event_loop')
    def shut_down(self):
        log.info('Thread exiting cleanly.')
        self.live = False

    @state_method('event_loop')
    def download(self):
        file_id = self.next_payload()
        url = urlparse.urljoin(self.data_server_url, file_id)
        log.info('Download request: {}'.format(url))

        headers = {
            'X-Auth-Token': self.token,
        }

        r = requests.get(
            url,
            headers=headers,
            verify=False,
            stream=True,
        )

        if r.status_code != 200:
            # Failed to get file, notify the client
            log.warn('Request failed: {} {}'.format(url, r.text))
            return self.send_payload(json.dumps({
                'error': r.text,
                'status_code': r.status_code,
            }))

        # Client assumes a metadata response first.
        try:
            size = long(r.headers['Content-Length'])
            log.info('Request responded: {} bytes'.format(size))
        except KeyError:
            msg = 'Request without length: {}'.format(url)
            log.error(msg)
            return self.send_payload(json.dumps({
                'error': msg,
                'status_code': r.status_code,
            }))

        # Send file size to client
        self.send_payload(json.dumps({
            'error': None,
            'file_size': size,
            'status_code': r.status_code,
        }))

        # Then streaming of the data itself.
        for chunk in r.iter_content(chunk_size=RES_CHUNK_SIZE):
            if not chunk:
                continue  # Empty are keep-alives.
            self.send(chunk, len(chunk))

    @state_method('authenticate', 'event_loop', 'download')
    def event_loop(self):
        switch = {
            CNTL_EXIT: self.shut_down,
            CNTL_DOWNLOAD: self.download,
        }
        cntl = self.recv_control()
        if cntl not in switch:
            raise RuntimeError('Unknown control code {}'.format(cntl))
        switch[cntl]()


class Client(ParcelThread):

    def __init__(self, token, host='localhost', port=9000):
        client = lib.new_client()
        log.info('Connecting to server at {}:{}'.format(host, port))
        lib.client_start(client, str(host), str(port))
        super(Client, self).__init__(
            instance=client,
            socket=lib.client_get_socket(client),
            close_func=lib.client_close,
        )
        self.authenticate(token)

    @state_method(STATE_IDLE)
    def handshake(self):
        self.send_control(CNTL_HANDSHAKE)
        self.recv_control(CNTL_HANDSHAKE)
        self.send_payload(json.dumps({
            'num_crypto_threads': 1,
            'version': 0.1,
        }))

    @state_method('handshake')
    def authenticate(self, token):
        self.send_payload(token)

    @state_method('authenticate', 'download')
    def download(self, uuid):
        self.send_control(CNTL_DOWNLOAD)
        self.send_payload(uuid)
        file_info = json.loads(self.next_payload())

        if file_info['error'] is None:
            size = int(file_info['file_size'])
            log.info('Downloading file: {}'.format(uuid))
            log.info('Download size: {}'.format(size))
            lib.client_recv_file(self.instance, uuid, size, 0)
            log.info('Downloadloaded to file: {}'.format(uuid))
        else:
            log.error('Unable to download file {}: {}'.format(
                uuid, file_info))
