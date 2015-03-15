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
log = get_logger('sthread')


class ServerThread(ParcelThread):

    def __init__(self, instance, data_server_url, max_enc_threads,
                 buffer_processes):
        super(ServerThread, self).__init__(
            instance=instance,
            socket=lib.sthread_get_socket(instance),
            close_func=lib.sthread_close,
        )

        # Initialize thread
        self.initialize_encryption('', max_enc_threads)
        self.handshake()
        self.authenticate()

        # Set attributes
        self.buffer_processes = buffer_processes
        self.data_server_url = data_server_url
        self.live = True
        self.send_thread = None

        # Start thread processing
        while self.live:
            self.event_loop()

    @state_method('initialize_encryption')
    def handshake(self):
        """Handshake steps

        1. Send handshake
        2. Wait for handshake
        3. receive client options and parse

        """

        self.send_control(CNTL_HANDSHAKE, encryption=False)
        self.recv_control(CNTL_HANDSHAKE, encryption=False)
        try:
            client_options = self.read_json()
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
        if self.token:
            log.info('Connected with token.')

    @state_method('authenticate', 'event_loop')
    def shut_down(self):
        """Exit the event loop

        """

        log.info('Thread exiting cleanly.')
        self.live = False

    def proxy_file_to_client(self, *args, **kwargs):
        return proxy_file_to_client(self, *args, **kwargs)

    @state_method('event_loop')
    def download(self):
        """Proxy a file to the client
        """
        try:
            file_request = self.read_json()
            file_id = file_request['file_id']
        except Exception, e:
            self.send_json({
                'error': 'Malformed file_request: {}'.format(str(e))})
            raise

        try:
            self.proxy_file_to_client(file_id, self.buffer_processes)
        except Exception, e:
            log.error('Unable to proxy file to client: {}'.format(str(e)))
            raise

    @state_method('authenticate', 'event_loop', 'download',
                  'initialize_encryption')
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

    @state_method(STATE_IDLE)
    def initialize_encryption(self, key, max_threads):
        key = str(range(256)).encode('hex')[:128]

        # Get the encryption request
        try:
            log.info('Waiting for encryption request...')
            client_request = self.read_json(encryption=False)
            requested_threads = client_request['requested-encryption-threads']
        except Exception, e:
            self.send_json({
                'error': 'Malformed file_request: {}'.format(str(e))
            }, encryption=False)
            raise

        # Create response
        response = {}
        response['message'] = 'Server will provide threads 0-{}'.format(
            max_threads)
        if requested_threads <= max_threads and requested_threads > 0:
            response['granted'] = True
        else:
            response['granted'] = False

        # Respond
        self.send_json(response, encryption=False)
        if not response['granted']:
            raise RuntimeError(
                'Unable to allocate encryption threads: {}'.format(
                    requested_threads))

        # Initialize Encryption
        self.encryptor = lib.encryption_init(key, requested_threads)
        self.decryptor = lib.decryption_init(key, requested_threads)
