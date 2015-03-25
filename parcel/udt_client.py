from log import get_logger
from client import Client
import urlparse
from cparcel import lib
# from multiprocessing import Process
from threading import Thread
import time

# Logging
log = get_logger('client')


class UDTClient(Client):

    def __init__(self, proxy_host, proxy_port, remote_uri, *args, **kwargs):
        self.start_proxy_server(proxy_host, proxy_port, remote_uri)
        local_uri = self.construct_local_uri(
            proxy_host, proxy_port, remote_uri)
        super(UDTClient, self).__init__(local_uri, *args, **kwargs)

    def construct_local_uri(self, proxy_host, proxy_port, remote_uri):
        """Given proxy settings and remote_uri, construct the uri where the
        proxy request will be sent

        """
        p = urlparse.urlparse(remote_uri)
        assert p.scheme, 'No url scheme specified'
        local_uri = '{}://{}:{}/data'.format(p.scheme, proxy_host, proxy_port)
        return local_uri

    def start_proxy_server(self, proxy_host, proxy_port, remote_uri):
        """Bind proxy.

        """

        p = urlparse.urlparse(remote_uri)
        assert p.scheme, 'No url scheme specified'
        port = p.port or {'https': '443', 'http': '80'}[p.scheme]
        log.info('Binding proxy server {}:{} -> {}:{}'.format(
            str(proxy_host), str(proxy_port), str(p.hostname), str(port)))
        lib.tcp2udt_start(
            str(proxy_host), str(proxy_port), str(p.hostname), str(port))
