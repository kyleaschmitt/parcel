import atexit
import urlparse
from threading import Thread

from parcel import auth
from parcel_thread import ParcelThread
from utils import state_method
from lib import lib
from log import get_logger
from const import (
    CNTL_EXIT, CNTL_DOWNLOAD, CNTL_HANDSHAKE, CNTL_FILE_INFO,
    STATE_IDLE, RES_CHUNK_SIZE
)
from version import version, compatible_versions

# Logging
log = get_logger('sthread')


class ServerThread(ParcelThread):

    def __init__(self, instance, uri, private_key):
        super(ServerThread, self).__init__(
            instance=instance,
            socket=lib.sthread_get_socket(instance),
            close_func=lib.sthread_close,
        )

        # Set attributes
        self.uri = uri
        self.private_key = private_key
        self.live = True
        self.send_thread = None

        # Encryption attributes
        self.private_key = private_key
        self.key = None
        self.iv = None

        # Initialize thread
        self.initialize_encryption()
        self.handshake()

        # Register teardown message callback
        # atexit.register(self.close)

        # Start thread processing
        while self.live:
            self.event_loop()

    @state_method(STATE_IDLE)
    def initialize_encryption(self):
        if not self.private_key:
            raise RuntimeError('No private key for encryption.')
        log.info('Performing pubkey handshake.')
        self.key, self.iv = auth.server_auth(
            self.send_payload,
            self.next_payload,
            self.private_key,
            encryption=False,
        )
        self.encryptor = lib.encryption_init(self.key, self.iv)
        self.decryptor = lib.decryption_init(self.key, self.iv)

    @state_method('initialize_encryption', STATE_IDLE)
    def handshake(self):
        """Handshake steps

        1. Send handshake
        2. Wait for handshake
        3. receive client options and parse

        """

        self.send_control(CNTL_HANDSHAKE, encryption=False)
        self.recv_control(CNTL_HANDSHAKE, encryption=False)
        self.send_json(self.get_server_options())
        server_options = self.read_json()
        server_version = server_options['version']
        if server_version not in compatible_versions:
            raise RuntimeError(
                'Server version {} not compatible'.format(server_version))

    @state_method('handshake')
    def receive_token(self):
        self.token = self.next_payload()
        if self.token:
            log.info('Connected with token {} bytes'.format(len(self.token)))

    @state_method('event_loop')
    def shut_down(self):
        """Exit the event loop

        """

        log.info('Thread exiting cleanly.')
        self.live = False

    @state_method('handshake', 'event_loop', 'download')
    def event_loop(self):
        """Loop over client requests

        """

        switch = {
            CNTL_EXIT: self.shut_down,
            CNTL_DOWNLOAD: self.download,
            CNTL_FILE_INFO: self.send_file_info,
        }
        cntl = self.recv_control()
        if cntl not in switch:
            raise RuntimeError('Unknown control code {}'.format(cntl))
            switch[cntl]()

    def get_server_options(self):
        return {
            'version': version
        }

    def download(self):
        pass

    def send_file_info(self):
        print 'here'
        file_request = self.read_json()
        try:
            file_id = file_request['file_id']
        except Exception as e:
            self.send_json({'error': 'Malformed request: {}'.format(str(e))})
            raise RuntimeError('Malformed file info request: {} {}'.format(
                str(e), file_request))
        try:
            name, size = self.request_file_information(file_id)
        except:
            self.send_json({'error': 'Malformed request'})
            raise RuntimeError('Malformed file info request: {}'.format(
                file_request))

        self.send_json({
            'file_name': name,
            'file_size': size
        })
