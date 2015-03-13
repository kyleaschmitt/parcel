import json
import urlparse
import requests
from threading import Thread
from multiprocessing.pool import Pool

from log import get_logger
from const import RES_CHUNK_SIZE

# Logging
log = get_logger()
requests.packages.urllib3.disable_warnings()


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


def _send_blocks(sthread, blocks):
    for block in blocks:
        log.debug('Sending {} bytes'.format(len(block)))
        sthread.send(block, len(block))


def _send_async(sthread, blocks):
    """Join any previously started send thread, and start a new one

    """
    sthread_join_send_thread(sthread)
    sthread.send_thread = Thread(target=_send_blocks, args=(sthread, blocks))
    sthread.send_thread.start()


def _read_range(args):
    url, headers, start, end = args
    # parse url for host
    scheme, host, path, params, q, frag = urlparse.urlparse(url)
    # specify range
    headers['Range'] = 'bytes={}-{}'.format(start, end)
    # provide host because it's mandatory
    headers['host'] = host
    # Get data
    r = requests.get(url, headers=headers, verify=False)

    # Check data
    r.raise_for_status()
    size = end - start + 1  # the range is inclusive of upper bound
    assert len(r.content) == size, '{} != {}'.format(
        len(r.content), size)

    return r.content


def distribute(start, stop, block):
    return [(a, min(stop, a+block)-1) for a in range(start, stop, block)]


def _read_map_async(url, headers, pool, pool_size, block_size, start, max_len):
    ranges = distribute(start, max_len, block_size)[:pool_size]
    args = [[url, headers, beg, end] for beg, end in ranges]
    return pool.map_async(_read_range, args)


def _async_stream_data_to_client(sthread, url, file_size, headers,
                                 processes=4):
    """Buffer and send until StopIteration

    """

    total_sent = 0
    pool = Pool(processes)

    while total_sent < file_size:
        async_read = _read_map_async(url, headers, pool, processes,
                                     RES_CHUNK_SIZE, total_sent,
                                     file_size)
        log.debug('Joining reads')
        blocks = async_read.get()
        _send_async(sthread, blocks)
        block_lens = [len(block) for block in blocks]
        total_sent += sum(block_lens)

    # Wait for async send and finish
    sthread_join_send_thread(sthread)
    pool.close()

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
    r.close()
    _async_stream_data_to_client(sthread, url, size, headers)
