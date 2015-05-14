# If windows, don't attempt to load library
from intervaltree import Interval
import os
import time

import requests
import urlparse

from segment import SegmentProducer
from const import HTTP_CHUNK_SIZE
from log import get_logger
from utils import print_download_information, write_offset, md5sum,\
    print_closing_header, print_opening_header


# Are we running on windows?
if os.name == 'nt':
    from threading import Thread as Process
else:
    # Assume a posix system
    from multiprocessing import Process

# Logging
log = get_logger('client')


def download_worker(client, path, file_id, producer):
    while True:
        interval = producer.q_work.get()
        if interval is None:
            return log.debug('Producer returned with no more work')
        client.read_write_segment(path, file_id, interval, producer.q_complete)


class Client(object):

    def __init__(self, uri, token, n_procs, directory,
                 segment_md5sums=False, debug=False):
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
        self.segment_md5sums = segment_md5sums
        self.debug = debug

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
        name = attachment.split('filename=')[-1] if attachment else None
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
            log.error(
                'Transfer size incorrect: {} != {} expected'.format(
                    actual, expected))
            return False
        return True

    def get_file_path(self, file_id, file_name):
        """Function to standardize the output path for a download.

        :param str file_id: The id of the file
        :param str file_name: The file name
        :returns: A string specifying the full download path

        """

        if file_name:
            return os.path.join(self.directory, '{}_{}'.format(
                file_id, file_name))
        else:
            return os.path.join(self.directory, file_id)

    def get_state_file_path(self, file_id, file_name):
        """Function to standardize the state path for a download.

        :param str file_id: The id of the file
        :param str file_name: The file name
        :returns: A string specifying the full download path

        """

        if file_name:
            return os.path.join(self.directory, '.{}_{}.parcel'.format(
                file_id, file_name))
        else:
            return os.path.join(self.directory, '.{}.parcel'.format(file_id))

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
        # Create header that specifies range and make initial stream
        # request. Note the 1 subtracted from the end of the interval
        # is because the HTTP range request is inclusive of the top of
        # the interval.
        start, end = interval.begin, interval.end-1
        assert end >= start, 'Invalid segment range.'
        headers = self.construct_header(start, end)
        r = self.make_file_request(file_id, headers)

        # Iterate over the data stream
        log.debug('Initializing segment: {}-{}'.format(start, end))
        for chunk in r.iter_content(chunk_size=HTTP_CHUNK_SIZE):
            if not chunk:
                continue  # Empty are keep-alives.
            offset = start + written
            written += len(chunk)

            # Write the chunk to disk, create an interval that
            # represents the chunk, get md5 info if necessary, and
            # report completion back to the producer
            write_offset(path, chunk, offset)
            if self.segment_md5sums:
                iv_data = {'md5sum': md5sum(chunk)}
            else:
                iv_data = None
            segment = Interval(offset, offset+len(chunk), iv_data)
            q_complete.put(segment)

        if not self.check_transfer_size(
                written, interval.end - interval.begin):
            return self.read_write_segment(
                path, file_id, interval, q_complete)
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
            log.info(
                'Download complete: {0:.2f} Gbps average'.format(rate))

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
                if self.debug:
                    raise
            finally:
                print_closing_header(file_id)

    def parallel_download(self, file_id, verify=False):
        """Start ``self.n_procs`` to download the file.

        :params str file_id:
            String containing the id of the entity to download

        """

        # File informaion
        print_opening_header(file_id)
        name, size = self.request_file_information(file_id)
        path = self.get_file_path(file_id, name)

        # Where to load and save download state
        state_path = self.get_state_file_path(file_id, name)

        self.initialize_file_download(file_id, name, path, size)

        # Create segments to stream
        producer = SegmentProducer(
            file_id=file_id,
            file_path=path,
            save_path=state_path,
            load_path=state_path,
            n_procs=self.n_procs,
            size=size,
            check_segment_md5sums=self.segment_md5sums,
        )
        args = (self, path, file_id, producer)

        # Divide work amongst process pool
        pool = [Process(target=download_worker, args=args)
                for i in range(self.n_procs)]
        for p in pool:
            p.start()
        self.start_timer()
        producer.wait_for_completion()
        self.stop_timer()
