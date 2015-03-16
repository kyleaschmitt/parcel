import os
import time

from parcel_thread import ParcelThread
from threading import Thread
from utils import state_method, print_download_information, monitor_transfer
from lib import lib
from log import get_logger
from http import parallel_http_download
from const import (
    # Lengths
    RES_CHUNK_SIZE,
    # Control messages
    CNTL_EXIT, CNTL_DOWNLOAD, CNTL_HANDSHAKE,
    # States
    STATE_IDLE,
)

# Logging
log = get_logger('client')


class Client(ParcelThread):

    @state_method('authenticate', 'download_files', 'download', STATE_IDLE)
    def download_files(self, file_ids, *args, **kwargs):
        """Download a list of files

        """

        if not file_ids:
            log.warn('No file ids given.')
            return

        for file_id in file_ids:
            log.info('Given file id: {}'.format(file_id))

        for file_id in file_ids:
            start = time.time()
            file_size = self.download_file(file_id, *args, **kwargs)
            stop = time.time()
            if file_size > 0:
                rate = (int(file_size)*8/1e9) / (stop - start)
                log.info(
                    'Download complete: {0:.2f} Gbps average'.format(rate))


class UDTClient(Client):

    def __init__(self, token, host='localhost', port=9000,
                 n_threads=4):

        self.n_threads = n_threads
        self.token = token

        client = lib.new_client()
        log.info('Connecting to server at {}:{}'.format(host, port))
        lib.client_start(client, str(host), str(port))
        super(Client, self).__init__(
            instance=client,
            socket=lib.client_get_socket(client),
            close_func=lib.client_close,
        )
        self.initialize_encryption('', n_threads)
        self.handshake()
        self.authenticate()

    @state_method('initialize_encryption')
    def handshake(self):
        """Handshake steps

        1. Send handshake
        2. Wait for handshake
        3. send our options

        """

        self.send_control(CNTL_HANDSHAKE, encryption=False)
        self.recv_control(CNTL_HANDSHAKE, encryption=False)
        self.send_json({
            'num_crypto_threads': 1,
            'version': 0.1,
        })

    @state_method('handshake')
    def authenticate(self):
        self.send_payload(self.token)

    def close(self):
        self.send_control(CNTL_EXIT)
        self.close_func(self.instance)

    @state_method('authenticate', 'download_files', 'download_file')
    def download_file(self, file_id, directory=None, print_stats=True):
        """Download steps:

        1. notify server of download state
        2. send file_id to download
        3. receive file info from server
        4. attempt to read into file

        """

        self.send_control(CNTL_DOWNLOAD)
        self.send_json({'file_id': file_id})
        file_info = self.read_json()

        if not directory:
            directory = os.path.abspath(os.getcwd())

        if file_info['error']:
            log.error('Unable to download file {}: {}'.format(
                file_id, file_info['error']))
            return -1

        file_size = int(file_info['file_size'])
        file_name = file_info.get('file_name', None)
        file_path = os.path.join(directory, '{}.{}'.format(file_id, file_name))

        print_download_information(file_id, file_size, file_name, file_path)

        # Download files
        print_stats = 1 if print_stats else 0
        monitor_thread = Thread(target=monitor_transfer,
                                args=(self, file_id, file_size))
        monitor_thread.start()
        ss = lib.client_recv_file(
            self.decryptor, self.instance, file_path, file_size,
            RES_CHUNK_SIZE, print_stats)
        monitor_thread.join()

        if ss < 0:
            raise RuntimeError('Download failed')

        if ss != file_size:
            log.error('File not completed {} != {}'.format(
                ss, file_size))
            return -1
        return ss

    @state_method(STATE_IDLE)
    def initialize_encryption(self, key, n_threads):
        key = str(range(256)).encode('hex')[:128]

        log.info('Requesting {} encryption threads'.format(n_threads))
        self.send_json({
            'requested-encryption-threads': n_threads
        }, encryption=False)

        log.info('Waiting for response...')
        response = self.read_json(encryption=False)
        if not response['granted']:
            log.error('Encryption threads not granted {}:'.format(
                response['message']))
            raise RuntimeError('Not granted encryption threads {}'.format(
                response['message']))
        else:
            log.info('Encryption threads granted {}:'.format(
                response['message']))

        self.encryptor = lib.encryption_init(key, n_threads)
        self.decryptor = lib.decryption_init(key, n_threads)


class HTTPClient(Client):

    def __init__(self, token, url, n_processes):
        self.n_processes = n_processes
        self.token = token
        self.url = url
        self.state = STATE_IDLE
        self.instance = None
        self.socket = None

    @state_method('download_files', 'download_file', STATE_IDLE)
    def download_file(self, file_id, directory=None, print_stats=False):
        if not directory:
            directory = os.path.abspath(os.getcwd())
        file_size = parallel_http_download(self.url, self.token, file_id,
                                           directory, self.n_processes)
        return file_size
