from math import ceil
from multiprocessing import Manager
from multiprocessing.pool import Pool
from threading import Thread
import os
import requests
import time
import urlparse

from const import HTTP_CHUNK_SIZE
from log import get_logger
from utils import print_download_information, set_file_length, get_pbar,\
    write_offset, calculate_segments

# Logging
log = get_logger('client')


def download_worker(args):
    client, path, segment, q_out = args
    return client.try_retry_read_write_segment(path, segment, q_out)


class Client(object):

    def __init__(self, uri, token, n_procs, directory):
        self.token = token
        self.n_procs = n_procs
        self.uri = uri
        self.directory = directory

    ############################################################
    #                          Util
    ############################################################

    def split_file(self, size, blocks):
        block_size = int(ceil(float(size)/blocks))
        segments = calculate_segments(0, size, block_size)
        return segments, block_size

    def check_transfer_size(self, actual, expected):
        if actual != expected:
            raise ValueError(
                'Transfer size incorrect: {} != {} expected'.format(
                    actual, expected))

    def async_write(self, thread, path, chunk, offset):
        """
        Async write to a file with offset from the beginning.

        If thread then join the last async write before continuing
        """
        if thread:
            thread.join()
        thread = Thread(target=write_offset, args=(path, chunk, offset))
        thread.start()
        return thread

    ############################################################
    #                          REST
    ############################################################

    def construct_header(self):
        return {
            'X-Auth-Token': self.token,
        }

    def construct_header_with_range(self, start, end):
        header = self.construct_header()
        header['Range'] = 'bytes={}-{}'.format(start, end)
        # provide host because it's mandatory, range request
        # may not work otherwise
        scheme, host, path, params, q, frag = urlparse.urlparse(self.uri)
        header['host'] = host
        return header

    def make_file_request(self, file_id, headers, verify=False, close=False):
        """Make request for file, just get the header.

        """
        url = urlparse.urljoin(self.uri, file_id)
        log.debug('Request to {}'.format(url))
        r = requests.get(url, headers=headers, verify=verify, stream=True)
        r.raise_for_status()
        if close:
            r.close()
        return r

    def request_file_information(self, file_id):
        headers = self.construct_header()
        r = self.make_file_request(file_id, headers, close=True)
        size, name = self.parse_file_header(r, file_id)
        return name, size

    def parse_file_header(self, r, url):
        """Send a header to the client.

        :returns: The file size and name
        """

        size = long(r.headers['Content-Length'])
        log.info('Request responded: {} bytes'.format(size))
        attachment = r.headers.get('content-disposition', None)
        file_name = attachment.split('filename=')[-1] if attachment else None
        return size, file_name

    def get_file_path(self, file_name):
        return os.path.join(self.directory, '{}.{}'.format(
            self.file_id, file_name))

    def read_write_segment(self, path, segment, q_out):
        written = 0
        write_thread = None
        start, end = segment
        log.debug('Initializing segment: {}-{}'.format(start, end))
        header = self.construct_header_with_range(start, end)
        r = self.make_file_request(self.file_id, header)
        for chunk in r.iter_content(chunk_size=HTTP_CHUNK_SIZE):
            if not chunk:
                continue  # Empty are keep-alives.
            # Write async to file
            write_thread = self.async_write(
                write_thread, path, chunk, start + written)
            written += len(chunk)
            q_out.put(len(chunk))  # for async reporting
        self.check_transfer_size(end - start + 1, written)
        return written

    def try_retry_read_write_segment(self, path, segment, q_out, retries=3):
        try:
            return self.read_write_segment(path, segment, q_out)
        except ValueError as e:
            log.warn('Buffering error: {}'.format(str(e)))
            if retries > 0:
                return self.try_retry_read_write_segment(
                    path, segment, q_out, retries-1)
            else:
                raise ValueError(
                    'Max buffer retries exceeded: {}'.format(str(e)))

    ############################################################
    #                       Reporting
    ############################################################

    def initialize_file_download(self, name, path, size):
        self.start_timer()
        print_download_information(self.file_id, size, name, path)
        set_file_length(path, size)
        self.pbar = get_pbar(self.file_id, size)

    def update_file_download(self, received):
        self.pbar.update(self.pbar.currval + received)

    def finalize_file_download(self, size, total_received):
        self.check_transfer_size(size, total_received)
        self.stop_timer(size)
        self.pbar.finish()

    def start_timer(self):
        self.start_time = time.time()

    def stop_timer(self, file_size=None):
        self.stop_time = time.time()
        if file_size > 0:
            rate = (int(file_size)*8/1e9) / (self.stop_time - self.start_time)
            log.info('Download complete: {0:.2f} Gbps average'.format(rate))

    ############################################################
    #                     Main download
    ############################################################

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
            self.parallel_download(file_id)

    def parallel_download(self, file_id, verify=False):

        # Process management
        manager = Manager()
        q = manager.Queue()

        # File informaion
        self.file_id = file_id
        name, size = self.request_file_information(file_id)
        path = self.get_file_path(name)

        # Create segments to stream
        segments, block_size = self.split_file(size, self.n_procs)
        self.initialize_file_download(name, path, size)
        args = ((self, path, segment, q) for segment in segments)

        # Divide work amongst process pool
        pool = Pool(self.n_procs)
        async_result = pool.map_async(download_worker, args)

        # Monitor progress
        while self.pbar.currval < size:
            self.update_file_download(q.get())

        # Finalize download
        total_received = sum(async_result.get())
        self.finalize_file_download(size, total_received)
        return total_received
