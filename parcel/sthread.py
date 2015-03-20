import atexit
import urlparse
from multiprocessing.pool import ThreadPool
from multiprocessing import Manager, Process
import requests

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


def write_to_socket(send, chunk):
    return send(chunk, inplace=True)


def read_worker(q_out, url, headers):
    r = requests.get(url, headers=headers, verify=False, stream=True)
    # Then streaming of the data itself.
    for chunk in r.iter_content(chunk_size=RES_CHUNK_SIZE):
        if not chunk:
            continue  # Empty are keep-alives.
        q_out.put(chunk)
    r.close()


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
        self.read_token()

        # Register teardown message callback
        atexit.register(self.close)

        # Start thread processing
        while self.live:
            self.event_loop()

    @state_method(STATE_IDLE)
    def initialize_encryption(self):
        if not self.private_key:
            raise RuntimeError('No private key for encryption.')
        log.info('Performing pubkey handshake.')
        private_key, iv = auth.server_auth(
            self.send_payload,
            self.next_payload,
            self.private_key,
            encryption=False,
        )
        self.encryptor = lib.encryption_init(private_key, iv)
        self.decryptor = lib.decryption_init(private_key, iv)

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

    @state_method('event_loop')
    def download(self):
        request = self.read_json()
        file_id = request['file_id']
        name, size = self.request_file_information(file_id)
        start = request.get('start', 0)
        end = request.get('end', size)
        url = urlparse.urljoin(self.uri, file_id)
        headers = self.construct_header_with_range(start, end)
        log.debug('Reading range: [{}]'.format(headers.get('Range')))

        manager = Manager()
        q = manager.Queue()

        reader = Process(target=read_worker, args=(q, url, headers))
        reader.start()

        while reader.is_alive():
            written = self.send(q.get())
            if written < 0:
                raise RuntimeError('Unable to write to socket.')

    def read_token(self):
        self.token = self.next_payload()

    def send_file_info(self):
        file_id = self.next_payload()
        try:
            name, size = self.request_file_information(file_id)
        except Exception as e:
            self.send_json({'error': str(e)})
            raise

        self.send_json({
            'file_name': name,
            'file_size': size
        })
