from ctypes import cdll, c_void_p, c_int
from log import get_logger
from utils import STRIP
import tempfile
import pkgutil

# Logging
log = get_logger('client')


# Load library
try:
    dll_data = pkgutil.get_data('parcel', 'src/lparcel.so')
    dll_file = tempfile.NamedTemporaryFile()
    dll_file.write(dll_data)
    _lib = cdll.LoadLibrary(dll_file.name)
except:
    log.debug(STRIP("""
    Unable to load parcel udt library. Will proceed with http option only."""))
    _lib = None


def no_parcel_lib(*args, **kwargs):
    raise NotImplementedError(STRIP("""
        C++ parcel dynamic library failed to load. Either it was not
        installed to the package directory, or the parcel udt command is
        currently not compatible with your machine.
        """))


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
