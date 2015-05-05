import signal
import os
from ctypes import cdll, c_void_p, c_int
from log import get_logger
from utils import STRIP

# Logging
log = get_logger('client')
PACKAGE_DIR = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'src')

# If windows, don't attempt to load library
if os.name == 'nt':
    _lib = None

# else assume a posix system
else:
    # Load library
    try:
        _lib = cdll.LoadLibrary(os.path.join(PACKAGE_DIR, 'lparcel.so'))
        # Signal handling for external calls
        signal.signal(signal.SIGINT, signal.SIG_DFL)
    except:
        log.warn(STRIP("""
        Unable to load parcel udt library. Will proceed with http option only.
        """))
        _lib = None


def no_parcel_lib(*args, **kwargs):
    raise NotImplementedError(STRIP("""
        C++ parcel dynamic library failed to load. Either it was not
        installed to the system path at {} or the udt parcel is
        currently not compatible with your machine.
        """.format(PACKAGE_DIR)))


class ParcelDLL(object):

    def __init__(self):
        if _lib:
            self._set_attributes()
        else:
            self._set_not_implemented()

    def _set_attributes(self):
        # int udt2tcp_start(char *local_host, char *local_port, char *remote_host, char *remote_port);
        self.udt2tcp_start = _lib.udt2tcp_start
        self.udt2tcp_start.argtypes = (c_void_p, c_void_p, c_void_p, c_void_p)
        self.udt2tcp_start.restype = c_int

        # int tcp2udt_start(char *local_host, char *local_port, char *remote_host, char *remote_port);
        self.tcp2udt_start = _lib.tcp2udt_start
        self.tcp2udt_start.argtypes = (c_void_p, c_void_p, c_void_p, c_void_p)
        self.tcp2udt_start.restype = c_int

    def _set_not_implemented(self):
        self.udt2tcp_start = no_parcel_lib
        self.tcp2udt_start = no_parcel_lib

lib = ParcelDLL()
