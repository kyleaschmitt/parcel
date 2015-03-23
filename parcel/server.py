import atexit
import signal

from log import get_logger


# Signal handling for external calls
signal.signal(signal.SIGINT, signal.SIG_DFL)

# Logging
log = get_logger('server')


class Server(object):

    def __init__(self):
        """
        Creates a new udpipeClient instance from shared object library
        """

        atexit.register(self.close)

    def start(self, host, port, uri):
        """

        """
        self.uri = uri

        log.info('Starting server at {}:{}'.format(host, port))

        log.info('|-- {}: {}'.format('uri', uri))

        raise NotImplementedError()

    def close(self):
        raise NotImplementedError()

    def listen(self):
        raise NotImplementedError()
