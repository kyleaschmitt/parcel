import urlparse
import requests
from threading import Thread
from multiprocessing.pool import Pool
import os
from math import ceil

from log import get_logger
from const import RES_CHUNK_SIZE
from utils import print_download_information

# Logging
log = get_logger()
try:
    requests.packages.urllib3.disable_warnings()
except Exception as e:
    log.error('Unable to silence requests warnings: {}'.format(str(e)))


####################################################################
#                            Util functions
####################################################################


def _check_transfer_size(actual, expected):
    if actual != expected:
        raise ValueError(
            'Transfer size incorrect: {} != {} expected'.format(
                actual, expected))


def write_offest(path, data, offset):
    f = open(path, 'r+b')
    f.seek(offset)
    f.write(data)
    f.close()


def set_file_length(path, length):
    f = open(path, 'wb')
    f.seek(length-1)
    f.write('\0')
    f.close()


def distribute(start, stop, block):
    """return a list of blocks in sizes no larger than `block`, the last
    block can be smaller.

    """
    return [(a, min(stop, a+block)-1) for a in range(start, stop, block)]


def add_range_to_header(url, header, start, end):
    # parse url for host
    scheme, host, path, params, q, frag = urlparse.urlparse(url)
    header = {key: value for key, value in header.items()}
    header['Range'] = 'bytes={}-{}'.format(start, end)
    # provide host because it's mandatory, range request doesn't work otherwise
    header['host'] = host
    return header


def construct_header(token, start=None, end=None):
    return {
        'X-Auth-Token': token,
    }


def _check_status_code(r, url):
    """Handle an un/successful requests.

    If unsuccessful, return errors. Return of NoneType means
    success. This is atypical but useful.

    """
    if r.status_code != 200:
        msg = 'Request failed: ERROR {}: {}'.format(
            r.status_code, r.text.replace('\n', ''))
        log.error(str(msg))
        return msg
    return None

####################################################################
#                          SThread functions
####################################################################


def make_file_request(url, headers, verify=False):
    """Make request for file, just get the header.

    If unsuccessful, return errors. Return of NoneType means
    success. This is atypical but useful.

    :returns: (errormsg, file size, file_name, request status code)

    """
    r = requests.get(url, headers=headers, verify=verify, stream=True)
    errors = _check_status_code(r, url)
    size, file_name = _parse_file_header(r, url)
    r.close()
    return errors, size, file_name, r.status_code


def _parse_file_header(r, url):
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


def sthread_join_send_thread(sthread):
    """If the sthread already has a send_thread, then join it

    :returns: None

    """
    if sthread.send_thread:
        sthread.send_thread.join()
        sthread.send_thread = None


def _send_blocks(sthread, blocks):
    """Loop over blocks and send them serially.  Included here as a target
    for async writes to UDT.

    :returns: None

    """
    for block in blocks:
        log.debug('Sending {} bytes'.format(len(block)))
        sthread.send(block, len(block))


def _send_async(sthread, blocks):
    """Join any previously started send thread, and start a new one

    :returns: None

    """
    sthread_join_send_thread(sthread)
    sthread.send_thread = Thread(target=_send_blocks, args=(sthread, blocks))
    sthread.send_thread.start()


def _read_range(args):
    url, headers, start, end, retries = args
    # specify range
    headers = add_range_to_header(url, headers, start, end)
    size = end - start + 1  # the range is inclusive of upper bound

    try:
        # Get data
        log.debug('Reading range: [{}]'.format(headers.get('Range')))
        r = requests.get(url, headers=headers, verify=False)

        # Check data
        r.raise_for_status()
        content = r.content
        r.close()
        assert len(content) == size, '{} != {}'.format(
            len(content), size)
    except Exception as e:
        log.warn('Buffering error: {}'.format(str(e)))
        if retries > 0:
            return _read_range([url, headers, start, end, retries-1])
        else:
            raise RuntimeError('Max buffer retries exceeded: {}'.format(
                retries))

    return content


def _read_map_async(url, headers, pool, pool_size, block_size, start,
                    max_len, retries=4):
    """Get all ranges from start to max_len.  assign one range per
    process, discard the others.

    :returns: async result object.  call .get() on it when you feel like data

    """
    # Get range for each process in pool
    ranges = distribute(start, max_len, block_size)[:pool_size]
    # Create args for each process
    args = [[url, headers, beg, end, retries] for beg, end in ranges]
    # Async read from data server. Return handler, call .get() later
    return pool.map_async(_read_range, args)


