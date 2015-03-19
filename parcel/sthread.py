import atexit
import urlparse
from threading import Thread

from parcel import auth
from parcel_thread import ParcelThread
from utils import state_method
from lib import lib
from log import get_logger
from const import (
    CNTL_EXIT, CNTL_DOWNLOAD, CNTL_HANDSHAKE,
    STATE_IDLE, RES_CHUNK_SIZE
)

# Logging
log = get_logger('sthread')


class ServerThread(ParcelThread):

    def __init__(self, instance, data_server_url, max_enc_threads,
                 buffer_processes, prikey=None):
        super(ServerThread, self).__init__(
            instance=instance,
            socket=lib.sthread_get_socket(instance),
            close_func=lib.sthread_close,
        )

        # Set attributes
        self.buffer_processes = buffer_processes
        self.data_server_url = data_server_url
        self.live = True
        self.send_thread = None

        # Encryption attributes
        self.prikey = prikey
        self.key = None
        self.iv = None

        # Initialize thread
        self.initialize_encryption('', max_enc_threads)
        self.handshake()
        self.authenticate()

        atexit.register(self.close)

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
        if self.prikey:  # Server private key specified - perform exchange.
            log.info('Performing pubkey handshake.')
            self.key, self.iv = auth.server_auth(
                self.send_payload,
                self.next_payload,
                self.prikey,
                encryption=False,
            )
        # TODO need to move token passing to after encryption has been enabled
        self.token = self.next_payload()
        if self.token:
            log.info('Connected with token.')

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
        try:
            file_request = self.read_json()
            file_id = file_request['file_id']
            ranges = file_request.get('Range', None)

        except Exception as e:
            self.send_json({
                'error': 'Malformed file_request: {}'.format(str(e))})
            raise

        try:
            self.proxy_file_to_client(file_id, self.buffer_processes, ranges)
        except Exception as e:
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
        except Exception as e:
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
        else:
            log.info('Granted request for {} threads'.format(
                requested_threads))

        # Initialize Encryption
        self.encryptor = lib.encryption_init(key, requested_threads)
        self.decryptor = lib.decryption_init(key, requested_threads)

    def sthread_join_send_thread(self):
        """If the sthread already has a send_thread, then join it

        :returns: None

        """
        if self.send_thread:
            self.send_thread.join()
            self.send_thread = None

    def udt_send_blocks(self, blocks):
        """Loop over blocks and send them serially.  Included here as a target
        for async writes to UDT.

        :returns: None

        """
        for block in blocks:
            log.debug('Sending {} bytes'.format(len(block)))
            self.send(block, len(block))

    def send_async(self, blocks):
        """Join any previously started send thread, and start a new one

        :returns: None

        """
        self.join_send_thread(self)
        self.send_thread = Thread(
            target=self.udt_send_blocks, args=(self, blocks))
        self.send_thread.start()

    def async_stream_data_to_client(self, url, file_size, headers,
                                    processes, buffer_retries,
                                    block_size=RES_CHUNK_SIZE):
        """Buffer and send

        1. async buffer get in parallel
        2. async send the blocks that we got last time (none the 1st round)
        3. wait for the buffering to return
        4. goto 1 until read complete
        5. send last set of blocks

        """
        log.info('Proxying {} to client'.format(url))

        total_sent = 0

        blocks = []
        while total_sent < file_size:
            self.send_async(self, blocks)
            self.check_transfer_size(file_size, total_sent)

    def proxy_file_to_client(self, file_id, processes, verify=False,
                             buffer_retries=4, ranges=None):

        if ranges:
            parse_range(ranges)
            url = urlparse.urljoin(self.data_server_url, file_id)
            log.info('Download request: {}'.format(url))

        headers = construct_header(self.token)
        try:
            errors, size, file_name, status_code = self.make_file_request(
                url, headers)
        except Exception as e:
            self.send_json({'error': str(e)})
            return str(e)

        # Send file header to client
        self.send_json({
            'error': errors,
            'file_size': size,
            'file_name': file_name,
            'status_code': status_code,
        })

        if not errors:
            self.async_stream_data_to_client(
                url, size, headers, processes, buffer_retries, ranges)

        return None
