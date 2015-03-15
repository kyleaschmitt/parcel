from ctypes import cdll, create_string_buffer
import atexit
import os
import signal
from utils import state_method, vec

from log import get_logger

from const import (
    # Lengths
    LEN_CONTROL, LEN_PAYLOAD_SIZE,
    # Control messages
    CNTL_EXIT,
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

        self.state = STATE_IDLE
        self.encryptor = None
        self.decryptor = None
        atexit.register(self.close)
        self.instance = instance
        self.socket = socket
        self.close_func = close_func
        log.debug('New instance {}'.format(self))
        self.initialize_encryption()
        self.handshake()

    def __repr__(self):
        return '<{}({}, {})>'.format(
            type(self).__name__, self.instance, self.socket)

    def assert_encryption(self):
        assert self.encryptor, 'Encryptor not initialized'
        assert self.decryptor, 'Decryptor not initialized'

    ############################################################
    #                     Library Wrappers
    ############################################################

    def read_size(self, size, encryption=True):
        encryption = False
        buff = create_string_buffer(size)
        if encryption:
            self.assert_encryption()
            rs = lib.read_size(self.decryptor, self.socket, buff, size)
        else:
            rs = lib.read_size_no_encryption(self.socket, buff, size)
        if (rs == -1):
            raise Exception('Unable to read from socket.')
        return buff.value

    def send(self, data, size=None, encryption=True):
        encryption = False
        if size is None:
            size = len(data)
        if encryption:
            self.assert_encryption()
            lib.send_data(self.encryptor, self.socket, data, size)
        else:
            lib.send_data_no_encryption(self.socket, data, size)

    ############################################################
    #                     Transfer Functions
    ############################################################

    def send_payload_size(self, size, encryption=True):
        buff = create_string_buffer(LEN_PAYLOAD_SIZE)
        buff.value = str(size)
        self.send(buff, LEN_PAYLOAD_SIZE, encryption)

    def read_payload_size(self, encryption=True):
        payload_size = int(self.read_size(LEN_PAYLOAD_SIZE))
        return payload_size

    def next_payload(self, encryption=True):
        payload_size = self.read_payload_size()
        return self.read_size(payload_size, encryption)

    def send_payload(self, payload, size=None, encryption=True):
        if size is None:
            size = len(payload)
        self.send_payload_size(size, encryption)
        self.send(payload, size, encryption)

    def send_control(self, cntl, encryption=True):
        cntl_buff = create_string_buffer(LEN_CONTROL, encryption)
        cntl_buff.raw = cntl
        self.send(cntl_buff, LEN_CONTROL, encryption)

    def recv_control(self, expected=None, encryption=True):
        cntl = self.read_size(LEN_CONTROL, encryption)
        log.debug('CONTROL: {}'.format(ord(cntl)))
        if expected is not None and cntl not in vec(expected):
            raise RuntimeError('Unexpected control msg: {} != {}'.format(
                ord(cntl), ord(expected)))
        return cntl

    ############################################################
    #                     State Functions
    ############################################################

    def close(self):
        self.send_control(CNTL_EXIT)
        self.close_func(self.instance)

    @state_method(STATE_IDLE)
    def handshake(self, *args, **kwargs):
        raise NotImplementedError()

    @state_method('handshake')
    def authenticate(self, *args, **kwargs):
        raise NotImplementedError()

    @state_method(STATE_IDLE)
    def initialize_encryption(self):
        # key = str(range(256)).encode('hex')[:256]
        # self.encryptor = lib.encryption_init(key, 4)
        # self.decryptor = lib.encryption_init(key, 4)
        pass
