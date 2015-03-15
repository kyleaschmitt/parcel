import signal
import os
from ctypes import (
    cdll, CFUNCTYPE, c_void_p, c_int, c_longlong
)

# Load library
INSTALL_PATH = '/usr/local/lib/'
_lib = cdll.LoadLibrary(os.path.join(INSTALL_PATH, 'lparcel.so'))


# Signal handling for external calls
signal.signal(signal.SIGINT, signal.SIG_DFL)


class ParcelDLL(object):

    def __init__(self):
        # int read_size(ThreadedEncryption *decryptor, UDTSOCKET socket, char *buff, int len)
        self.read_size = _lib.read_size
        self.read_size.argtypes = (c_void_p, c_int, c_void_p, c_int)
        self.read_size.restype = c_int

        # int read_size_no_encryption(UDTSOCKET socket, char *buff, int len)
        self.read_size_no_encryption = _lib.read_size_no_encryption
        self.read_size_no_encryption.argtypes = (c_int, c_void_p, c_int)
        self.read_size_no_encryption.restype = c_int

        # int send_data(ThreadedEncryption *encryptor, UDTSOCKET socket, char *buff, int len)
        self.send_data = _lib.send_data
        self.send_data.argtypes = (c_void_p, c_int, c_void_p, c_int)
        self.send_data.restype = c_int

        # int send_data_no_encryption(UDTSOCKET socket, char *buff, int len)
        self.send_data_no_encryption = _lib.send_data_no_encryption
        self.send_data_no_encryption.argtypes = (c_int, c_void_p, c_int)
        self.send_data_no_encryption.restype = c_int

        # Client* new_client()
        self.new_client = _lib.new_client
        self.new_client.restype = c_void_p

        # int client_start(Client *client, char *host, char *port)
        self.client_start = _lib.client_start
        self.client_start.argtypes = (c_void_p, c_void_p, c_void_p)
        self.client_start.restype = c_int

        # UDTSOCKET client_get_socket(Client *client)
        self.client_get_socket = _lib.client_get_socket
        self.client_get_socket.argtypes = (c_void_p,)
        self.client_get_socket.restype = c_int

        # UDTSOCKET sthread_get_socket(Sthread *sthread)
        self.sthread_get_socket = _lib.sthread_get_socket
        self.sthread_get_socket.argtypes = (c_void_p,)
        self.sthread_get_socket.restype = c_int

        # int client_close(Client *client)
        self.client_close = _lib.client_close
        self.client_close.argtypes = (c_void_p,)
        self.client_close.restype = c_int

        # int sthread_close(Sthread *sthread)
        self.sthread_close = _lib.sthread_close
        self.sthread_close.argtypes = (c_void_p,)
        self.sthread_close.restype = c_int

        # ThreadedEncryption *encryption_init(char *key, int n_threads)
        self.encryption_init = _lib.encryption_init
        self.encryption_init.argtypes = (c_void_p, c_int)
        self.encryption_init.restype = c_void_p

        # ThreadedDecryption *decryption_init(char *key, int n_threads)
        self.decryption_init = _lib.decryption_init
        self.decryption_init.argtypes = (c_void_p, c_int)
        self.decryption_init.restype = c_void_p

        # int client_recv_file(Client *client, char *path, int size, int64_t offset = 0)
        self.client_recv_file = _lib.client_recv_file
        self.client_recv_file.argtypes = (c_void_p, c_void_p, c_int, c_longlong)
        self.client_recv_file.restype = c_int



        # self.temp = _lib.temp
        # self.temp.argtypes = (c_void_p, c_int)
        # self.temp.restype = c_void_p


lib = ParcelDLL()
