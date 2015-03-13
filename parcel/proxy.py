import json
import urlparse
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


# Logging
log = get_logger()


def _check_status_code(sthread, r, url):
    if r.status_code != 200:
        # Failed to get file, notify the client
        msg = 'Request failed: {} {}'.format(url, r.text)
        log.warn(msg)
        sthread.send_payload(json.dumps({
            'error': r.text, 'status_code': r.status_code}))
        raise RuntimeError(msg)


def _send_file_header(sthread, r, url):
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
        sthread.send_payload(json.dumps({
            'error': msg, 'status_code': r.status_code}))

    # Send file header to client
    sthread.send_payload(json.dumps({
        'error': None,
        'file_size': size,
        'status_code': r.status_code,
    }))
    return size


def _send_async(sthread, block):
    return sthread.send(block, len(block))


def _stream_data_to_client(sthread, r, file_size):
    """Buffer and send until StopIteration

    """

    total_sent = 0
    for chunk in r.iter_content(chunk_size=RES_CHUNK_SIZE):
        if not chunk:
            continue  # Empty are keep-alives.
        _send_async(sthread, chunk)
        total_sent += len(chunk)
    if total_sent != file_size:
        raise RuntimeError(
            'Proxy terminated prematurely: sent {} != expected {}'.format(
                total_sent, file_size))


def proxy_file_to_client(sthread, file_id, verify=False):

    url = urlparse.urljoin(sthread.data_server_url, file_id)
    log.info('Download request: {}'.format(url))

    headers = {
        'X-Auth-Token': sthread.token,
    }

    r = requests.get(url, headers=headers, verify=verify, stream=True)
    _check_status_code(sthread, r, url)
    size = _send_file_header(sthread, r, url)
    _stream_data_to_client(sthread, r, size)
