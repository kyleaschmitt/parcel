import atexit
import signal
import urlparse
from cparcel import lib
import time

from log import get_logger


# Signal handling for external calls
signal.signal(signal.SIGINT, signal.SIG_DFL)

# Logging
log = get_logger('server')


class Server(object):

    def start(self, proxy_host, proxy_port, remote_uri):
        """

        """
        p = urlparse.urlparse(remote_uri)
        assert p.scheme, 'No url scheme specified'
        port = p.port or {'https': '443', 'http': '80'}[p.scheme]
        log.info('Binding proxy server {}:{} -> {}:{}'.format(
            proxy_host, proxy_port, p.hostname, port))
        lib.udt2tcp_start(
            str(proxy_host), str(proxy_port), str(p.hostname), str(port))

        while True:
            # Block because udt2tcp_start is non-blocking
            time.sleep(99999999)
