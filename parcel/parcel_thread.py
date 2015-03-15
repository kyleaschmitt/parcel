from ctypes import create_string_buffer
import atexit
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

from lib import lib

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
        buff = create_string_buffer(size)
        if encryption:
            self.assert_encryption()
            rs = lib.read_size(self.decryptor, self.socket, buff, size)
        else:
            rs = lib.read_size_no_encryption(self.socket, buff, size)
        if (rs == -1):
            raise Exception('Unable to read from socket.')
        return buff.value

    def send(self, data, size=None, encryption=True, encrypt_inplace=False):
        if size is None:
            size = len(data)
        if encryption:
            self.assert_encryption()
            in_place = 1 if encrypt_inplace else 0
            lib.send_data(self.encryptor, self.socket, data, size, in_place)
        else:
            lib.send_data_no_encryption(self.socket, data, size)

    ############################################################
    #                     Transfer Functions
    ############################################################

    def send_payload_size(self, size, **send_args):
        buff = create_string_buffer(LEN_PAYLOAD_SIZE)
        buff.value = str(size)
        self.send(buff, LEN_PAYLOAD_SIZE, **send_args)

    def read_payload_size(self, **read_args):
        payload_size = int(self.read_size(LEN_PAYLOAD_SIZE, **read_args))
        return payload_size

    def next_payload(self, **read_args):
        payload_size = self.read_payload_size()
        return self.read_size(payload_size, **read_args)

    def send_payload(self, payload, size=None, **send_args):
        if size is None:
            size = len(payload)
        self.send_payload_size(size, **send_args)
        self.send(payload, size, **send_args)

    def send_control(self, cntl, **send_args):
        cntl_buff = create_string_buffer(LEN_CONTROL)
        cntl_buff.raw = cntl
        self.send(cntl_buff, LEN_CONTROL, **send_args)

    def recv_control(self, expected=None, **read_args):
        cntl = self.read_size(LEN_CONTROL, **read_args)
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
        key = str(range(256)).encode('hex')[:256]
        self.encryptor = lib.encryption_init(key, 1)
        self.decryptor = lib.decryption_init(key, 1)
