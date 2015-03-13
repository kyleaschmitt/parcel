from ctypes import cdll
import atexit
import os
import signal
from threading import Thread

from log import get_logger
from sthread import ServerThread


# Load library
INSTALL_PATH = '/usr/local/lib/'
lib = cdll.LoadLibrary(os.path.join(INSTALL_PATH, 'lparcel.so'))

# Signal handling for external calls
signal.signal(signal.SIGINT, signal.SIG_DFL)

# Logging
log = get_logger()


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
            log.info('New ServerThread: {}'.format(instance))
            ServerThread(instance, **self.sthread_args)
        except Exception, e:
            log.error('ServerThread exception: {}'.format(str(e)))

    def listen(self):
        while True:
            instance = lib.server_next_client(self.server)
            t = Thread(target=self.server_thread, args=(instance,))
            t.start()
