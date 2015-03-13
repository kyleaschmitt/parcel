import json

from parcel_thread import ParcelThread
from utils import state_method
from lib import lib
from log import get_logger
from proxy import proxy_file_to_client
from const import (
    # Lengths
    LEN_CONTROL, LEN_PAYLOAD_SIZE, RES_CHUNK_SIZE,
    # Control messages
    CNTL_EXIT, CNTL_DOWNLOAD, CNTL_HANDSHAKE,
    # States
    STATE_IDLE,
)

# Logging
log = get_logger()


class ServerThread(ParcelThread):

    def __init__(self, instance, data_server_url):
        super(ServerThread, self).__init__(
            instance=instance,
            socket=lib.sthread_get_socket(instance),
            close_func=lib.sthread_close,
        )

        self.data_server_url = data_server_url
        self.authenticate()
        self.token = None
        self.live = True
        while self.live:
            self.event_loop()

    @state_method(STATE_IDLE)
    def handshake(self):
        """Handshake steps

        1. Send handshake
        2. Wait for handshake
        3. receive client options and parse

        """

        self.send_control(CNTL_HANDSHAKE)
        self.recv_control(CNTL_HANDSHAKE)
        client_option_str = self.next_payload()
        try:
            client_options = json.loads(client_option_str)
        except:
            log.error('Unable to process client options: {}'.format(
                client_options))
        log.debug('Client options: {}'.format(client_options))

    def clientport(self):
        return lib.sthread_get_clientport(self.instance)

    def clienthost(self):
        return lib.sthread_get_clienthost(self.instance)

    @state_method('handshake')
    def authenticate(self):
        """Authentication stub

        """

        self.token = self.next_payload()
        log.info('Connected with token: "{}"'.format(self.token))

    @state_method('authenticate', 'event_loop')
    def shut_down(self):
        """Exit the event loop

        """

        log.info('Thread exiting cleanly.')
        self.live = False

    @state_method('event_loop')
    def download(self):
        """Proxy a file to the client
        """
        file_id = self.next_payload()
        try:
            proxy_file_to_client(self, file_id)
        except Exception, e:
            log.error('Unable to proxy file to client: {}'.format(str(e)))

    @state_method('authenticate', 'event_loop', 'download')
    def event_loop(self):
        """Loop over client requests

        """

        switch = {
            CNTL_EXIT: self.shut_down,
            CNTL_DOWNLOAD: self.download,
        }
        cntl = self.recv_control()
        if cntl not in switch:
            raise RuntimeError('Unknown control code {}'.format(cntl))
        switch[cntl]()
