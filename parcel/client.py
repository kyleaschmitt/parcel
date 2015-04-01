from multiprocessing import Process
from intervaltree import Interval
from threading import Thread
import os
import time

import requests
import urlparse

from segment import SegmentProducer
from const import HTTP_CHUNK_SIZE
from log import get_logger
from utils import print_download_information, set_file_length, get_pbar,\
    write_offset

# Logging
log = get_logger('client')


def download_worker(client, path, file_id, producer):
    while True:
        interval = producer.q_work.get()
        if interval is None:
            return log.debug('Producer returned with no more work')
        client.read_write_segment(path, file_id, interval, producer.q_complete)


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

    def make_file_request(self, file_id, headers, verify=False,
                          close=False, max_retries=16):
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

        # Set urllib3 retries and mount for session
        a = requests.adapters.HTTPAdapter(max_retries=max_retries)
        s = requests.Session()
        s.mount(urlparse.urlparse(url).scheme, a)

        r = s.get(url, headers=headers, verify=verify, stream=True)
        try:
            r.raise_for_status()
        except Exception as e:
            raise RuntimeError('{}: {}'.format(str(e), r.text))
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
        name = attachment.split('filename=')[-1] if attachment else 'untitled'
        return name, size

    ############################################################
    #                          Util
    ############################################################

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

    def get_file_path(self, file_id, file_name):
        """Function to standardize the output path for a download.

        :param str file_id: The id of the file
        :param str file_name: The file name
        :returns: A string specifying the full download path

        """

        return os.path.join(self.directory, '{}_{}'.format(
            file_id, file_name))

    def read_write_segment(self, path, file_id, interval, q_complete):
        """Read data from the data server and write it to a file.

        :param str file_id: The id of the file
        :params str path: A string specifying the full download path
        :params tuple segment:
            A tuple containing the interval to download (start, end)
        :params q_out: A multiprocessing Queue used for async reporting
        :returns: The total number of bytes written

        """

        written = 0
        start, end = interval.begin, interval.end-1
        headers = self.construct_header(start, end)
        r = self.make_file_request(file_id, headers)
        log.debug('Initializing segment: {}-{}'.format(start, end))
        for chunk in r.iter_content(chunk_size=HTTP_CHUNK_SIZE):
            if not chunk:
                continue  # Empty are keep-alives.
            offset = start + written
            written += len(chunk)
            # Write async to file
            write_offset(path, chunk, offset)
            # Report completion
            q_complete.put(Interval(offset, offset+len(chunk)))
        self.check_transfer_size(end - start + 1, written)
        return written

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

        print_download_information(file_id, size, name, path)
        set_file_length(path, size)

    def finalize_file_download(self, size, total_received):
        """Finalize the download. Validate the download and clean up reporting.

        :params int size: The expcected size of the file
        :params int total_received: The number of bytes actually received.
        :returns: None

        """

        self.check_transfer_size(size, total_received)

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
            try:
                self.parallel_download(file_id, *args, **kwargs)
            except Exception as e:
                log.error('Unable to download {}: {}'.format(
                    file_id, str(e)))
                raise

    def parallel_download(self, file_id, verify=False):
        """Start ``self.n_procs`` to download the file.

        :params str file_id:
            String containing the id of the entity to download

        """

        # File informaion
        name, size = self.request_file_information(file_id)
        path = self.get_file_path(file_id, name)

        # Where to load and save download state
        save_path = '{path}.state'.format(path=path)
        load_path = save_path

        self.initialize_file_download(file_id, name, path, size)

        # Create segments to stream
        producer = SegmentProducer(
            file_id, save_path, load_path, self.n_procs, size)
        args = (self, path, file_id, producer)

        # Divide work amongst process pool
        pool = [Process(target=download_worker, args=args)
                for i in range(self.n_procs)]
        for p in pool:
            p.start()
        self.start_timer()
        producer.wait_for_completion()
        self.stop_timer()
