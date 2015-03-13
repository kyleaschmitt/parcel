import json
import urlparse
import requests
from threading import Thread

from log import get_logger

from const import RES_CHUNK_SIZE

# Logging
log = get_logger()


def _check_status_code(sthread, r, url):
    """Handle an un/successful requests.

    """
    if r.status_code != 200:
        # Failed to get file, notify the client
        msg = 'Request failed: {} {}'.format(url, r.text)
        log.warn(str(msg))
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


def sthread_join_send_thread(sthread):
    """If the sthread already has a send_thread, then join it

    """
    if sthread.send_thread:
        sthread.send_thread.join()
        sthread.send_thread = None


def _send_async(sthread, block):
    """Join any previously started send thread, and start a new one

    """

    sthread_join_send_thread(sthread)
    sthread.send_thread = Thread(target=sthread.send, args=(block, len(block)))
    sthread.send_thread.start()


def _stream_data_to_client(sthread, r, file_size):
    """Buffer and send until StopIteration

    """

    total_sent = 0

    # Iterate over file and send async to client
    for chunk in r.iter_content(chunk_size=RES_CHUNK_SIZE):
        if not chunk:
            continue  # Empty are keep-alives.
        _send_async(sthread, chunk)
        total_sent += len(chunk)

    # Wait for async send to finish
    sthread_join_send_thread(sthread)

    # Check size
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
