import json

from parcel_thread import ParcelThread
from utils import state_method
from lib import lib
from log import get_logger
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


class Client(ParcelThread):

    def __init__(self, token, host='localhost', port=9000):
        client = lib.new_client()
        log.info('Connecting to server at {}:{}'.format(host, port))
        lib.client_start(client, str(host), str(port))
        super(Client, self).__init__(
            instance=client,
            socket=lib.client_get_socket(client),
            close_func=lib.client_close,
        )
        self.authenticate(token)

    @state_method(STATE_IDLE)
    def handshake(self):
        """Handshake steps

        1. Send handshake
        2. Wait for handshake
        3. send our options

        """

        self.send_control(CNTL_HANDSHAKE)
        self.recv_control(CNTL_HANDSHAKE)
        self.send_payload(json.dumps({
            'num_crypto_threads': 1,
            'version': 0.1,
        }))

    @state_method('handshake')
    def authenticate(self, token):
        self.send_payload(token)

    @state_method('authenticate', 'download')
    def download(self, uuid):
        """Download steps:

        1. notify server of download state
        2. send uuid to download
        3. receive file info from server
        4. attempt to read into file

        """
        self.send_control(CNTL_DOWNLOAD)
        self.send_payload(uuid)
        file_info = json.loads(self.next_payload())

        if file_info['error'] is None:
            size = int(file_info['file_size'])
            log.info('Downloading file: {}'.format(uuid))
            log.info('Download size: {}'.format(size))
            lib.client_recv_file(self.instance, uuid, size, 0)
            log.info('Downloadloaded to file: {}'.format(uuid))
        else:
            log.error('Unable to download file {}: {}'.format(
                uuid, file_info))
