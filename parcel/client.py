import time
import os
from multiprocessing.pool import ThreadPool, Pool
from multiprocessing import Manager
from parcel_thread import ParcelThread
import Crypto

from log import get_logger
from const import STATE_IDLE, RES_CHUNK_SIZE
from utils import (
    print_download_information, set_file_length, get_pbar, state_method
)

# Logging
log = get_logger('client')


def download_worker(args):
    client, path, segment, q_out = args
    return client.try_retry_read_write_segment(path, segment, q_out)


class Client(ParcelThread):

    def __init__(self, uri, token, n_procs, directory):
        super(Client, self).__init__(None, None, None)
        self.token = token
        self.n_procs = n_procs
        self.uri = uri
        self.directory = directory

    def get_segment_iterator(self, start, end, *args, **kwargs):
        raise NotImplementedError()

    def try_retry_read_write_segment(self, path, segment, retries=3):
        raise NotImplementedError()

    def read_write_segment(self, path, segment):
        raise NotImplementedError()

    def start_timer(self):
        self.start_time = time.time()

    def stop_timer(self, file_size=None, print_stats=True):
        self.stop_time = time.time()
        if file_size > 0 and print_stats:
            rate = (int(file_size)*8/1e9) / (self.stop_time - self.start_time)
            log.info('Download complete: {0:.2f} Gbps average'.format(rate))

    def get_file_path(self, file_name):
        return os.path.join(self.directory, '{}.{}'.format(
            self.file_id, file_name))

    def initialize_file_download(self, name, path, size):
        self.start_timer()
        print_download_information(self.file_id, size, name, path)
        set_file_length(path, size)
        self.pbar = get_pbar(self.file_id, size)

    def finalize_file_download(self, size, total_received):
        self.check_transfer_size(size, total_received)
        self.stop_timer(size)
        self.pbar.finish()

    def update_file_download(self, received):
        self.pbar.update(self.pbar.currval + received)

    @state_method('handshake', 'download_files', 'download', STATE_IDLE)
    def download_files(self, file_ids, *args, **kwargs):
        """Download a list of files

        """
        self.start = None
        self.stop = None

        # Remove duplicates
        file_ids = set(file_ids)

        # Short circuit of no ids given
        if not file_ids:
            log.warn('No file ids given.')
            return

        # Log file ids
        for file_id in file_ids:
            log.info('Given file id: {}'.format(file_id))

        # Download each file
        for file_id in file_ids:
            self.download_file(file_id)

    @state_method('download_files', 'download_file', STATE_IDLE)
    def download_file(self, file_id, print_stats=False,
                      block_size=RES_CHUNK_SIZE):
        file_size = self.parallel_download(file_id)
        return file_size

    def make_pickleable(self):
        pass

    def parallel_download(self, file_id, verify=False):

        # Process management
        manager = Manager()
        q = manager.Queue()

        # File informaion
        self.file_id = file_id
        name, size = self.request_file_information()
        path = self.get_file_path(name)

        # Create segments to stream
        segments, block_size = self.split_file(size, self.n_procs)
        self.initialize_file_download(name, path, size)
        args = ((self, path, segment, q) for segment in segments)

        # Divide work amongst process pool
        pool = ThreadPool(self.n_procs, initializer=Crypto.Random.atfork())
        self.make_pickleable()
        async_result = pool.map_async(download_worker, args)

        # Monitor progress
        while self.pbar.currval < size:
            self.update_file_download(q.get())

        # Finalize download
        total_received = sum(async_result.get())
        self.finalize_file_download(size, total_received)
        return total_received
