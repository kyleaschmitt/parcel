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
    client, file_id, path, segment, q_out = args
    return client.try_retry_read_write_segment(
        3, file_id, path, segment, q_out)


class Client(object):

    def __init__(self, uri, token, n_procs, directory):
        """Creates a parcel client object.

        :param str uri:
            The uri path [scheme://server:port/path] of the remote server
        :param str token:
            The authentication token that will be added to the HTTP
            X-Auth-Token header
        :param int n_procs:
            The number of processes to use in download
        :param str directory:
            The directory to which any data will be downloaded

        """

        self.token = token
        self.n_procs = n_procs
        self.uri = uri if uri.endswith('/') else uri + '/'
        self.directory = directory

        # Nullify timers
        self.start, self.stop = None, None

    ############################################################
    #                          Util
    ############################################################

    def split_file(self, size, blocks):
        """Given a file and number of blocks, divide the interval into a
        chunked workload.  The block sizes will be evenly distributed
        best as possible; the last block will contain the normal
        interval size or smaller.

        :param int size: The total size of the file
        :param int blocks: The number of blocks to divide the file into.

        """

        block_size = int(ceil(float(size)/blocks))
        segments = calculate_segments(0, size, block_size)
        return segments, block_size

    def check_transfer_size(self, actual, expected):
        """Simple validation on any expected versus actual sizes.

        :param int actual: The size that was actually transferred
        :param int actual: The size that was expected to be transferred

        """

        if actual != expected:
            raise ValueError(
                'Transfer size incorrect: {} != {} expected'.format(
                    actual, expected))

    def async_write(self, thread, path, chunk, offset):
        """Async write to a file with offset from the beginning. If ``thread``
        then join the last async write before continuing.

        :param Thread thread: The result of a previous async_write to block on
        :param str path: The path to the file to write to
        :param str chunk: The string-like object to write to file
        :param int offset: The offset from the beginning of the file
        :returns: A python Thread object that was spawned to write to the file

        """
        if thread:
            thread.join()
        thread = Thread(target=write_offset, args=(path, chunk, offset))
        thread.start()
        return thread

    ############################################################
    #                          REST
    ############################################################

    def construct_header(self, start=None, end=None):
        """Return a standard header for any parcel HTTP request.  If ``start``
        and ``end`` are specified, then the header will contain a Range
        request.

        :param int start: optional. The beginning of the range interval
        :param int end: optional.
            The end of the range interval. This value is inclusive.
            If give range A-B, then both bytes A and B will be
            included.
        :returns: A dictionary header containing the token

        """

        header = {
            'X-Auth-Token': self.token,
        }
        if start is not None and end is not None:
            header['Range'] = 'bytes={}-{}'.format(start, end)
            # provide host because it's mandatory, range request
            # may not work otherwise
            scheme, host, path, params, q, frag = urlparse.urlparse(self.uri)
            header['host'] = host
        return header

    def make_file_request(self, file_id, headers, verify=False, close=False):
        """Make request for file and return the response.

        :param str file_id: The id of the entity being requested.
        :param dict headers: Request headers. see :func:`construct_header()`.
        :param bool verify: Verify SSL hostname
        :param bool close:
            Automatically close the connection. Set to true if you just
            the response header.
        :returns: A `requests` response.

        """
        url = urlparse.urljoin(self.uri, file_id)
        log.debug('Request to {}'.format(url))
        r = requests.get(url, headers=headers, verify=verify, stream=True)
        r.raise_for_status()
        if close:
            r.close()
        return r

    def request_file_information(self, file_id):
        """Make a request to the data server for information on the file.

        :param str file_id: The id of the entity being requested.
        :returns: Tuple containing the name and size of the entity

        """

        headers = self.construct_header()
        r = self.make_file_request(file_id, headers, close=True)
        size = long(r.headers['Content-Length'])
        log.info('Request responded: {} bytes'.format(size))
        attachment = r.headers.get('content-disposition', None)
        name = attachment.split('filename=')[-1] if attachment else None
        return name, size

    def get_file_path(self, file_id, file_name):
        """Function to standardize the output path for a download.

        :param str file_id: The id of the file
        :param str file_name: The file name
        :returns: A string specifying the full download path

        """

        return os.path.join(self.directory, '{}_{}'.format(
            file_id, file_name))

    def read_write_segment(self, file_id, path, segment, q_out):
        """Read data from the data server and write it to a file.

        :param str file_id: The id of the file
        :params str path: A string specifying the full download path
        :params tuple segment:
            A tuple containing the interval to download (start, end)
        :params q_out: A multiprocessing Queue used for async reporting
        :returns: The total number of bytes written

        """

        written = 0
        write_thread = None
        start, end = segment
        log.debug('Initializing segment: {}-{}'.format(start, end))
        header = self.construct_header(start, end)
        r = self.make_file_request(file_id, header)
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

    def try_retry_read_write_segment(self, retries, *args, **kwargs):
        """A wrapper for :func:`read_write_segment()`.  Will on retry of the
        correct number of bytes was not downloaded.

        :params str path: A string specifying the full download path
        :params tuple segment:
            A tuple containing the interval to download (start, end)
        :params q_out: A multiprocessing Queue used for async reporting
        :params int retries: The number of times to retry on failure
        :returns: The total number of bytes written

        """

        try:
            return self.read_write_segment(*args, **kwargs)
        except ValueError as e:
            log.warn('Buffering error: {}'.format(str(e)))
            if retries <= 0:
                raise ValueError(
                    'Max buffer retries exceeded: {}'.format(str(e)))
            return self.try_retry_read_write_segment(
                retries-1, *args, **kwargs)

    ############################################################
    #                       Reporting
    ############################################################

    def initialize_file_download(self, file_id, name, path, size):
        """Start the file transfer. Start logging, set the file size.

        :param str file_id: The id of the file
        :param str name: The name of the file
        :params str path: A string specifying the full download path
        :params int size: The total size of the file
        :returns: None

        """

        self.start_timer()
        print_download_information(file_id, size, name, path)
        set_file_length(path, size)
        self.pbar = get_pbar(file_id, size)

    def update_file_download(self, received):
        """Currently only updates the file download progressbar.

        :param int received: The amount to update the progressbar by.
        :returns: None

        """

        self.pbar.update(self.pbar.currval + received)

    def finalize_file_download(self, size, total_received):
        """Finalize the download. Validate the download and clean up reporting.

        :params int size: The expcected size of the file
        :params int total_received: The number of bytes actually received.
        :returns: None

        """

        self.check_transfer_size(size, total_received)
        self.stop_timer(size)
        self.pbar.finish()

    def start_timer(self):
        """Start a download timer.

        :returns: None

        """

        self.start_time = time.time()

    def stop_timer(self, file_size=None):
        """Stop a download timer and pring a summary.

        :returns: None

        """

        self.stop_time = time.time()
        if file_size > 0:
            rate = (int(file_size)*8/1e9) / (self.stop_time - self.start_time)
            log.info('Download complete: {0:.2f} Gbps average'.format(rate))

    ############################################################
    #                     Main download
    ############################################################

    def download_files(self, file_ids, *args, **kwargs):
        """Download a list of files.

        :params list file_ids:
            A list of strings containing the ids of the entities to download

        """
        # Short circuit of no ids given
        if not file_ids:
            log.warn('No file ids given.')
            return

        # Log file ids
        for file_id in file_ids:
            log.info('Given file id: {}'.format(file_id))

        # Download each file
        for file_id in set(file_ids):
            self.parallel_download(file_id, *args, **kwargs)

    def parallel_download(self, file_id, verify=False):
        """Start ``self.n_procs`` to download the file.

        :params str file_id:
            String containing the id of the entity to download

        """

        # Process management
        manager = Manager()
        q = manager.Queue()

        # File informaion
        name, size = self.request_file_information(file_id)
        path = self.get_file_path(file_id, name)

        # Create segments to stream
        segments, block_size = self.split_file(size, self.n_procs)
        self.initialize_file_download(file_id, name, path, size)
        args = ((self, file_id, path, segment, q) for segment in segments)

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