def _async_stream_data_to_client(sthread, url, file_size, headers,
                                 processes, buffer_retries,
                                 block_size=RES_CHUNK_SIZE):
    """Buffer and send

    1. async buffer get in parallel
    2. async send the blocks that we got last time (none the 1st round)
    3. wait for the buffering to return
    4. goto 1 until read complete
    5. send last set of blocks

    """
    log.info('Proxying {} to client'.format(url))

    total_sent = 0
    pool = Pool(processes)

    blocks = []
    while total_sent < file_size:
        # Start new read
        async_read = _read_map_async(url, headers, pool, processes,
                                     block_size, total_sent,
                                     file_size, buffer_retries)
        # Write any data we got last round, waits for last send to complete
        log.debug('Writing {} bytes'.format(sum(map(len, blocks))))
        _send_async(sthread, blocks)
        # Get more data while sending
        log.debug('Joining async read')
        blocks = async_read.get()
        # Count the rest we just read
        total_sent += sum([len(block) for block in blocks])

    # Send last round of data
    log.debug('Writing last {} bytes'.format(sum(map(len, blocks))))
    _send_async(sthread, blocks)
    # Wait for send to complete and close the pool
    sthread_join_send_thread(sthread)
    pool.close()
    _check_transfer_size(file_size, total_sent)


def proxy_file_to_client(sthread, file_id, processes, verify=False,
                         buffer_retries=4):

    url = urlparse.urljoin(sthread.data_server_url, file_id)
    log.info('Download request: {}'.format(url))

    headers = construct_header(sthread.token)
    try:
        errors, size, file_name, status_code = make_file_request(url, headers)
    except Exception as e:
        sthread.send_json({'error': str(e)})
        return str(e)

    # Send file header to client
    sthread.send_json({
        'error': errors,
        'file_size': size,
        'file_name': file_name,
        'status_code': status_code,
    })

    if not errors:
        _async_stream_data_to_client(sthread, url, size, headers,
                                     processes, buffer_retries)

    return None


####################################################################
#                        HTTPClient functions
####################################################################


def _read_write_range(path, url, headers, start, end):
    headers = add_range_to_header(url, headers, start, end)
    log.debug('Reading range: [{}]'.format(headers.get('Range')))
    r = requests.get(url, headers=headers, verify=False, stream=True)
    offset = start
    total_written = 0
    # Then streaming of the data itself.
    for chunk in r.iter_content(chunk_size=RES_CHUNK_SIZE):
        if not chunk:
            continue  # Empty are keep-alives.
        write_offest(path, chunk, offset)
        offset += len(chunk)
        total_written += len(chunk)

    return total_written


def _try_retry_read_write_range(args):
    path, url, headers, start, end, retries = args
    try:
        written = _read_write_range(path, url, headers, start, end)
        _check_transfer_size(end-start+1, written)  # range is inclusive
    except ValueError as e:
        log.warn('Buffering error: {}'.format(str(e)))
        if retries > 0:
            return _try_retry_read_write_range(
                [path, url, headers, start, end, retries-1])
        else:
            raise RuntimeError('Max buffer retries exceeded: {}'.format(
                retries))
    return written


def parallel_http_download(url, token, file_id, directory, processes,
                           verify=False, buffer_retries=4,
                           block_size=RES_CHUNK_SIZE):

    url = urlparse.urljoin(url, file_id)
    headers = construct_header(token)
    try:
        log.info('Request to {} to url'.format(url))
        errors, size, file_name, status_code = make_file_request(url, headers)
    except Exception as e:
        log.error(str(e))
        return -1

    if errors:
        return -1

    file_path = os.path.join(directory, '{}.{}'.format(file_id, file_name))
    print_download_information(file_id, size, file_name, file_path)
    set_file_length(file_path, size)
    pool = Pool(processes)
    # Get range for each process in pool
    block_size = int(ceil(float(size)/processes))
    ranges = distribute(0, size, block_size)

    # Create args for each process
    args = [[file_path, url, headers, beg, end, buffer_retries]
            for beg, end in ranges]
    total_sent = sum(pool.map(_try_retry_read_write_range, args))
    pool.close()
    _check_transfer_size(size, total_sent)

    return total_sent
