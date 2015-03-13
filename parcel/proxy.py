from ctypes import cdll, create_string_buffer
import json
import atexit
import os
import signal
import urlparse
from functools import wraps
from threading import Thread
import requests

from log import get_logger

from const import (
    # Lengths
    LEN_CONTROL, LEN_PAYLOAD_SIZE, RES_CHUNK_SIZE,
    # Control messages
    CNTL_EXIT, CNTL_DOWNLOAD, CNTL_HANDSHAKE,
    # States
    STATE_IDLE,
)

# Load library
INSTALL_PATH = '/usr/local/lib/'
lib = cdll.LoadLibrary(os.path.join(INSTALL_PATH, 'lparcel.so'))

# Signal handling for external calls
signal.signal(signal.SIGINT, signal.SIG_DFL)

# Logging
log = get_logger()


def _check_status_code(self, r, url):
    if r.status_code != 200:
        # Failed to get file, notify the client
        msg = 'Request failed: {} {}'.format(url, r.text)
        log.warn(msg)
        self.send_payload(json.dumps({
            'error': r.text, 'status_code': r.status_code}))
        raise RuntimeError(msg)


def _send_file_header(self, r, url):
    """Send a header to the client.

    :returns: The file size
    """

    # Client assumes a metadata response first.
    try:
        size = long(r.headers['Content-Length'])
        log.info('Request responded: {} bytes'.format(size))
    except KeyError:
        msg = 'Request without length: {}'.format(url)
        log.error(msg)
        self.send_payload(json.dumps({
            'error': msg, 'status_code': r.status_code}))

    # Send file header to client
    self.send_payload(json.dumps({
        'error': None,
        'file_size': size,
        'status_code': r.status_code,
    }))
    return size


def _stream_data_to_client(self, r, file_size):
    total_sent = 0
    # Then streaming of the data itself.
    for chunk in r.iter_content(chunk_size=RES_CHUNK_SIZE):
        if not chunk:
            continue  # Empty are keep-alives.
        rs = len(chunk)
        self.send(chunk, rs)
        total_sent += rs
    if total_sent != file_size:
        raise RuntimeError(
            'Proxy terminated prematurely: sent {} != expected {}'.format(
                total_sent, file_size))


def proxy_file_to_client(self, file_id, verify=False):

    url = urlparse.urljoin(self.data_server_url, file_id)
    log.info('Download request: {}'.format(url))

    headers = {
        'X-Auth-Token': self.token,
    }

    r = requests.get(url, headers=headers, verify=verify, stream=True)
    _check_status_code(self, r, url)
    size = _send_file_header(self, r, url)
    _stream_data_to_client(self, r, size)
