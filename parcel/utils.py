from functools import wraps
from progressbar import ProgressBar, Percentage, Bar, ETA, FileTransferSpeed

from const import GB
from log import get_logger
from lib import lib
import time
import urlparse
import requests
from const import HTTP_CHUNK_SIZE, RES_CHUNK_SIZE

# Logging
log = get_logger('utils')

# Silence warnings from requests
try:
    requests.packages.urllib3.disable_warnings()
except Exception as e:
    log.info('Unable to silence requests warnings: {}'.format(str(e)))


def get_pbar(file_id, maxval):
    """Create and initialize a custom progressbar

    :param str title: The text of the progress bar
    "param int maxva': The maximumum value of the progress bar

    """
    title = 'Downloading {}: '.format(file_id)
    pbar = ProgressBar(widgets=[
        title, Percentage(), ' ',
        Bar(marker='#', left='[', right=']'), ' ',
        ETA(), ' ', FileTransferSpeed(), ' '], maxval=maxval)
    pbar.update(0)
    return pbar


def monitor_transfer(client, file_id, total_size):
    pbar = get_pbar('File: {}'.format(file_id), total_size)
    time.sleep(1)
    while (lib.get_client_live(client.instance)):
        try:
            pbar.update(lib.get_client_downloaded(client.instance))
        except:
            pass
        time.sleep(1)
    pbar.finish()


def print_download_information(file_id, size, name, path):
    log.info('-'*40)
    log.info('Starting download   : {}'.format(file_id))
    log.info('-'*40)
    log.info('File name           : {}'.format(name))
    log.info('Download size       : {} B ({:.2f} GB)'.format(
        size, (size / float(GB))))
    log.info('Downloading file to : {}'.format(path))


def vec(val):
    return val if hasattr(val, '__iter__') else [val]


def state_method(*states):
    """Enter a new state

    :param states:
        A list of str or single str specifying the states that are
        valid preceeding this one

    """

    def wrapper(func, *args, **kwargs):
        @wraps(func)
        def f(self, *args, **kwargs):
            assert self.state in vec(states), \
                'Moving from state <{}> to <{}> is invalid'.format(
                    self.state, func.__name__)
            self.state = func.__name__
            log.debug('{}: Entering state: {}'.format(self, self.state))
            try:
                return func(self, *args, **kwargs)
            except KeyboardInterrupt:
                log.error('KeyboardInterrupt in state {}'.format(self.state))
                self.close()
            log.debug('{}: Exiting state: {}'.format(self, self.state))
        return f
    return wrapper


def parse_ranges(ranges):
    """Validate an HTTP ranges, throwing an exception if it isn't something
    we support. For now we only support things of the form bytes={begin}-{end}

    """
    try:
        ranges = ranges.strip()
        unit, nums = ranges.split("=")
        if unit != "bytes":
            raise RuntimeError(
                "Only byte rangess are supported, not {}".format(unit))
        begin, end = nums.split("-")
        begin, end = int(begin), int(end)
        if end < begin:
            raise RuntimeError("impossible ranges: {}".format(ranges))
        else:
            return begin, end
    except ValueError:
        raise RuntimeError("Malformed ranges: {}".format(ranges))


def check_transfer_size(actual, expected):
    if actual != expected:
        raise ValueError(
            'Transfer size incorrect: {} != {} expected'.format(
                actual, expected))


def write_offset(path, data, offset):
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


def check_status_code(r, url):
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


def read_range(path, url, headers, start, end):
    headers = add_range_to_header(url, headers, start, end)
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


def parse_file_header(r, url):
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


def make_file_request(url, headers, verify=False):
    """Make request for file, just get the header.

    If unsuccessful, return errors. Return of NoneType means
    success. This is atypical but useful.

    :returns: (errormsg, file size, file_name, request status code)

    """
    r = requests.get(url, headers=headers, verify=verify, stream=True)
    errors = check_status_code(r, url)
    size, file_name = parse_file_header(r, url)
    r.close()
    return errors, size, file_name, r.status_code


def read_write_range(path, url, headers, start, end, q):
    headers = add_range_to_header(url, headers, start, end)
    log.debug('Reading range: [{}]'.format(headers.get('Range')))
    r = requests.get(url, headers=headers, verify=False, stream=True)
    offset = start
    total_written = 0
    # Then streaming of the data itself.
    for chunk in r.iter_content(chunk_size=HTTP_CHUNK_SIZE):
        if not chunk:
            continue  # Empty are keep-alives.
        write_offset(path, chunk, offset)
        written = len(chunk)
        offset += written
        total_written += written
        q.put(written)

    return total_written


def try_retry_read_write_range(args):
    path, url, headers, start, end, retries, q = args
    try:
        written = read_write_range(path, url, headers, start, end, q)
        check_transfer_size(end-start+1, written)  # range is inclusive
    except ValueError as e:
        log.warn('Buffering error: {}'.format(str(e)))
        if retries > 0:
            return try_retry_read_write_range(
                [path, url, headers, start, end, retries-1, q])
        else:
            raise RuntimeError('Max buffer retries exceeded: {}'.format(
                retries))
    return written
