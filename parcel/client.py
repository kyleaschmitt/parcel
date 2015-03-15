import json
import os

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
log = get_logger('client')


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
        self.initialize_encryption()
        self.handshake()
        self.authenticate(token)

    @state_method('initialize_encryption')
    def handshake(self):
        """Handshake steps

        1. Send handshake
        2. Wait for handshake
        3. send our options

        """

        self.send_control(CNTL_HANDSHAKE, encryption=False)
        self.recv_control(CNTL_HANDSHAKE, encryption=False)
        self.send_payload(json.dumps({
            'num_crypto_threads': 1,
            'version': 0.1,
        }))

    @state_method('handshake')
    def authenticate(self, token):
        self.send_payload(token)

    @state_method('authenticate', 'download_files', 'download')
    def download_files(self, file_ids, *args, **kwargs):
        """Download a list of files

        """

        if not file_ids:
            log.warn('No file ids given.')
            return

        for file_id in file_ids:
            log.info('Found file id: {}'.format(file_id))

        for file_id in file_ids:
            self.download(file_id, *args, **kwargs)

    @state_method('authenticate', 'download_files', 'download')
    def download(self, file_id, directory=None):
        """Download steps:

        1. notify server of download state
        2. send file_id to download
        3. receive file info from server
        4. attempt to read into file

        """
        self.send_control(CNTL_DOWNLOAD)
        self.send_payload(json.dumps({
            'file_id': file_id}))
        file_info = json.loads(self.next_payload())

        if not directory:
            directory = os.path.abspath(os.getcwd())

        log.info('-'*40)
        log.info('Starting download   : {}'.format(file_id))
        log.info('-'*40)

        if file_info['error'] is None:
            file_size = int(file_info['file_size'])
            file_name = file_info.get('file_name', None)

            # Create file path
            file_path = os.path.join(directory, file_id)
            log.info('File name           : {}'.format(file_name))
            log.info('Download size       : {}'.format(file_size))
            log.info('Downloading file to : {}'.format(file_path))

            # Download files
            lib.client_recv_file(self.instance, file_path, file_size, 0)
            log.info('Completed.')
        else:
            log.error('Unable to download file {}: {}'.format(
                file_id, file_info['error']))
