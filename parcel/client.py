from . import const
from . import utils
from .download_stream import DownloadStream
from .log import get_logger
from .portability import colored
from .portability import Process
from .segment import SegmentProducer

import requests
import os
import time

# Logging
log = get_logger('client')


class Client(object):

    def __init__(self, uri, token, n_procs, directory=None,
                 debug=False, **kwargs):

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

        DownloadStream.http_chunk_size = kwargs.get(
            'http_chunk_size', const.HTTP_CHUNK_SIZE)
        DownloadStream.check_segment_md5sums = kwargs.get(
            'segment_md5sums', True)
        SegmentProducer.save_interval = kwargs.get(
            'save_interval', const.SAVE_INTERVAL)
        self.related_files = kwargs.get(
            'download_related_files', True)
        self.annotations = kwargs.get(
            'download_annotations', True)

        self.debug = debug
        self.directory = directory or os.path.abspath(os.getcwd())
        self.n_procs = n_procs
        self.start = None
        self.stop = None
        self.token = token
        self.uri = self.fix_uri(uri)

    @staticmethod
    def fix_uri(uri):
        uri = uri if uri.endswith('/') else '{}/'.format(uri)
        if not (uri.startswith('https://') or uri.startswith('http://')):
            uri = 'https://{}'.format(uri)
        return uri

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
        downloaded, errors = [], {}
        for file_id in set(file_ids):
            try:
                self.parallel_download(
                    file_id,
                    *args, **kwargs)
                downloaded.append(file_id)
            except Exception as e:
                log.error('Unable to download {}: {}'.format(
                    file_id, str(e)))
                errors[file_id] = str(e)
                if self.debug:
                    raise
            finally:
                utils.print_closing_header(file_id)

        # Print error messages
        self.print_summary(downloaded, errors)
        for file_id, error in errors.iteritems():
            print('ERROR: {}: {}'.format(file_id, error))

        return downloaded, errors

    def print_summary(self, downloaded, errors):
        print('\nSUMMARY:')
        if downloaded:
            print('{}: {}'.format(
                colored('Successfully downloaded', 'green'), len(downloaded)))
        if errors:
            print('{}: {}'.format(
                colored('Failed to download', 'red'), len(errors)))
        print('')

    def get_related_files(self, file_id):
        """Query the GDC api for related files.

        :params str file_id: String containing the id of the primary entity
        :returns: A list of related file ids

        """
        url = '{}/files/{}?fields=related_files.file_id'.format(
            self.uri.replace('/data/', ''), file_id)
        try:
            r = requests.get(url, verify=False)
            r.raise_for_status()
            related_files = [rf['file_id'] for rf in
                             r.json()['data'].get('related_files', [])]
        except Exception as e:
            log.warn('Unable to get related files for {}: {}'.format(
                file_id, e))
            related_files = []
        log.info('Related files for {}: {}'.format(
            file_id, related_files))
        return related_files

    def download_related_files(self, file_id, directory):
        """Finds and downloads files related tol the primary entity.

        :param str file_id: String containing the id of the primary entity
        :param str directory: The primary entity's directory

        """
        for related_file in self.get_related_files(file_id):
            self.parallel_download(
                related_file,
                directory,
                download_related_files=False,
                download_annotations=False,
            )

    def get_annotations(self, file_id):
        """Query the GDC api for annotations and download them to a file.

        :params str file_id: String containing the id of the primary entity
        :returns: A list of related file ids

        """
        url = '{}/files/{}?fields=annotations.annotation_id'.format(
            self.uri.replace('/data/', ''), file_id)
        try:
            r = requests.get(url, verify=False)
            r.raise_for_status()
            annotations = [a['annotation_id'] for a in
                           r.json()['data'].get('annotations', [])]
        except Exception as e:
            log.warn('Unable to get related files for {}: {}'.format(
                file_id, e))
            annotations = []
        return annotations

    def download_annotations(self, file_id, directory):
        annotations = self.get_annotations(file_id)
        if annotations:
            self.parallel_download(
                ','.join(annotations),
                directory,
                download_related_files=False,
                download_annotations=False,
            )

    def parallel_download(self, file_id, directory=None,
                          download_related_files=None,
                          download_annotations=None):
        """Start ``self.n_procs`` to download the file.

        :params str file_id:
            String containing the id of the entity to download

        """

        # File informaion
        utils.print_opening_header(file_id)
        log.info('Getting file information...')
        directory = (os.path.join(self.directory, file_id)
                     if directory is None else directory)
        download = DownloadStream(file_id, self.uri, directory, self.token)
        download.init()

        # Create segments producer to stream
        n_procs = 1 if download.size < .01 * const.GB else self.n_procs
        producer = SegmentProducer(download, n_procs)

        def download_worker():
            while True:
                segment = producer.q_work.get()
                if segment is None:
                    return log.debug('Producer returned with no more work')
                download.write_segment(segment, producer.q_complete)

        # Divide work amongst process pool
        pool = [Process(target=download_worker) for i in range(n_procs)]

        # Start pool
        map(lambda p: p.start(), pool)
        self.start_timer()

        # Wait for file to finish download
        producer.wait_for_completion()
        self.stop_timer()

        # Recurse on related files
        if download_related_files or (
                download_related_files is None and self.related_files):
            self.download_related_files(file_id, directory)

        # Recurse on annotations
        if download_annotations or (
                download_annotations is None and self.annotations):
            self.download_annotations(file_id, directory)
