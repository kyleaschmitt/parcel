from ctypes import cdll, create_string_buffer
import atexit
import os
import signal
from utils import state_method, vec

from log import get_logger

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
log = get_logger('parcel')


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
        log.debug('New instance {}'.format(self))
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
