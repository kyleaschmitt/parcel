from ctypes import create_string_buffer
from utils import state_method, vec
import json
from math import ceil
import urlparse
from log import get_logger

from const import (
    # Lengths
    LEN_CONTROL, LEN_PAYLOAD_SIZE,
    # Control messages
    CNTL_EXIT, RES_CHUNK_SIZE,
    # States
    STATE_IDLE,
)
from utils import calculate_segments

from lib import lib
import requests

# Logging
log = get_logger('parcel')


class ParcelThread(object):

    def __init__(self, instance, socket, close_func):
        """
        Creates a new udpipeClient instance from shared object library
        """

        self.state = STATE_IDLE
        self.encryptor = None
        self.decryptor = None
        self.instance = instance
        self.socket = socket
        self.close_func = close_func
        self.uri = None
        self.token = None
        log.debug('New instance {}'.format(self))

    def __repr__(self):
        return '<{}({}, {})>'.format(
            type(self).__name__, self.instance, self.socket)

    def assert_encryption(self):
        assert self.encryptor, 'Encryptor not initialized'
        assert self.decryptor, 'Decryptor not initialized'

    ############################################################
    #                     Library Wrappers
    ############################################################

    def read_size(self, size, encryption=True):
        buff = create_string_buffer(size)
        if encryption:
            self.assert_encryption()
            rs = lib.read_size(self.decryptor, self.socket, buff, size)
        else:
            rs = lib.read_size_no_encryption(self.socket, buff, size)
        if (rs == -1):
            raise Exception('Unable to read from socket.')
        return buff.value

    def send(self, data, size=None, encryption=True, encrypt_inplace=False):
        if encrypt_inplace and encryption:
            assert isinstance(data, str)
            # copy because encryption is in place
            to_send = (data+'\0')[:-1]
        else:
            to_send = data
        if size is None:
            size = len(data)
        if encryption:
            self.assert_encryption()
            ss = lib.send_data(self.encryptor, self.socket, to_send, size)
        else:
            ss = lib.send_data_no_encryption(self.socket, to_send, size)
        if ss != size:
            raise RuntimeError('Unable to write to socket.')

    ############################################################
    #                     Transfer Functions
    ############################################################

    def send_payload_size(self, size, **send_args):
        buff = create_string_buffer(LEN_PAYLOAD_SIZE)
        buff.value = str(size)
        self.send(buff, LEN_PAYLOAD_SIZE, **send_args)

    def read_payload_size(self, **read_args):
        payload_size = int(self.read_size(LEN_PAYLOAD_SIZE, **read_args))
        return payload_size

    def next_payload(self, **read_args):
        payload_size = self.read_payload_size(**read_args)
        return self.read_size(payload_size, **read_args)

    def send_payload(self, payload, size=None, **send_args):
        if size is None:
            size = len(payload)
        self.send_payload_size(size, **send_args)
        self.send(payload, size, **send_args)

    def send_control(self, control, **send_args):
        self.send_json({'CONTROL': control}, **send_args)

    def recv_control(self, expected=None, **read_args):
        cntl_json = self.read_json(**read_args)
        try:
            control = cntl_json['CONTROL']
        except KeyError:
            log.error('Received a non-control message: {}'.format(cntl_json))
            raise
        log.debug('CONTROL: {}'.format(control))
        if expected is not None and control not in vec(expected):
            raise RuntimeError('Unexpected control msg: {} != {}'.format(
                control, expected))
        return control

    def send_json(self, doc, **send_args):
        payload = json.dumps(doc)
        self.send_payload(payload, size=len(payload), **send_args)

    def read_json(self, **read_args):
        return json.loads(self.next_payload(**read_args))

    ############################################################
    #                     State Functions
    ############################################################

    def close(self):
        self.close_func(self.instance)

    @state_method(STATE_IDLE)
    def handshake(self, *args, **kwargs):
        raise NotImplementedError()

    @state_method('handshake')
    def authenticate(self, *args, **kwargs):
        raise NotImplementedError()

    ############################################################
    #                          Util
    ############################################################

    def split_file(self, size, blocks):
        block_size = int(ceil(float(size)/blocks))
        segments = calculate_segments(0, size, block_size)
        return segments, block_size

    ############################################################
    #                   REST API Functions
    ############################################################

    def request_file_information(self, file_id):
        headers = self.construct_header()
        r = self.make_file_request(headers, close=True)
        size, name = self.parse_file_header(r, file_id)
        return name, size

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

    def read_range_to_file(self, path, url, headers, start, end):
        headers = self.construct_header_with_range(start, end)
        log.debug('Reading range: [{}]'.format(headers.get('Range')))
        r = requests.get(url, headers=headers, verify=False, stream=True)
        offset = start
        total_written = 0
        # Then streaming of the data itself.
        for chunk in r.iter_content(chunk_size=RES_CHUNK_SIZE):
            if not chunk:
                continue  # Empty are keep-alives.
            yield chunk
            offset += len(chunk)
            total_written += len(chunk)

    def check_transfer_size(self, actual, expected):
        if actual != expected:
            raise ValueError(
                'Transfer size incorrect: {} != {} expected'.format(
                    actual, expected))

    def parse_ranges(self, ranges):
        """Validate an HTTP ranges, throwing an exception if it isn't something
        we support.

        """
        ranges = ranges.strip()
        unit, nums = ranges.split("=")
        if unit != "bytes":
            raise RuntimeError(
                "Only byte rangess are supported, not {}".format(unit))
        begin, end = nums.split("-")
        begin, end = int(begin), int(end)
        if end < begin:
            raise ValueError("bad range: {}".format(ranges))
        return begin, end

    def parse_file_header(self, r, url):
        """Send a header to the client.

        :returns: The file size and name
        """

        # Client assumes a metadata response first.
        try:
            size = long(r.headers['Content-Length'])
            log.info('Request responded: {} bytes'.format(size))
        except KeyError:
            msg = 'Request without length: {}'.format(url)
            log.error(msg)

        attachment = r.headers.get('content-disposition', None)
        file_name = attachment.split('filename=')[-1] if attachment else None

        return size, file_name
