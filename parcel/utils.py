from functools import wraps
from progressbar import ProgressBar, Percentage, Bar, ETA, FileTransferSpeed

from const import GB
from log import get_logger
from lib import lib
import time
import requests

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


def calculate_segments(start, stop, block):
    """return a list of blocks in sizes no larger than `block`, the last
    block can be smaller.

    """
    return [(a, min(stop, a+block)-1) for a in range(start, stop, block)]
