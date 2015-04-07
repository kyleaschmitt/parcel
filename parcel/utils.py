from progressbar import ProgressBar, Percentage, Bar, ETA, FileTransferSpeed
from stat import S_ISDIR, S_ISCHR, S_ISBLK, S_ISREG, S_ISFIFO, \
    S_ISLNK, S_ISSOCK

import os
from const import GB
from log import get_logger
import requests
import hashlib
import mmap
from contextlib import contextmanager

# Logging
log = get_logger('utils')

# Silence warnings from requests
try:
    requests.packages.urllib3.disable_warnings()
except Exception as e:
    log.info('Unable to silence requests warnings: {}'.format(str(e)))


def get_pbar(file_id, maxval, start_val=0):
    """Create and initialize a custom progressbar

    :param str title: The text of the progress bar
    "param int maxva': The maximumum value of the progress bar

    """
    title = 'Downloading {}: '.format(file_id)
    pbar = ProgressBar(widgets=[
        title, Percentage(), ' ',
        Bar(marker='#', left='[', right=']'), ' ',
        ETA(), ' ', FileTransferSpeed(), ' '], maxval=maxval)
    pbar.currval = start_val
    pbar.start()
    return pbar


def print_download_information(file_id, size, name, path):
    log.info('-'*40)
    log.info('Starting download   : {}'.format(file_id))
    log.info('-'*40)
    log.info('File name           : {}'.format(name))
    log.info('Download size       : {} B ({:.2f} GB)'.format(
        size, (size / float(GB))))
    log.info('Downloading file to : {}'.format(path))


def write_offset(path, data, offset):
    try:
        f = open(path, 'r+b')
        f.seek(offset)
        f.write(data)
        f.close()
    except Exception as e:
        raise Exception('Unable to write offset: {}'.format(str(e)))


def read_offset(path, offset, size):
    try:
        f = open(path, 'r+b')
        f.seek(offset)
        data = f.read(size)
        f.close()
        return data
    except Exception as e:
        raise Exception('Unable to read offset: {}'.format(str(e)))


def set_file_length(path, length):
    try:
        if os.path.isfile(path) and os.path.getsize(path) == length:
            return
        f = open(path, 'wb')
        f.seek(length-1)
        f.write('\0')
        f.truncate()
        f.close()
    except Exception as e:
        raise Exception('Unable to set file length: {}'.format(str(e)))


def get_file_type(path):
    try:
        mode = os.stat(path).st_mode
        if S_ISDIR(mode):
            return 'directory'
        elif S_ISCHR(mode):
            return 'character device'
        elif S_ISBLK(mode):
            return 'block device'
        elif S_ISREG(mode):
            return 'regular'
        elif S_ISFIFO(mode):
            return 'fifo'
        elif S_ISLNK(mode):
            return 'link'
        elif S_ISSOCK(mode):
            return 'socket'
        else:
            return 'unknown'
    except Exception as e:
        raise RuntimeError('Unable to get file type: {}'.format(str(e)))


def calculate_segments(start, stop, block):
    """return a list of blocks in sizes no larger than `block`, the last
    block can be smaller.

    """
    return [(a, min(stop, a+block)-1) for a in range(start, stop, block)]


def md5sum(block):
    m = hashlib.md5()
    m.update(block)
    return m.hexdigest()


@contextmanager
def mmap_open(path):
    try:
        with open(path, "r+b") as f:
            mm = mmap.mmap(f.fileno(), 0)
            yield mm
    except Exception as e:
        raise RuntimeError('Unable to get file type: {}'.format(str(e)))
